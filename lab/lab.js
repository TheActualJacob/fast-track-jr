// Mission Lab: write a mission, fly it in the browser (Pyodide), watch the 3D replay, submit it.
const $ = (id) => document.getElementById(id);
const BASE = new URL('../', import.meta.url);           // site root (works on GitHub Pages sub-paths)
const FIELDS = {
  jr: { course: 'course/fast_track_jr.json', template: 'missions/_template.py', folder: 'missions', label: 'Fast Track Jr.' },
  real: { course: 'course/fast_track_2027.json', template: 'training/_template_real.py', folder: 'training', label: 'Mission 2027: Fast Track · official solo field' },
};
const FLY_TIMEOUT_MS = 15000;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const mmss = (t) => { t = Math.max(0, t || 0); const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(1).padStart(4, '0')}`; };
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

// Where pull requests go: detected on GitHub Pages (<owner>.github.io/<repo>/), otherwise the club repo.
const REPO = (() => {
  const m = location.hostname.match(/^([^.]+)\.github\.io$/);
  const seg = location.pathname.split('/').filter(Boolean)[0];
  return m && seg ? `${m[1]}/${seg}` : 'TheActualJacob/fast-track-jr';
})();

// ------------------------------------------------------------------ editor
const editor = CodeMirror($('editor'), {
  mode: 'python', theme: 'ftj', lineNumbers: true, indentUnit: 4, tabSize: 4, indentWithTabs: false,
  matchBrackets: true, gutters: ['CodeMirror-linenumbers', 'ftj-marks'],
  extraKeys: {
    Tab: (cm) => cm.execCommand(cm.somethingSelected() ? 'indentMore' : 'insertSoftTab'),
    'Shift-Tab': 'indentLess',
    'Ctrl-Enter': () => fly(),
    'Cmd-Enter': () => fly(),
  },
});
let field = FIELDS[store.get('lab.field')] ? store.get('lab.field') : 'jr';
let saveTimer = null;
let errMark = null;
editor.on('change', () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => store.set(`lab.code.${field}`, editor.getValue()), 400);
  if (errMark) { editor.removeLineClass(errMark, 'wrap', 'err-line'); errMark = null; }
});

const nameInput = $('name');
nameInput.value = store.get('lab.name') || '';
const cleanName = () => nameInput.value.trim().replace(/[^A-Za-z0-9-]/g, '');
nameInput.addEventListener('input', () => {
  nameInput.classList.remove('bad');
  store.set('lab.name', nameInput.value.trim());
  $('fileLabel').textContent = `${FIELDS[field].folder}/${cleanName() || 'your-username'}.py`;
});

const courses = {};
async function getCourse(f) {
  if (!courses[f]) courses[f] = await (await fetch(new URL(FIELDS[f].course, BASE))).json();
  return courses[f];
}
async function getTemplate(f) {
  return (await fetch(new URL(FIELDS[f].template, BASE), { cache: 'no-cache' })).text();
}

async function setField(f, code = null) {
  field = f;
  store.set('lab.field', f);
  $('field').value = f;
  $('courseLabel').textContent = FIELDS[f].label;
  $('guide').hidden = f !== 'jr';
  $('fileLabel').textContent = `${FIELDS[f].folder}/${cleanName() || 'your-username'}.py`;
  editor.setValue(code ?? store.get(`lab.code.${f}`) ?? await getTemplate(f));
  editor.clearHistory();
  clearRunMarks();
  lastLog = null;
  exploreViewer();
}
$('field').addEventListener('change', (e) => setField(e.target.value));
$('reset').addEventListener('click', async () => {
  if (!confirm('Throw away your code and start again from the template?')) return;
  editor.setValue(await getTemplate(field));
});

// ------------------------------------------------------------------ Python worker
let worker = null;
let ready = false;
let queued = false;
let flying = null;
const flyBtn = $('fly');

function setStatus(text, cls = '') {
  const s = $('status');
  s.textContent = text;
  s.className = 'status ' + cls;
}

function startWorker() {
  ready = false;
  flyBtn.disabled = true;
  worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.type === 'ready') {
      ready = true;
      flyBtn.disabled = false;
      setStatus('Ready', 'ok');
      if (queued) { queued = false; fly(); }
    } else if (m.type === 'fatal') {
      setStatus('Couldn’t load Python. Check your internet connection and reload.', 'bad');
    } else if (m.type === 'result') {
      finish(m.log);
    } else if (m.type === 'error') {
      clearTimeout(flying); flying = null;
      flyBtn.disabled = false;
      setStatus('Simulator error', 'bad');
      $('output').innerHTML = `<ul class="msgs"><li class="bad">The simulator itself hit a problem: ${esc(m.message)}</li></ul>`;
    }
  };
  worker.postMessage({ type: 'init', base: BASE.href });
  setStatus('Loading Python…', 'busy');
}

async function fly() {
  if (flying) return;
  if (!ready) { queued = true; setStatus('Loading Python… will fly as soon as it’s ready', 'busy'); return; }
  const name = cleanName() || 'pilot';
  const course = await getCourse(field);
  clearRunMarks();
  setStatus('Flying…', 'busy');
  flyBtn.disabled = true;
  flying = setTimeout(() => {
    // a mission that never finishes: kill the worker and start a fresh one
    worker.terminate();
    flying = null;
    startWorker();
    showMessage('bad', 'Your program ran for a long time without finishing. Is there a <span class="mono">while</span> loop that never ends, or never calls the drone?');
  }, FLY_TIMEOUT_MS);
  worker.postMessage({ type: 'run', code: editor.getValue(), filename: `${name}.py`, name, course });
}
flyBtn.addEventListener('click', fly);

// ------------------------------------------------------------------ results
let lastLog = null;

function helperLines(log) {
  const outers = {};
  for (const c of log.calls || []) if (c.line && c.outer?.length) (outers[c.line] ||= new Set()).add(c.outer[0]);
  return new Set(Object.keys(outers).filter((k) => outers[k].size > 1).map(Number));
}
function creditLine(log, ev, helpers) {
  if (!ev?.line) return null;
  return ev.outer?.length && helpers.has(ev.line) ? ev.outer[0] : ev.line;
}

function finish(log) {
  clearTimeout(flying); flying = null;
  if (document.body.classList.contains('result-collapsed')) setResultOpen(true);
  flyBtn.disabled = false;
  lastLog = log;
  setStatus(`Flown · ${log.result.score} points`, 'ok');
  renderResult(log);
  loadViewer(log);
}

function renderResult(log) {
  const r = log.result;
  const helpers = helperLines(log);
  const src = log.source.split('\n');
  let kind = 'good', kicker = 'Run complete', title, why = '';
  if (log.crash) {
    const ln = creditLine(log, log.crash, helpers);
    kind = 'bad'; kicker = 'Crash';
    title = `Hit the ${log.crash.what.replace(/^the /, '')} at ${mmss(log.crash.t)}`;
    if (ln) why = `Line ${ln} · <span class="mono">${esc((src[ln - 1] || '').trim())}</span>`;
  } else if (log.error) {
    kind = 'bad'; kicker = 'Bug in your code';
    title = `${esc(log.error.type)}${log.error.line ? ` on line ${log.error.line}` : ''}`;
    why = esc(log.error.message);
  } else if (r.landing === 'land_bullseye') {
    kind = 'best'; title = 'Landed on the bullseye';
  } else if (r.status === 'landed') {
    title = { land_pad: 'Landed on the landing pad', land_cube: 'Landed on a cube' }[r.landing] || 'Landed on the floor';
    if (!r.landing) { kind = 'neutral'; why = 'No landing points'; }
  } else if (r.status === 'never took off') {
    kind = 'neutral'; kicker = 'No flight'; title = 'The drone never took off'; why = 'Did you call <span class="mono">drone.takeoff()</span>?';
  } else {
    kind = 'neutral'; kicker = 'Program ended'; title = `Drone ${esc(r.status)}`;
  }
  const tasks = (r.breakdown || []).filter((t) => !t.group || t.count)
    .map((t) => `<span class="${t.count ? 'done' : ''}">${esc(t.label)}${t.count ? ` +${t.points * t.count}` : ''}</span>`).join('');
  const msgs = (log.events || []).filter((e) => e.type === 'warn')
    .map((e) => `<li>${esc(e.text)}${creditLine(log, e, helpers) ? `<span class="ln">line ${creditLine(log, e, helpers)}</span>` : ''}</li>`).join('');
  const prints = (log.console || []).filter((c) => !c.text.startsWith('[sim]'));
  $('output').innerHTML = `
    <div class="res ${kind}"><div class="accentbar"></div>
      <div><div class="kicker">${kicker}</div><div class="title">${title}</div>${why ? `<div class="why">${why}</div>` : ''}</div>
      <div class="nums"><div class="num"><b>${r.score}</b><span>Points</span></div><div class="num"><b>${mmss(r.finish_time)}</b><span>Time</span></div></div>
    </div>
    <div class="tasks">${tasks}</div>
    ${msgs ? `<ul class="msgs">${msgs}</ul>` : ''}
    ${prints.length ? `<div class="console-head">print() output</div><div class="console">${prints.map((c) => `<div><span class="t">${mmss(c.t)}</span>${esc(c.text)}</div>`).join('')}</div>` : ''}`;
  const badLine = log.error?.line || (log.crash && creditLine(log, log.crash, helpers));
  if (badLine && badLine <= editor.lineCount()) {
    errMark = editor.addLineClass(badLine - 1, 'wrap', 'err-line');
    editor.scrollIntoView({ line: badLine - 1, ch: 0 }, 80);
  }
}

function showMessage(cls, html) {
  setStatus(cls === 'bad' ? 'Stopped' : 'Ready', cls === 'bad' ? 'bad' : 'ok');
  $('output').innerHTML = `<ul class="msgs"><li class="${cls}">${html}</li></ul>`;
}

// ------------------------------------------------------------------ the embedded 3D viewer
let pendingLog = null;
function loadViewer(log) {
  pendingLog = log;
  $('viewer').src = `sim/viewer/index.html?run=parent&embed=1&autoplay=1&n=${Date.now()}`;
}
function exploreViewer() {
  pendingLog = null;
  $('viewer').src = `sim/viewer/index.html?embed=1&course=${encodeURIComponent(FIELDS[field].course)}`;
}

let hl = [];
function highlight(line, outer = []) {
  for (const h of hl) editor.removeLineClass(h.handle, 'background', h.cls);
  hl = [];
  const add = (n, cls) => {
    if (n > 0 && n <= editor.lineCount()) hl.push({ handle: editor.addLineClass(n - 1, 'background', cls), cls });
  };
  add(line, 'run-line');
  for (const o of outer || []) add(o, 'run-outer');
  if (line > 0 && !editor.hasFocus()) editor.scrollIntoView({ line: line - 1, ch: 0 }, 90);
}
function setMarks(marks) {
  editor.clearGutter('ftj-marks');
  const byLine = {};
  for (const m of marks || []) if (m.line) (byLine[m.line] ||= []).push(m);
  for (const [ln, ms] of Object.entries(byLine)) {
    if (+ln > editor.lineCount()) continue;
    const bad = ms.find((m) => m.bad);
    const el = document.createElement('div');
    el.className = 'gmark' + (bad ? ' bad' : '');
    el.textContent = bad ? bad.text : `+${ms.reduce((a, m) => a + parseInt(m.text.slice(1), 10), 0)}`;
    editor.setGutterMarker(+ln - 1, 'ftj-marks', el);
  }
}
function clearRunMarks() {
  highlight(0);
  editor.clearGutter('ftj-marks');
  if (errMark) { editor.removeLineClass(errMark, 'wrap', 'err-line'); errMark = null; }
}

addEventListener('message', (e) => {
  if (e.origin !== location.origin || !e.data) return;
  const m = e.data;
  if (m.type === 'viewer-ready' && pendingLog) e.source.postMessage({ type: 'run', log: pendingLog }, location.origin);
  else if (m.type === 'line') highlight(m.line, m.outer);
  else if (m.type === 'marks') setMarks(m.marks);
});

// ------------------------------------------------------------------ submitting
function toast(text, ms = 3200) {
  const t = $('toast');
  t.textContent = text;
  t.classList.add('on');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove('on'), ms);
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

async function pack(obj) {
  const stream = new Blob([JSON.stringify(obj)]).stream().pipeThrough(new CompressionStream('deflate-raw'));
  const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function unpack(str) {
  const b64 = str.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((str.length + 3) % 4);
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return JSON.parse(await new Response(stream).text());
}

function needName() {
  if (cleanName()) return false;
  nameInput.classList.add('bad');
  nameInput.focus();
  toast('Type your GitHub username first (top bar).');
  return true;
}

const menu = $('submitMenu');
$('submitBtn').addEventListener('click', (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; });
addEventListener('click', () => { menu.hidden = true; });
menu.addEventListener('click', async (e) => {
  const act = e.target.closest('button')?.dataset.act;
  if (!act) return;
  const code = editor.getValue();
  const name = cleanName();
  if (act === 'pr') {
    if (needName()) return;
    // folder goes inside the filename: GitHub drops the last URL folder when ?filename= is given
    const file = `${FIELDS[field].folder}/${name}.py`;
    let url = `https://github.com/${REPO}/new/main?filename=${encodeURIComponent(file)}&value=${encodeURIComponent(code)}`;
    const copied = await copy(code);
    if (url.length > 7500) url = `https://github.com/${REPO}/new/main?filename=${encodeURIComponent(file)}`;
    window.open(url, '_blank', 'noopener');
    toast(copied ? 'Opened GitHub. Your code is also copied, so if it asks you to fork first, paste it in after.' : 'Opened GitHub.', 6000);
  } else if (act === 'link') {
    const link = `${location.origin}${location.pathname}#m=${await pack({ n: name || 'pilot', f: field, c: code })}`;
    toast((await copy(link)) ? 'Share link copied. Paste it where your leader asks.' : 'Couldn’t copy. Your browser blocked the clipboard.', 4500);
  } else if (act === 'download') {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([code], { type: 'text/x-python' }));
    a.download = `${name || 'mission'}.py`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  menu.hidden = true;
});

// ------------------------------------------------------------------ layout: resize + collapse (remembered)
const root = document.documentElement;
function refreshEditor() { requestAnimationFrame(() => editor.refresh()); }

function dragHandle(handle, axis, onMove, onEnd) {
  handle.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    handle.classList.add('drag');
    document.body.classList.add('dragging', axis === 'x' ? 'dragging-x' : 'dragging-y');
    const move = (ev) => onMove(ev);
    const up = () => {
      handle.removeEventListener('pointermove', move);
      handle.classList.remove('drag');
      document.body.classList.remove('dragging', 'dragging-x', 'dragging-y');
      onEnd();
      refreshEditor();
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up, { once: true });
    handle.addEventListener('pointercancel', up, { once: true });
  });
}

// code | replay divider
dragHandle($('vsplit'), 'x', (ev) => {
  const w = Math.max(300, Math.min(innerWidth - 380, ev.clientX));
  root.style.setProperty('--code-w', `${Math.round(w)}px`);
}, () => store.set('lab.codeW', root.style.getPropertyValue('--code-w')));
$('vsplit').addEventListener('dblclick', () => { root.style.removeProperty('--code-w'); store.set('lab.codeW', ''); refreshEditor(); });

// editor / result divider
dragHandle($('hsplit'), 'y', (ev) => {
  const pane = $('leftPane').getBoundingClientRect();
  const h = Math.max(60, Math.min(pane.height - 160, pane.bottom - ev.clientY - 34));
  root.style.setProperty('--out-h', `${Math.round(h)}px`);
}, () => store.set('lab.outH', root.style.getPropertyValue('--out-h')));
$('hsplit').addEventListener('dblclick', () => { root.style.removeProperty('--out-h'); store.set('lab.outH', ''); refreshEditor(); });

function setCodeOpen(open) {
  document.body.classList.toggle('code-collapsed', !open);
  $('codeRail').hidden = open;
  store.set('lab.codeOpen', open ? '1' : '0');
  if (open) refreshEditor();
}
function setResultOpen(open) {
  document.body.classList.toggle('result-collapsed', !open);
  store.set('lab.resultOpen', open ? '1' : '0');
  refreshEditor();
}
$('collapseCode').addEventListener('click', () => setCodeOpen(false));
$('codeRail').addEventListener('click', () => setCodeOpen(true));
$('toggleResult').addEventListener('click', () => setResultOpen(document.body.classList.contains('result-collapsed')));
$('resultHead').addEventListener('dblclick', () => setResultOpen(document.body.classList.contains('result-collapsed')));
addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
    e.preventDefault();
    setCodeOpen(document.body.classList.contains('code-collapsed'));
  }
});
addEventListener('resize', refreshEditor);

if (store.get('lab.codeW')) root.style.setProperty('--code-w', store.get('lab.codeW'));
if (store.get('lab.outH')) root.style.setProperty('--out-h', store.get('lab.outH'));
if (store.get('lab.codeOpen') === '0') setCodeOpen(false);
if (store.get('lab.resultOpen') === '0') setResultOpen(false);

// ------------------------------------------------------------------ start up
(async () => {
  startWorker();
  const m = location.hash.match(/^#m=([\w-]+)/);
  if (m) {
    try {
      const shared = await unpack(m[1]);
      await setField(FIELDS[shared.f] ? shared.f : 'jr', shared.c);
      $('output').innerHTML = `<p class="muted">Loaded <b>${esc(shared.n)}</b>'s mission from a share link. Flying it…</p>`;
      queued = true;
      if (ready) { queued = false; fly(); }
      return;
    } catch {
      toast('That share link looks broken.');
    }
  }
  await setField(field);
  $('fileLabel').textContent = `${FIELDS[field].folder}/${cleanName() || 'your-username'}.py`;
})();
