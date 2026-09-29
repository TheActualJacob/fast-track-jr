// Fast Track Jr. — 3D flight replay.
// Sim coordinates (cm): x forward, y left, z up.  three.js: X = x, Y = z, Z = -y.
import * as THREE from 'three';

const $ = (id) => document.getElementById(id);
const P = new URLSearchParams(location.search);
const W = (x, y, z = 0) => new THREE.Vector3(x, z, -y);
const PALETTE = ['#ff4d6d', '#4cc9f0', '#5ee08a', '#ffd166', '#c77dff', '#ff9f1c', '#2ec4b6', '#f15bb5',
  '#9ef01a', '#00bbf9', '#fb8500', '#e9ff70', '#8ecae6', '#ffafcc', '#b8f2e6', '#f4a261'];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const mmss = (t) => { t = Math.max(0, t || 0); const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(1).padStart(4, '0')}`; };
const store = {
  get(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};

// ------------------------------------------------------------------ data
// everything is fetched relative to the site root, so this also works from a sub-folder (GitHub Pages)
const BASE = new URL('../../', import.meta.url);
const EMBED = !!P.get('embed');          // inside the Mission Lab page
if (EMBED) document.body.classList.add('embed');
const toParent = (msg) => { if (EMBED && parent !== window) parent.postMessage(msg, location.origin); };

async function getJSON(path) {
  const r = await fetch(new URL(path.replace(/^\/+/, ''), BASE), { cache: 'no-store' });
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

async function loadData() {
  let session = null;
  const runs = [];
  if (P.get('runs')) {
    session = await getJSON(P.get('runs'));
    for (const meta of session.runs) {
      try { runs.push(Object.assign(await getJSON(meta.file), { meta })); } catch (e) { console.warn(e); }
    }
  } else if (P.get('run') === 'parent') {
    // the Mission Lab hands us the flight log it just simulated in the browser
    runs.push(await new Promise((resolve) => {
      addEventListener('message', function onMsg(e) {
        if (e.origin !== location.origin || e.data?.type !== 'run') return;
        removeEventListener('message', onMsg);
        resolve(e.data.log);
      });
      parent.postMessage({ type: 'viewer-ready' }, location.origin);
    }));
  } else if (P.get('run')) {
    runs.push(await getJSON(P.get('run')));
  }
  const course = runs[0]?.course || await getJSON(P.get('course') || 'course/fast_track_jr.json');
  return { session, runs, course };
}

const { session, runs, course } = await loadData();
const EXPLORE = runs.length === 0;
const LIMIT = course.time_limit_s || 180;
const ranked = [...runs].sort((a, b) => (b.result.score - a.result.score) || ((a.result.finish_time || 1e9) - (b.result.finish_time || 1e9)));
runs.forEach((r, i) => { r.color = PALETTE[i % PALETTE.length]; r.idx = i; r.meta = r.meta || {}; });
$('courseName').textContent = course.name || 'Course';
const DURATION = EXPLORE ? 0 : Math.max(...runs.map((r) => (r.frames.length ? r.frames[r.frames.length - 1][0] : 0))) + 1.5;

// ------------------------------------------------------------------ renderer / camera
const canvas = $('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#0b0f15');
scene.fog = new THREE.Fog('#0b0f15', 1100, 2600);

const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 1, 6000);
const controls = new THREE.OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.495;
controls.minDistance = 25;
controls.maxDistance = 1800;
window.__ftj = { camera, controls, THREE };  // handy for poking around in the devtools console

// middle of the field (for framing)
const mats = course.mats;
const fx0 = Math.min(...mats.map((m) => m.x[0])), fx1 = Math.max(...mats.map((m) => m.x[1]));
const fy0 = Math.min(...mats.map((m) => m.y[0])), fy1 = Math.max(...mats.map((m) => m.y[1]));
const FIELD_C = W((fx0 + fx1) / 2, (fy0 + fy1) / 2, 40);
// wide shot from the inside corner of the L, scaled to the size of the field so everything fits
const HOME_TARGET = W((fx0 + fx1) / 2 + 18, (fy0 + fy1) / 2 - 3, 12);
const FIELD_DIAG = Math.hypot(fx1 - fx0, fy1 - fy0);
const HOME_CAM = { pos: HOME_TARGET.clone().add(new THREE.Vector3(-0.66, 0.58, 0.47).multiplyScalar(FIELD_DIAG * 1.72)), target: HOME_TARGET };

function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);
resize();

// ------------------------------------------------------------------ lights
scene.add(new THREE.HemisphereLight('#c9dbff', '#221a12', 1.25));
const sun = new THREE.DirectionalLight('#fff4e6', 2.4);
sun.position.copy(FIELD_C).add(new THREE.Vector3(-260, 620, -330));
sun.target.position.copy(FIELD_C);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
{
  const half = Math.max(420, Math.hypot(fx1 - fx0, fy1 - fy0) * 0.75);
  Object.assign(sun.shadow.camera, { left: -half, right: half, top: half, bottom: -half, near: 50, far: 2000 });
}
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.6;
scene.add(sun, sun.target);
const fill = new THREE.DirectionalLight('#7fa7ff', 0.5);
fill.position.copy(FIELD_C).add(new THREE.Vector3(400, 300, 400));
scene.add(fill);

// ------------------------------------------------------------------ helpers
const mat = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.62, metalness: 0.05, ...o });
const BLACK = mat('#15181d', { roughness: 0.5 });
const METAL = mat('#3b4048', { roughness: 0.35, metalness: 0.6 });
const pickables = [];

function shadowed(obj) {
  obj.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return obj;
}

function rod(a, b, r, material) {
  const len = a.distanceTo(b);
  const g = new THREE.CylinderGeometry(r, r, len, 10);
  const m = new THREE.Mesh(g, material);
  m.position.copy(a).add(b).multiplyScalar(0.5);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
  return m;
}

function tripod(base, height = 34, spread = 28, material = METAL) {
  const g = new THREE.Group();
  const top = base.clone().add(new THREE.Vector3(0, height, 0));
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.4;
    g.add(rod(top, base.clone().add(new THREE.Vector3(Math.cos(a) * spread, 0.5, Math.sin(a) * spread)), 0.9, material));
  }
  return g;
}

// orient a group so local +X runs along the gate, +Y is up and +Z is the fly-through direction
function gateBasis(facing) {
  const [fx, fy] = facing; const n = Math.hypot(fx, fy);
  const F = new THREE.Vector3(fx / n, 0, -fy / n);
  const L = new THREE.Vector3(-fy / n, 0, -fx / n);
  return new THREE.Matrix4().makeBasis(L, new THREE.Vector3(0, 1, 0), F);
}

function textCanvas(text, { size = 26, color = '#eef1f5', bg = 'rgba(12,15,20,0.86)', weight = 650, pad = 12, bar = null, sub = null } = {}) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const font = `${weight} ${size}px Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif`;
  const subFont = `500 ${size}px Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif`;
  ctx.font = font;
  ctx.letterSpacing = '1.5px';
  const barW = bar ? 6 : 0;
  const tw = ctx.measureText(text).width;
  ctx.font = subFont;
  const sw = sub ? ctx.measureText(sub).width + 16 : 0;
  const w = Math.ceil(barW + pad * 2 + tw + sw);
  const h = Math.ceil(size * 1.6);
  c.width = w * 2; c.height = h * 2;
  ctx.scale(2, 2);
  ctx.letterSpacing = '1.5px';
  if (bg) {
    ctx.fillStyle = bg;
    ctx.beginPath(); ctx.roundRect(0, 0, w, h, 5); ctx.fill();
  }
  if (bar) { ctx.fillStyle = bar; ctx.beginPath(); ctx.roundRect(0, 0, barW, h, [5, 0, 0, 5]); ctx.fill(); }
  ctx.textBaseline = 'middle';
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.fillText(text, barW + pad, h / 2 + 1);
  if (sub) {
    ctx.font = subFont;
    ctx.fillStyle = 'rgba(238,241,245,0.55)';
    ctx.fillText(sub, barW + pad + tw + 16, h / 2 + 1);
  }
  return c;
}

function label(text, pos, heightCm = 13, opts = {}) {
  const c = textCanvas(text, opts);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  s.scale.set(heightCm * c.width / c.height, heightCm, 1);
  s.position.copy(pos);
  s.renderOrder = 10;
  return s;
}

// ------------------------------------------------------------------ floor, mats, zones
const floor = new THREE.Mesh(new THREE.PlaneGeometry(6000, 6000), mat('#1d2229', { roughness: 0.95 }));
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(1600, 32, '#323b47', '#262d37');
grid.position.copy(FIELD_C).setY(0.05);
grid.material.transparent = true;
grid.material.opacity = 0.55;
scene.add(grid);

// ---- photo mode (?photo=1&theme=light&cam=x,y,z,tx,ty,tz&drone=x,y,z,yaw&labels=0): clean renders for docs
const PHOTO = !!P.get('photo');
const LIGHT = P.get('theme') === 'light';
if (PHOTO) document.body.classList.add('photo');
if (LIGHT) {
  scene.background = new THREE.Color('#ffffff');
  scene.fog = null;
  floor.material = new THREE.ShadowMaterial({ opacity: 0.12 });
  grid.visible = false;
  renderer.toneMappingExposure = 1.3;
  scene.traverse((o) => {
    if (o.isHemisphereLight) { o.color.set('#ffffff'); o.groundColor.set('#8a8f98'); o.intensity = 1.9; }
    if (o.isDirectionalLight && o !== sun) { o.color.set('#ffffff'); o.intensity = 0.9; }
  });
  sun.intensity = 2.0;
}

function camoTexture(wcm, hcm, seed) {
  const px = 4;
  const c = document.createElement('canvas');
  c.width = Math.round(wcm * px); c.height = Math.round(hcm * px);
  const ctx = c.getContext('2d');
  let s = seed;
  const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  ctx.fillStyle = '#c9cdd2'; ctx.fillRect(0, 0, c.width, c.height);
  const cell = 9;
  for (const [col, blobs, size] of [['#9ba1a8', 120, 9], ['#6d737b', 110, 7], ['#3c4148', 90, 6], ['#e9ecef', 80, 5]]) {
    ctx.fillStyle = col;
    for (let b = 0; b < blobs * (wcm * hcm) / 26000; b++) {
      let x = Math.floor(rnd() * c.width / cell), y = Math.floor(rnd() * c.height / cell);
      for (let k = 0; k < size * 6; k++) {
        ctx.fillRect(x * cell, y * cell, cell, cell);
        x += Math.floor(rnd() * 3) - 1; y += Math.floor(rnd() * 3) - 1;
      }
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

mats.forEach((m, i) => {
  const w = m.x[1] - m.x[0], d = m.y[1] - m.y[0];
  const long = Math.max(w, d), short = Math.min(w, d);
  // build it long-side-along-X so the camo texture isn't stretched, then turn it if needed
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(long, 0.4, short),
    mat('#ffffff', { map: camoTexture(long, short, 1234 + i * 97), roughness: 0.9 }));
  if (d > w) mesh.rotation.y = Math.PI / 2;
  mesh.position.copy(W((m.x[0] + m.x[1]) / 2, (m.y[0] + m.y[1]) / 2, 0.2));
  mesh.receiveShadow = true;
  scene.add(mesh);
});

function floorRect(r, color, opacity, h = 0.45) {
  const w = r.x[1] - r.x[0], d = r.y[1] - r.y[0];
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
  m.rotation.x = -Math.PI / 2;
  m.position.copy(W((r.x[0] + r.x[1]) / 2, (r.y[0] + r.y[1]) / 2, h));
  scene.add(m);
  return m;
}
const labels = new THREE.Group();
scene.add(labels);
if (course.start_zone) {
  floorRect(course.start_zone, '#2fd16f', 0.5);
  labels.add(label('START', W(course.start_zone.x[0] + 4, course.start_zone.y[1] + 22, 4), 9, { bar: '#2fd16f' }));
}
if (course.pilot_station && !LIGHT) {
  floorRect(course.pilot_station, '#2f6fe0', 0.45, 0.1);
  const ps = course.pilot_station;
  labels.add(label('PILOT STATION', W((ps.x[0] + ps.x[1]) / 2, (ps.y[0] + ps.y[1]) / 2, 6), 9, { bar: '#2f6fe0' }));
}
// safety net / flight zone outline
if (!LIGHT) {
  const z = course.flight_zone;
  const pts = [[z.x[0], z.y[0]], [z.x[1], z.y[0]], [z.x[1], z.y[1]], [z.x[0], z.y[1]], [z.x[0], z.y[0]]].map(([x, y]) => W(x, y, 0.3));
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineDashedMaterial({ color: '#56657a', dashSize: 14, gapSize: 10 }));
  line.computeLineDistances();
  scene.add(line);
}

// ------------------------------------------------------------------ field elements
const ARROW_MAT = new THREE.MeshBasicMaterial({ color: '#ff4040', transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false });
function chevron(size = 12) {
  const s = new THREE.Shape();
  s.moveTo(-size, -size * 0.2); s.lineTo(0, size * 0.55); s.lineTo(size, -size * 0.2);
  s.lineTo(size, -size * 0.75); s.lineTo(0, 0); s.lineTo(-size, -size * 0.75); s.closePath();
  return new THREE.ShapeGeometry(s);
}
const arrows = new THREE.Group();
scene.add(arrows);
function addArrows(pos, dir3, count = 3, gap = 16) {
  // chevrons lying flat, pointing along dir3 (three.js vector), ending just before pos
  const yaw = Math.atan2(-dir3.x, -dir3.z);
  for (let i = 0; i < count; i++) {
    const m = new THREE.Mesh(chevron(), ARROW_MAT);
    m.rotation.set(-Math.PI / 2, 0, 0);
    const g = new THREE.Group();
    g.add(m);
    g.rotation.y = yaw;
    g.position.copy(pos).addScaledVector(dir3, -(count - i) * gap - 10);
    arrows.add(g);
  }
}

function buildArch(el) {
  const band = el.outer_h - el.inner_h;
  const ai = el.inner_w / 2, bi = el.inner_h, ao = ai + band, bo = el.outer_h;
  const shape = new THREE.Shape();
  shape.moveTo(ao, 0);
  shape.absellipse(0, 0, ao, bo, 0, Math.PI, false);
  shape.lineTo(-ai, 0);
  shape.absellipse(0, 0, ai, bi, Math.PI, 0, true);
  shape.lineTo(ao, 0);
  const geo = new THREE.ExtrudeGeometry(shape, { depth: 4, bevelEnabled: false, curveSegments: 72 });
  geo.translate(0, 0, -2);
  const g = new THREE.Group();
  const body = new THREE.Mesh(geo, mat(el.color, { roughness: 0.7, side: THREE.DoubleSide }));
  g.add(body);
  // dark piping on both edges + white stripes, like the real arches
  for (const [a, b, r, m] of [[ao, bo, 1.6, BLACK], [ai, bi, 1.6, BLACK], [ai + band * 0.3, bi + band * 0.3, 0.5, mat('#ffffff')], [ai + band * 0.38, bi + band * 0.38, 0.5, mat('#ffffff')]]) {
    const curve = new THREE.EllipseCurve(0, 0, a, b, 0, Math.PI, false);
    const pts = curve.getPoints(90).map((p) => new THREE.Vector3(p.x, p.y, m === BLACK ? 0 : 2.2));
    g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 160, r, 6), m));
  }
  // feet + tension wire
  for (const sgn of [-1, 1]) {
    const u = sgn * (ai + band / 2);
    for (const rot of [Math.PI / 4, -Math.PI / 4]) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(62, 2.2, 3), METAL);
      bar.position.set(u, 1.1, 0);
      bar.rotation.y = rot;
      g.add(bar);
    }
  }
  const wire = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-el.outer_w / 2, 1.5, 0), new THREE.Vector3(el.outer_w / 2, 1.5, 0)]),
    new THREE.LineBasicMaterial({ color: '#9aa4b1' }));
  g.add(wire);
  g.applyMatrix4(gateBasis(el.facing));
  g.position.copy(W(el.center[0], el.center[1], 0));
  body.userData.el = el;
  pickables.push(body);
  scene.add(shadowed(g));
  const [fx, fy] = el.facing;
  addArrows(W(el.center[0], el.center[1], 80), new THREE.Vector3(fx, 0, -fy).normalize());
  return { top: W(el.center[0], el.center[1], el.outer_h + 16) };
}

const polesDrawn = new Set();
function buildKeyhole(el) {
  const ri = el.inner_d / 2, ro = el.outer_d / 2, cz = el.center[2];
  const shape = new THREE.Shape();
  shape.absarc(0, 0, ro, 0, Math.PI * 2, false);
  const hole = new THREE.Path();
  hole.absarc(0, 0, ri, 0, Math.PI * 2, true);
  shape.holes.push(hole);
  const geo = new THREE.ExtrudeGeometry(shape, { depth: 3, bevelEnabled: false, curveSegments: 64 });
  geo.translate(0, 0, -1.5);
  const ring = new THREE.Group();
  const body = new THREE.Mesh(geo, mat(el.color, { roughness: 0.55 }));
  ring.add(body);
  const rim = el.accent ? mat(el.accent, { roughness: 0.5, emissive: el.accent, emissiveIntensity: 0.15 }) : BLACK;
  for (const r of [ro, ri]) ring.add(new THREE.Mesh(new THREE.TorusGeometry(r, el.accent ? 0.7 : 1.1, 8, 72), el.accent && r === ri ? BLACK : rim));
  ring.applyMatrix4(gateBasis(el.facing));
  ring.position.copy(W(el.center[0], el.center[1], cz));
  scene.add(shadowed(ring));
  const [px, py] = el.pole || [el.center[0], el.center[1]];
  const top = el.pole_top ?? cz - ro;
  const key = `${px},${py}`;
  if (!polesDrawn.has(key)) {
    polesDrawn.add(key);
    const base = W(px, py, 0);
    scene.add(shadowed(rod(base, W(px, py, top), 1.5, METAL)));
    scene.add(shadowed(tripod(base)));
  }
  if (el.pole) {  // T-bracket from the pole to the edge of the ring
    const c = W(el.center[0], el.center[1], cz), p = W(px, py, cz);
    const dir = c.clone().sub(p).normalize();
    scene.add(shadowed(rod(p, c.clone().addScaledVector(dir, -ro + 0.5), 1.1, METAL)));
  }
  body.userData.el = el;
  pickables.push(body);
  const [fx, fy] = el.facing;
  addArrows(W(el.center[0], el.center[1], cz), new THREE.Vector3(fx, 0, -fy).normalize(), el.pole ? 2 : 3, el.pole ? 12 : 16);
  return { top: W(el.center[0], el.center[1], cz + ro + 12) };
}

function buildCube(el) {
  const h = el.size / 2, H = el.height, rh = el.hole_d / 2;
  const g = new THREE.Group();
  const frame = mat('#17191e', { roughness: 0.55 });
  const accent = mat(el.color, { roughness: 0.5 });
  for (const n of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    const s = new THREE.Shape();
    s.moveTo(-h, 0); s.lineTo(h, 0); s.lineTo(h, H); s.lineTo(-h, H); s.closePath();
    const hole = new THREE.Path();
    hole.absarc(0, H / 2, rh, 0, Math.PI * 2, true);
    s.holes.push(hole);
    const geo = new THREE.ExtrudeGeometry(s, { depth: 2.5, bevelEnabled: false, curveSegments: 48 });
    geo.translate(0, 0, -1.25);
    const face = new THREE.Group();
    const wall = new THREE.Mesh(geo, frame);
    wall.userData.el = el;
    pickables.push(wall);
    face.add(wall);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(rh + 2.2, 1.6, 8, 48), accent);
    rim.position.set(0, H / 2, 1.6);
    face.add(rim);
    face.applyMatrix4(gateBasis(n));
    face.position.copy(W(n[0] * h, n[1] * h, 0));
    g.add(face);
  }
  const top = new THREE.Mesh(new THREE.BoxGeometry(2 * h + 2.5, 2, 2 * h + 2.5), frame);
  top.position.y = H;
  top.userData.el = el;
  pickables.push(top);
  g.add(top);
  const edge = new THREE.Mesh(new THREE.BoxGeometry(2 * h - 8, 2.2, 2 * h - 8), accent);
  edge.position.y = H + 0.2;
  g.add(edge);
  const inner = new THREE.Mesh(new THREE.BoxGeometry(2 * h - 12, 2.4, 2 * h - 12), frame);
  inner.position.y = H + 0.3;
  g.add(inner);
  g.position.copy(W(el.center[0], el.center[1], 0));
  scene.add(shadowed(g));
  return { top: W(el.center[0], el.center[1], H + 20) };
}

function stripeTexture() {
  const c = document.createElement('canvas');
  c.width = 1024; c.height = 64;
  const ctx = c.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 64);
  grad.addColorStop(0, '#0e0f12'); grad.addColorStop(1, '#23262c');
  ctx.fillStyle = grad; ctx.fillRect(0, 0, 1024, 64);
  let s = 7;
  for (let i = 0; i < 220; i++) {
    s = (s * 16807) % 2147483647;
    const x = (s / 2147483647) * 1024;
    const a = 0.08 + ((s >> 3) % 100) / 300;
    ctx.fillStyle = `rgba(230,235,245,${a})`;
    ctx.fillRect(x, 0, 1 + ((s >> 5) % 4), 64);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = THREE.RepeatWrapping;
  return t;
}

function buildTunnel(el) {
  const R = el.diameter / 2, zb = el.bottom, zt = el.bottom + el.length, zm = (zb + zt) / 2;
  const [cx, cy] = el.center;
  const [ox, oy] = el.stand_offset || [45, 0];
  const g = new THREE.Group();
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(R, R, el.length, 64, 1, true),
    mat('#ffffff', { map: stripeTexture(), side: THREE.DoubleSide, roughness: 0.8 }));
  tube.position.copy(W(cx, cy, zm));
  tube.userData.el = el;
  pickables.push(tube);
  g.add(tube);
  for (const z of [zb, zt]) {
    const rim = new THREE.Mesh(new THREE.TorusGeometry(R, 1.2, 8, 72), BLACK);
    rim.rotation.x = Math.PI / 2;
    rim.position.copy(W(cx, cy, z));
    g.add(rim);
  }
  const n = Math.hypot(ox, oy);
  const pole = W(cx + ox, cy + oy, 0);
  g.add(rod(pole, W(cx + ox, cy + oy, zm), 1.5, METAL));
  g.add(rod(W(cx + ox / n * R, cy + oy / n * R, zm), W(cx + ox, cy + oy, zm), 1.2, METAL));
  g.add(tripod(pole));
  scene.add(shadowed(g));
  addArrowsDown(W(cx, cy, zt + 26));
  return { top: W(cx, cy, zt + 44) };
}

function addArrowsDown(pos) {
  for (let i = 0; i < 2; i++) {
    const m = new THREE.Mesh(chevron(11), ARROW_MAT);
    m.rotation.set(0, 0, Math.PI);           // point down
    m.position.copy(pos).add(new THREE.Vector3(0, i * 14, 0));
    const m2 = m.clone();
    m2.rotation.set(0, Math.PI / 2, Math.PI);
    arrows.add(m, m2);
  }
}

function padTexture(R, Rb) {
  const c = document.createElement('canvas');
  const S = 1024; c.width = c.height = S;
  const ctx = c.getContext('2d');
  const k = (S / 2) / R;
  ctx.translate(S / 2, S / 2);
  ctx.fillStyle = '#101216'; ctx.beginPath(); ctx.arc(0, 0, R * k, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#e0224a'; ctx.lineWidth = 2.6 * k; ctx.beginPath(); ctx.arc(0, 0, (R - 1.6) * k, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = 1.2 * k; ctx.beginPath(); ctx.arc(0, 0, Rb * k, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = 'rgba(224,34,74,0.18)'; ctx.beginPath(); ctx.arc(0, 0, Rb * k, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#e0224a';
  ctx.font = `800 ${3.4 * k}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText('AERIAL DRONE', 0, -(Rb + 5) * k);
  ctx.font = `600 ${2.6 * k}px system-ui, sans-serif`;
  ctx.fillText('COMPETITION', 0, (Rb + 8) * k);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function buildPad(el) {
  const R = el.diameter / 2, Rb = el.bullseye_d / 2;
  const m = new THREE.Mesh(new THREE.CircleGeometry(R, 72), mat('#ffffff', { map: padTexture(R, Rb), roughness: 0.7 }));
  m.rotation.x = -Math.PI / 2;
  m.rotation.z = Math.PI / 2;
  m.position.copy(W(el.center[0], el.center[1], 0.7));
  m.receiveShadow = true;
  m.userData.el = el;
  pickables.push(m);
  scene.add(m);
  return { top: W(el.center[0] - R - 6, el.center[1], 16) };
}

const taskPts = Object.fromEntries(course.tasks.map((t) => [t.id, t]));
const elementTops = {};
for (const el of course.elements) {
  const b = { arch: buildArch, keyhole: buildKeyhole, cube: buildCube, tunnel: buildTunnel, landing_pad: buildPad }[el.type];
  if (!b) continue;
  const info = b(el);
  elementTops[el.id] = info.top;
  const t = taskPts[el.id];
  let sub = t ? `${t.points} PTS${t.bonus ? ' · BONUS' : ''}` : '';
  if (el.type === 'landing_pad') sub = '5 · BULLSEYE 15';
  if (el.id === 'small_cube' || (el.type === 'cube' && !t)) sub = 'LAND 10';
  labels.add(label((el.short || el.label).toUpperCase(), info.top, 10.5, { bar: el.accent || el.color, sub }));
}

// ------------------------------------------------------------------ drones
const PROP_BLADE = new THREE.BoxGeometry(5.8, 0.14, 0.7);
const glowTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.25, 'rgba(255,255,255,0.45)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
})();

function makeDrone(run) {
  const color = new THREE.Color(run ? run.color : '#ffd166');
  const root = new THREE.Group();          // position + yaw
  const body = new THREE.Group();          // tilt
  body.rotation.order = 'YZX';
  root.add(body);
  const shell = new THREE.Mesh(new THREE.BoxGeometry(6.4, 2.4, 5.2), mat('#1b1f25', { roughness: 0.4 }));
  shell.position.y = 2.2;
  body.add(shell);
  const lid = new THREE.Mesh(new THREE.BoxGeometry(5, 0.8, 4), mat('#2a3039', { roughness: 0.3, metalness: 0.2 }));
  lid.position.y = 3.6;
  body.add(lid);
  const nose = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.0, 2.4), new THREE.MeshBasicMaterial({ color: '#ffffff' }));
  nose.position.set(3.6, 2.4, 0);
  body.add(nose);
  const ledMat = new THREE.MeshBasicMaterial({ color: '#ff2020' });
  const led = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.5, 3.2), ledMat);
  led.position.y = 0.85;
  body.add(led);
  const armMat = mat('#20252c', { roughness: 0.5 });
  const guardMat = mat(color, { roughness: 0.45 });
  const discMat = new THREE.MeshBasicMaterial({ color: '#d9e2ee', transparent: true, opacity: 0.16, depthWrite: false, side: THREE.DoubleSide });
  const props = [];
  for (const [sx, sz, dir] of [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) {
    const x = sx * 4.5, z = sz * 4.5;
    const arm = new THREE.Mesh(new THREE.BoxGeometry(6.4, 0.9, 1.1), armMat);
    arm.position.set(x / 2, 2, z / 2);
    arm.rotation.y = Math.atan2(-z, x);
    body.add(arm);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 1.6, 12), armMat);
    hub.position.set(x, 2.4, z);
    body.add(hub);
    const guard = new THREE.Mesh(new THREE.TorusGeometry(3.25, 0.32, 6, 32), guardMat);
    guard.rotation.x = Math.PI / 2;
    guard.position.set(x, 2.6, z);
    body.add(guard);
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.5, 1.6, 0.5), armMat);
    leg.position.set(x * 0.95, 0.8, z * 0.95);
    body.add(leg);
    const prop = new THREE.Group();
    prop.position.set(x, 3.4, z);
    prop.add(new THREE.Mesh(PROP_BLADE, mat('#e6ebf2', { roughness: 0.4 })));
    const disc = new THREE.Mesh(new THREE.CircleGeometry(2.95, 24), discMat);
    disc.rotation.x = -Math.PI / 2;
    disc.visible = false;
    prop.add(disc);
    prop.userData = { dir, disc };
    body.add(prop);
    props.push(prop);
  }
  shadowed(body);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: '#ff2020', transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.8 }));
  glow.scale.set(26, 26, 1);
  glow.position.y = 0.6;
  root.add(glow);
  scene.add(root);

  // height stick + ground ring make the height readable from far away
  const stickGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
  const stick = new THREE.Line(stickGeo, new THREE.LineDashedMaterial({ color, transparent: true, opacity: 0.55, dashSize: 4, gapSize: 3 }));
  scene.add(stick);
  const ring = new THREE.Mesh(new THREE.RingGeometry(4.2, 5.4, 32), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7, depthWrite: false, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2;
  scene.add(ring);

  let tag = null;
  if (run) {
    tag = label(run.name, new THREE.Vector3(), 8, { bar: run.color, size: 24, weight: 600 });
    scene.add(tag);
  }

  // trail
  let trail = null;
  if (run && run.frames.length) {
    const arr = new Float32Array(run.frames.length * 3);
    run.frames.forEach((f, i) => { arr[i * 3] = f[1]; arr[i * 3 + 1] = f[3] + 2.5; arr[i * 3 + 2] = -f[2]; });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(arr, 3));
    trail = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 }));
    trail.frustumCulled = false;
    scene.add(trail);
  }
  return { root, body, props, ledMat, glow, stick, ring, tag, trail, guardMat };
}

const startPose = [0, course.start.x, course.start.y, 0, course.start.yaw, 0, 0, 0];
function frameIndex(F, t) {
  let lo = 0, hi = F.length - 1;
  if (hi < 0 || t <= F[0][0]) return 0;
  if (t >= F[hi][0]) return hi;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (F[m][0] <= t) lo = m; else hi = m; }
  return lo;
}
function poseAt(run, t) {
  const F = run ? run.frames : [];
  if (!F.length) return { p: startPose, i: 0 };
  const i = frameIndex(F, t);
  const a = F[i], b = F[Math.min(i + 1, F.length - 1)];
  const k = b[0] > a[0] ? Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0]))) : 0;
  const lerp = (u, v) => u + (v - u) * k;
  let dyaw = b[4] - a[4];
  dyaw = ((dyaw + 540) % 360) - 180;
  return { p: [t, lerp(a[1], b[1]), lerp(a[2], b[2]), lerp(a[3], b[3]), a[4] + dyaw * k, lerp(a[5], b[5]), lerp(a[6], b[6]), a[7]], i };
}
function surfaceAt(x, y) {
  for (const el of course.elements) {
    if (el.type === 'cube' && Math.abs(x - el.center[0]) < el.size / 2 + 2 && Math.abs(y - el.center[1]) < el.size / 2 + 2) return el.height;
  }
  return 0;
}
function ledAt(run, t) {
  let c = [255, 32, 32];
  for (const l of run?.leds || []) { if (l.t <= t) c = l.rgb; else break; }
  return c;
}

const drones = EXPLORE ? [makeDrone(null)] : runs.map(makeDrone);

// ------------------------------------------------------------------ state
const state = {
  t: 0, playing: false, speed: 1, cam: 'broadcast', focus: ranked[0]?.idx ?? 0,
  race: runs.length > 1, labels: true, sound: true, lastT: 0, bannerFor: null,
  follow: true,
};
const saved = store.get('ftj-view');
if (saved && P.get('watch')) Object.assign(state, { cam: saved.cam, speed: saved.speed, labels: saved.labels, sound: saved.sound });
const focusRun = () => runs[state.focus];

// ------------------------------------------------------------------ audio
let actx = null;
function audio() {
  if (!state.sound) return null;
  try {
    actx = actx || new (window.AudioContext || window.webkitAudioContext)();
    if (actx.state === 'suspended') actx.resume();
  } catch { return null; }
  return actx;
}
function tone(hz, ms, type = 'sine', vol = 0.06, when = 0) {
  const a = audio(); if (!a) return;
  const o = a.createOscillator(), g = a.createGain();
  o.type = type; o.frequency.value = hz;
  const t0 = a.currentTime + when;
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(vol, t0 + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + ms / 1000);
  o.connect(g).connect(a.destination);
  o.start(t0); o.stop(t0 + ms / 1000 + 0.05);
}
function ding(points) { tone(880, 180, 'triangle', 0.08); tone(points >= 15 ? 1568 : 1319, 260, 'triangle', 0.07, 0.09); }
function crashSound() {
  const a = audio(); if (!a) return;
  const len = a.sampleRate * 0.5, buf = a.createBuffer(1, len, a.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.5);
  const s = a.createBufferSource(), g = a.createGain();
  s.buffer = buf; g.gain.value = 0.25;
  s.connect(g).connect(a.destination); s.start();
}

// ------------------------------------------------------------------ UI: code panel
const TOKENS = /(#.*$)|("(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?)|\b(and|as|break|class|continue|def|elif|else|except|False|finally|for|from|if|import|in|is|lambda|None|not|or|pass|return|True|try|while|with)\b|\b(\d+(?:\.\d+)?)\b|\b(drone|print|range)\b|\.([A-Za-z_]\w*)(?=\s*\()/g;
function highlight(line) {
  let out = '', last = 0, m;
  const span = (cls, txt) => `<span class="tok-${cls}">${esc(txt)}</span>`;
  TOKENS.lastIndex = 0;
  while ((m = TOKENS.exec(line))) {
    out += esc(line.slice(last, m.index));
    if (m[1]) out += span('com', m[1]);
    else if (m[2]) out += span('str', m[2]);
    else if (m[3]) out += span('kw', m[3]);
    else if (m[4]) out += span('num', m[4]);
    else if (m[5]) out += span(m[5] === 'drone' ? 'self' : 'fn', m[5]);
    else if (m[6]) out += '.' + span('fn', m[6]);
    last = TOKENS.lastIndex;
    if (m[0] === '') TOKENS.lastIndex++;
  }
  return (out + esc(line.slice(last))) || ' ';
}

// A line inside a helper function (called from several places) credits its caller instead.
function helperLines(run) {
  const outers = {};
  for (const c of run?.calls || []) if (c.line && c.outer?.length) (outers[c.line] ||= new Set()).add(c.outer[0]);
  return new Set(Object.keys(outers).filter((k) => outers[k].size > 1).map(Number));
}
function creditLine(run, ev) {
  if (!ev?.line) return null;
  if (ev.outer?.length && run._helpers?.has(ev.line)) return ev.outer[0];
  return ev.line;
}

let codeLines = [];
function renderCode(run) {
  const box = $('code');
  box.innerHTML = '';
  codeLines = [];
  if (run) run._helpers = helperLines(run);
  const src = (run?.source || '').replace(/\s+$/, '').split('\n');
  $('fileName').textContent = run?.mission_file || '';
  src.forEach((s, i) => {
    const d = document.createElement('div');
    d.className = 'ln';
    d.innerHTML = `<span class="no">${i + 1}</span><span class="src">${highlight(s)}</span><span class="chips"></span>`;
    box.appendChild(d);
    codeLines.push(d);
  });
  if (run?.error?.line && codeLines[run.error.line - 1]) codeLines[run.error.line - 1].classList.add('err');
  codeState.active = -1; codeState.chipsKey = ''; codeState.outerKey = '';
}
const codeState = { active: -1, chipsKey: '', outerKey: '' };

function updateCode(run, t) {
  if (!run) return;
  let line = -1;
  const C = run.calls;
  let lo = 0, hi = C.length - 1, found = null;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (C[m].t0 <= t) { found = C[m]; lo = m + 1; } else hi = m - 1; }
  let outer = [];
  if (found && (t < found.t1 || t - found.t1 < 0.05) && found.line) { line = found.line; outer = found.outer || []; }
  const outerKey = outer.join(',');
  if (outerKey !== codeState.outerKey) {
    for (const d of codeLines) d.classList.remove('outer');
    for (const n of outer) codeLines[n - 1]?.classList.add('outer');
    codeState.outerKey = outerKey;
  }
  const crashed = run.crash && t >= run.crash.t;
  const errored = run.error && t >= (run.events.find((e) => e.type === 'error')?.t ?? 0);
  if (line !== codeState.active) {
    if (codeState.active > 0) codeLines[codeState.active - 1]?.classList.remove('active');
    if (line > 0 && codeLines[line - 1]) {
      codeLines[line - 1].classList.add('active');
      const box = $('code'), el = codeLines[line - 1];
      const top = el.offsetTop - box.clientHeight * 0.35;
      if (el.offsetTop < box.scrollTop + 20 || el.offsetTop > box.scrollTop + box.clientHeight - 40) box.scrollTo({ top, behavior: 'smooth' });
    }
    codeState.active = line;
    toParent({ type: 'line', line, outer });
  }
  // chips: points earned by each line, crash / error markers
  const evs = run.events.filter((e) => e.t <= t && e.line && (e.type === 'score' || e.type === 'crash' || e.type === 'error'));
  const key = evs.length + ':' + (crashed ? 1 : 0) + (errored ? 1 : 0);
  if (key === codeState.chipsKey) return;
  codeState.chipsKey = key;
  toParent({ type: 'marks', marks: evs.map((e) => ({ line: creditLine(run, e), text: e.type === 'score' ? `+${e.points}` : (e.type === 'crash' ? 'CRASH' : 'ERROR'), bad: e.type !== 'score' })) });
  codeLines.forEach((d) => { d.querySelector('.chips').innerHTML = ''; d.classList.remove('crash'); });
  for (const e of evs) {
    const d = codeLines[creditLine(run, e) - 1];
    if (!d) continue;
    const chip = document.createElement('span');
    chip.className = 'chip' + (e.type === 'score' ? '' : ' bad');
    chip.textContent = e.type === 'score' ? `+${e.points}` : (e.type === 'crash' ? 'CRASH' : 'ERROR');
    d.querySelector('.chips').appendChild(chip);
    if (e.type === 'crash') d.classList.add('crash');
  }
}

function updateConsole(run, t) {
  const box = $('console');
  const rows = (run?.console || []).filter((c) => c.t <= t);
  if (box.dataset.n === String(rows.length)) return;
  box.dataset.n = rows.length;
  box.innerHTML = rows.length ? rows.map((c) => `<div class="row"><span class="t">${mmss(c.t)}</span><span>${esc(c.text)}</span></div>`).join('')
    : '<div class="empty">Nothing printed yet.</div>';
  box.scrollTop = box.scrollHeight;
}

// ------------------------------------------------------------------ UI: scorecard / feed / board
function renderCard() {
  const ul = $('card');
  ul.innerHTML = '';
  let sep = false;
  for (const task of course.tasks) {
    if (task.group === 'landing' && !sep) {
      sep = true;
      const s = document.createElement('li'); s.className = 'sep'; s.textContent = 'Final landing (pick one)'; ul.appendChild(s);
    }
    const li = document.createElement('li');
    li.dataset.task = task.id;
    li.innerHTML = `<span class="tick">✓</span><span>${esc(task.label)}${task.bonus ? '<span class="bonus">BONUS</span>' : ''}</span><span class="pts">${task.points}</span>`;
    ul.appendChild(li);
  }
  const tot = document.createElement('li');
  tot.className = 'total';
  tot.innerHTML = '<span></span><span>Total</span><span class="pts" id="cardTotal">0</span>';
  ul.appendChild(tot);
}
const cardState = { key: '' };
function updateCard(run, t) {
  const counts = {};
  let total = 0;
  for (const e of run?.events || []) if (e.type === 'score' && e.t <= t) { counts[e.task] = (counts[e.task] || 0) + 1; total += e.points; }
  const key = JSON.stringify(counts);
  if (key === cardState.key) return total;
  const prev = cardState.key ? JSON.parse(cardState.key) : {};
  cardState.key = key;
  for (const li of $('card').querySelectorAll('li[data-task]')) {
    const id = li.dataset.task, n = counts[id] || 0, task = taskPts[id];
    li.classList.toggle('done', n > 0);
    li.querySelector('.pts').textContent = n ? `+${task.points * n}${n > 1 ? ` (${n}×)` : ''}` : task.points;
    if (n > (prev[id] || 0) && state.playing) { li.classList.remove('flash'); void li.offsetWidth; li.classList.add('flash'); }
  }
  $('cardTotal').textContent = total;
  return total;
}

function updateFeed(run, t) {
  const evs = (run?.events || []).filter((e) => e.t <= t && e.text !== 'Touched down.');
  const ul = $('feed');
  if (ul.dataset.n === String(evs.length)) return;
  ul.dataset.n = evs.length;
  ul.innerHTML = evs.map((e) => {
    const body = e.type === 'score'
      ? `<span class="pts">+${e.points}</span>${esc(e.text.replace(/^\+\d+\s+/, ''))}`
      : esc(e.text.replace(/^CRASH! /, 'Crash: '));
    const ln = creditLine(run, e);
    return `<li class="${e.type}"><span class="t">${mmss(e.t)}</span><span>${body}${ln ? `<span class="line-ref">L${ln}</span>` : ''}</span></li>`;
  }).join('') || '<li class="info"><span class="t"></span><span>Waiting for takeoff</span></li>';
  ul.scrollTop = ul.scrollHeight;
}

function statusBadge(r) {
  if (r.crash) return ['Crash', 'bad'];
  if (r.error) return ['Error', 'bad'];
  if (r.result.landing === 'land_bullseye') return ['Bullseye', 'best'];
  if (r.result.landing === 'land_cube') return ['Cube', 'good'];
  if (r.result.landing === 'land_pad') return ['Pad', 'good'];
  if (r.result.status === 'landed') return ['Floor', ''];
  if (r.result.status === 'never took off') return ['No flight', 'warn'];
  return ['Airborne', 'warn'];
}
function renderBoard() {
  if (runs.length < 2) return;
  $('boardWrap').hidden = false;
  $('race').checked = state.race;
  $('board').innerHTML = ranked.map((r, i) => `<li data-idx="${r.idx}"><span class="rk">${i + 1}</span><span class="sw" style="background:${r.color}"></span>
    <span class="nm">${esc(r.name)}${r.meta.pr ? `<small>PR #${esc(r.meta.pr)} · ${mmss(r.result.finish_time)}</small>` : `<small>${mmss(r.result.finish_time)}</small>`}</span>
    <span class="badge ${statusBadge(r)[1]}">${statusBadge(r)[0]}</span><span class="sc">${r.result.score}</span></li>`).join('');
  for (const li of $('board').children) li.addEventListener('click', () => setFocus(+li.dataset.idx));
  $('race').addEventListener('change', (e) => { state.race = e.target.checked; applyVisibility(); });
}

function setFocus(idx) {
  state.focus = idx;
  const run = focusRun();
  for (const li of $('board').children) li.classList.toggle('focus', +li.dataset.idx === idx);
  $('pilotName').textContent = run.name;
  $('pilotDot').style.background = run.color;
  $('pilotDot').style.color = run.color;
  const m = run.meta || {};
  const bits = [];
  if (m.pr) bits.push(m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">PR #${esc(m.pr)}</a>` : `PR #${esc(m.pr)}`);
  if (m.title) bits.push(esc(m.title));
  bits.push(esc(run.mission_file || ''));
  if (run.realistic) bits.push('realistic mode');
  $('pilotMeta').innerHTML = bits.filter(Boolean).join(' · ');
  renderCode(run);
  cardState.key = '';
  $('feed').dataset.n = '';
  $('console').dataset.n = '';
  renderTimelineMarks();
  applyVisibility();
  state.bannerFor = null;
  $('banner').hidden = true;
}

function applyVisibility() {
  drones.forEach((d, i) => {
    const show = EXPLORE || state.race || i === state.focus;
    const focus = i === state.focus;
    for (const o of [d.root, d.stick, d.ring]) o.visible = show;
    if (d.trail) { d.trail.visible = show; d.trail.material.opacity = focus ? 0.9 : 0.35; }
    if (d.tag) d.tag.visible = show && state.race && runs.length > 1;
  });
}

// ------------------------------------------------------------------ timeline
function renderTimelineMarks() {
  const run = focusRun();
  const box = $('tlMarks');
  box.innerHTML = '';
  if (!run || !DURATION) return;
  const add = (t, cls) => { const d = document.createElement('div'); d.className = 'mk ' + cls; d.style.left = `${(t / DURATION) * 100}%`; box.appendChild(d); };
  for (const e of run.events) if (['score', 'crash', 'error', 'warn'].includes(e.type)) add(e.t, e.type);
  if (LIMIT < DURATION) add(LIMIT, 'limit');
  $('tEnd').textContent = mmss(DURATION);
}
function seek(t) {
  state.t = Math.max(0, Math.min(DURATION, t));
  state.lastT = state.t;
  if (state.t < (state.bannerAt ?? Infinity)) { $('banner').hidden = true; state.bannerFor = null; }
}
{
  const tl = $('timeline');
  let drag = false;
  const at = (e) => { const r = tl.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * DURATION); };
  tl.addEventListener('pointerdown', (e) => { drag = true; tl.setPointerCapture(e.pointerId); at(e); });
  tl.addEventListener('pointermove', (e) => { if (drag) at(e); });
  tl.addEventListener('pointerup', () => { drag = false; });
}

// ------------------------------------------------------------------ toasts / banners
function toast(html, cls = '') {
  const d = document.createElement('div');
  d.className = 'toast ' + cls;
  d.innerHTML = html;
  $('toasts').appendChild(d);
  setTimeout(() => d.remove(), 2500);
  while ($('toasts').children.length > 3) $('toasts').firstChild.remove();
}
function banner(run) {
  const b = $('banner');
  const r = run.result;
  let kind = 'good', kicker = 'Run complete', title, why = '';
  if (run.crash) {
    kind = 'crash'; kicker = 'Run ended · crash';
    title = `Hit the ${run.crash.what.replace(/^the /, '')}`;
    const ln = creditLine(run, run.crash);
    const src = (run.source || '').split('\n')[ln - 1];
    if (ln) why = `Line ${ln} · <span class="mono">${esc((src || '').trim())}</span>`;
  } else if (run.error) {
    kind = 'crash'; kicker = 'Run ended · error in code';
    title = `${esc(run.error.type)}${run.error.line ? ` on line ${run.error.line}` : ''}`;
    why = esc(run.error.message);
  } else if (r.landing === 'land_bullseye') {
    kind = 'best'; title = 'Landed on the bullseye';
  } else if (r.status === 'landed') {
    title = { land_pad: 'Landed on the landing pad', land_cube: 'Landed on a cube' }[r.landing] || 'Landed on the floor';
    if (!r.landing) { kind = 'neutral'; why = 'No landing points'; }
  } else {
    kind = 'neutral'; kicker = 'Program ended'; title = `Drone ${esc(r.status)}`;
  }
  const tasks = (r.scores || []).length;
  if (!why) why = `${tasks} scoring task${tasks === 1 ? '' : 's'} · ${esc(run.name)}`;
  b.className = kind;
  b.innerHTML = `<div class="bar"></div><div class="body"><div class="kicker">${kicker}</div><div class="title">${title}</div><div class="why">${why}</div></div>
    <div class="nums"><div class="num"><b>${r.score}</b><span>Points</span></div><div class="num"><b>${mmss(r.finish_time)}</b><span>Time</span></div></div>`;
  b.hidden = false;
}

function fireEvents(t0, t1) {
  const run = focusRun();
  if (!run || t1 <= t0) return;
  for (const e of run.events) {
    if (e.t <= t0 || e.t > t1) continue;
    if (e.type === 'score') { toast(`<span class="p">+${e.points}</span>${esc(e.text.replace(/^\+\d+\s+/, ''))}`); ding(e.points); bumpScore(); }
    else if (e.type === 'crash') { toast(`<span class="p">CRASH</span>${esc(e.text.replace(/^CRASH! /, ''))}`, 'crash'); crashSound(); }
    else if (e.type === 'warn') toast(esc(e.text), 'warn');
    else if (e.type === 'error') toast(`<span class="p">ERROR</span>${esc(e.text)}`, 'crash');
  }
  for (const s of run.sounds || []) if (s.t > t0 && s.t <= t1) tone(s.hz, Math.min(s.ms, 1500), 'square', 0.035);
  const endT = run.crash ? run.crash.t + 1.2 : (run.result.finish_time || 0) + 0.8;
  if (t0 < endT && t1 >= endT && state.bannerFor !== run.idx) { state.bannerFor = run.idx; state.bannerAt = endT; banner(run); }
}
function bumpScore() { const s = $('score'); s.classList.remove('bump'); void s.offsetWidth; s.classList.add('bump'); }

// ------------------------------------------------------------------ cameras
let bcast = store.get('ftj-cam') && P.get('watch') ? store.get('ftj-cam') : null;
camera.position.copy(bcast ? new THREE.Vector3(...bcast.pos) : HOME_CAM.pos);
controls.target.copy(bcast ? new THREE.Vector3(...bcast.target) : HOME_CAM.target);
const chase = { pos: new THREE.Vector3(), look: new THREE.Vector3(), dir: new THREE.Vector3(1, 0, 0), init: false };
let fly = null; // camera tween

function setCam(mode) {
  if (state.cam === 'broadcast' || state.cam === 'top') bcast = { pos: camera.position.toArray(), target: controls.target.toArray(), mode: state.cam };
  state.cam = mode;
  for (const b of $('cams').children) b.classList.toggle('on', b.dataset.cam === mode);
  controls.enabled = mode === 'broadcast' || mode === 'top';
  camera.fov = mode === 'fpv' ? 78 : 42;
  camera.updateProjectionMatrix();
  chase.init = false;
  if (mode === 'top') flyTo(FIELD_C.clone().setY(760).add(new THREE.Vector3(0, 0, 1)), FIELD_C.clone().setY(0));
  if (mode === 'broadcast') flyTo(HOME_CAM.pos, HOME_CAM.target);
}
function flyTo(pos, target, dur = 0.9) {
  fly = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos.clone(), t1: target.clone(), k: 0, dur };
}

function updateCamera(dt, pose) {
  const [, x, y, z, yaw] = pose;
  const drone = W(x, y, z + 3);
  if (fly) {
    fly.k = Math.min(1, fly.k + dt / fly.dur);
    const e = 1 - Math.pow(1 - fly.k, 3);
    camera.position.lerpVectors(fly.p0, fly.p1, e);
    controls.target.lerpVectors(fly.t0, fly.t1, e);
    if (fly.k >= 1) fly = null;
    controls.update();
    return;
  }
  if (state.cam === 'broadcast' || state.cam === 'top') {
    if (state.cam === 'broadcast' && state.follow && state.playing && !EXPLORE) {
      const want = drone.clone().multiplyScalar(0.55).add(HOME_CAM.target.clone().multiplyScalar(0.45));
      const delta = want.sub(controls.target).multiplyScalar(Math.min(1, dt * 1.2));
      controls.target.add(delta);
      camera.position.add(delta);
    }
    controls.update();
    return;
  }
  const yr = THREE.MathUtils.degToRad(yaw);
  const fwd = new THREE.Vector3(Math.cos(yr), 0, -Math.sin(yr));
  if (state.cam === 'chase') {
    // sit behind the direction of travel (the drone may be strafing sideways), else behind the nose
    const run = focusRun();
    const back = poseAt(run, Math.max(0, state.t - 0.25)).p;
    const vel = new THREE.Vector3(x - back[1], 0, -(y - back[2]));
    const want_dir = vel.length() > 4 ? vel.normalize() : fwd.clone();
    if (!chase.init) chase.dir = want_dir.clone();
    chase.dir.lerp(want_dir, Math.min(1, dt * 2.5)).normalize();
    const want = drone.clone().addScaledVector(chase.dir, -95).add(new THREE.Vector3(0, 48, 0));
    const look = drone.clone().addScaledVector(chase.dir, 50).add(new THREE.Vector3(0, -8, 0));
    if (!chase.init) { chase.pos.copy(want); chase.look.copy(look); chase.init = true; }
    chase.pos.lerp(want, Math.min(1, dt * 3));
    chase.look.lerp(look, Math.min(1, dt * 5));
    camera.position.copy(chase.pos);
    camera.lookAt(chase.look);
  } else if (state.cam === 'fpv') {
    camera.position.copy(drone).addScaledVector(fwd, 7).add(new THREE.Vector3(0, 2, 0));
    camera.lookAt(camera.position.clone().addScaledVector(fwd, 100).add(new THREE.Vector3(0, -14, 0)));
  }
}

// ------------------------------------------------------------------ hover: coordinates + element info
const ray = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
canvas.addEventListener('pointermove', (e) => {
  mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(mouse, camera);
  const tip = $('tooltip');
  const hit = ray.intersectObjects(pickables, false)[0];
  if (hit && (state.cam === 'broadcast' || state.cam === 'top')) {
    const el = hit.object.userData.el;
    const t = taskPts[el.id];
    tip.innerHTML = `<b>${esc(el.label)}${t ? ` · ${t.points} pts${t.bonus ? ' (bonus)' : ''}` : ''}</b><span>${esc(el.hint || '')}</span>`;
    tip.style.left = `${Math.min(e.clientX + 14, innerWidth - 300)}px`;
    tip.style.top = `${e.clientY + 14}px`;
    tip.hidden = false;
  } else tip.hidden = true;
  const p = new THREE.Vector3();
  const c = $('coords');
  if (ray.ray.intersectPlane(floorPlane, p) && (state.cam === 'broadcast' || state.cam === 'top')) {
    const x = Math.round(p.x), y = Math.round(-p.z);
    c.textContent = `x ${x} cm (${x >= 0 ? 'forward' : 'back'})  ·  y ${y} cm (${y >= 0 ? 'left' : 'right'})`;
    c.classList.add('on');
  } else c.classList.remove('on');
});
canvas.addEventListener('pointerleave', () => { $('tooltip').hidden = true; $('coords').classList.remove('on'); });

// ------------------------------------------------------------------ explore mode panel
function renderExplore() {
  $('exploreWrap').hidden = false;
  $('cardWrap').hidden = true;
  $('feedWrap').hidden = true;
  document.body.classList.add('no-code');
  $('pilotMeta').textContent = EMBED ? 'Press Fly to watch your mission here' : 'No flight loaded · python fly.py missions/<you>.py';
  $('clock').textContent = '3:00.0';
  for (const id of ['play', 'restart', 'speeds', 'togCode']) $(id).hidden = true;
  $('timeline').parentElement.style.visibility = 'hidden';
  for (const b of $('cams').children) if (b.dataset.cam === 'chase' || b.dataset.cam === 'fpv') b.hidden = true;
  const ul = $('elements');
  ul.innerHTML = course.elements.map((el) => {
    const t = taskPts[el.id];
    return `<li data-id="${esc(el.id)}"><span class="sw" style="background:${esc(el.accent || el.color)}"></span><div><b>${esc(el.label)}${t ? `<small>${t.points} pts${t.bonus ? ' · bonus' : ''}</small>` : ''}</b><span>${esc(el.hint || '')}</span></div></li>`;
  }).join('');
  for (const li of ul.children) {
    li.addEventListener('click', () => {
      const el = course.elements.find((e) => e.id === li.dataset.id);
      const zc = el.type === 'keyhole' ? el.center[2] : el.type === 'arch' ? 80 : el.type === 'tunnel' ? el.bottom + el.length / 2 : 30;
      const tgt = W(el.center[0], el.center[1], zc);
      const [fx, fy] = el.facing || [1, 0];
      const back = new THREE.Vector3(fx, 0, -fy).normalize().multiplyScalar(-230);
      back.add(new THREE.Vector3(back.z * 0.5, 110, -back.x * 0.5));
      setCam('broadcast');
      flyTo(tgt.clone().add(back), tgt);
    });
  }
}

// ------------------------------------------------------------------ controls wiring
function setPlaying(on) {
  if (EXPLORE) return;
  if (on && state.t >= DURATION - 0.01) seek(0);
  state.playing = on;
  $('playIcon').setAttribute('d', on ? 'M7 5h4v14H7zm6 0h4v14h-4z' : 'M8 5.5v13l11-6.5z');
  $('intro').hidden = true;
  if (on) audio();
}
$('play').addEventListener('click', () => setPlaying(!state.playing));
$('bigPlay').addEventListener('click', (e) => { e.stopPropagation(); setPlaying(true); });
$('intro').addEventListener('click', () => setPlaying(true));
$('restart').addEventListener('click', () => { seek(0); setPlaying(true); });
for (const b of $('speeds').children) b.addEventListener('click', () => setSpeed(+b.dataset.speed));
function setSpeed(s) { state.speed = s; for (const b of $('speeds').children) b.classList.toggle('on', +b.dataset.speed === s); }
for (const b of $('cams').children) b.addEventListener('click', () => setCam(b.dataset.cam));
function setLabels(on) { state.labels = on; labels.visible = on; arrows.visible = on; $('togLabels').classList.toggle('on', on); }
function setSound(on) {
  state.sound = on; $('togSound').classList.toggle('on', on);
  $('soundIcon').setAttribute('d', on ? 'M4 9v6h4l5 4V5L8 9H4zm12.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4z' : 'M4 9v6h4l5 4V5L8 9H4zm15.6 3 2.1-2.1-1.4-1.4-2.1 2.1-2.1-2.1-1.4 1.4 2.1 2.1-2.1 2.1 1.4 1.4 2.1-2.1 2.1 2.1 1.4-1.4z');
}
function setCodePanel(on) { document.body.classList.toggle('no-code', !on); $('togCode').classList.toggle('on', on); }
$('togLabels').addEventListener('click', () => setLabels(!state.labels));
$('togSound').addEventListener('click', () => setSound(!state.sound));
$('togCode').addEventListener('click', () => setCodePanel(document.body.classList.contains('no-code')));
$('hideLeft').addEventListener('click', () => setCodePanel(false));

addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' && e.target.type !== 'checkbox') return;
  const k = e.key;
  if (k === ' ') { e.preventDefault(); setPlaying(!state.playing); }
  else if (k === 'ArrowRight') seek(state.t + (e.shiftKey ? 10 : 2));
  else if (k === 'ArrowLeft') seek(state.t - (e.shiftKey ? 10 : 2));
  else if (k === 'r' || k === 'R') { seek(0); setPlaying(true); }
  else if (k >= '1' && k <= '4') setCam(['broadcast', 'chase', 'top', 'fpv'][+k - 1]);
  else if (k === 'l' || k === 'L') setLabels(!state.labels);
  else if (k === 'm' || k === 'M') setSound(!state.sound);
  else if (k === 'c' || k === 'C') setCodePanel(document.body.classList.contains('no-code'));
  else if (k === '+' || k === '=') setSpeed(Math.min(4, state.speed * 2));
  else if (k === '-') setSpeed(Math.max(0.5, state.speed / 2));
  else if ((k === 'n' || k === 'p') && runs.length > 1) {
    const order = ranked.map((r) => r.idx), i = order.indexOf(state.focus);
    setFocus(order[(i + (k === 'n' ? 1 : order.length - 1)) % order.length]);
  } else if (k === 'f') { if (!document.fullscreenElement) document.documentElement.requestFullscreen?.(); else document.exitFullscreen?.(); }
});

addEventListener('beforeunload', () => {
  if (state.cam === 'broadcast') bcast = { pos: camera.position.toArray(), target: controls.target.toArray() };
  if (bcast) store.set('ftj-cam', bcast);
  store.set('ftj-view', { cam: state.cam, speed: state.speed, labels: state.labels, sound: state.sound });
});

// live reload for `fly.py --watch`
if (P.get('watch') && P.get('runs')) {
  let stamp = session?.stamp;
  setInterval(async () => {
    try {
      const s = await getJSON(P.get('runs'));
      if (s.stamp !== stamp) { stamp = s.stamp; const u = new URL(location.href); u.searchParams.set('autoplay', '1'); location.replace(u); }
    } catch { /* server restarting */ }
  }, 1000);
}

// ------------------------------------------------------------------ boot
renderCard();
setLabels(state.labels);
setSound(state.sound);
setSpeed(state.speed);
if (EXPLORE) {
  renderExplore();
} else {
  renderBoard();
  setFocus(state.focus);
  document.title = `${session?.title || runs[0].name} · ${course.name}`;
  if (P.get('autoplay')) setPlaying(true); else $('intro').hidden = false;
}
if (state.cam !== 'broadcast') setCam(state.cam);
applyVisibility();
const nums = (k) => (P.get(k) || '').split(',').map(Number);
if (P.get('cam')) {
  const [x, y, z, tx, ty, tz] = nums('cam');
  camera.position.copy(W(x, y, z));
  controls.target.copy(W(tx, ty, tz));
  controls.update();
}
if (P.get('fov')) { camera.fov = +P.get('fov'); camera.updateProjectionMatrix(); }
if (P.get('labels') === '0') { state.labels = false; labels.visible = false; }
if (P.get('arrows') === '0') arrows.visible = false;
const DRONE_OVERRIDE = P.get('drone') ? nums('drone') : null;
if (P.get('t')) seek(+P.get('t'));

Object.assign(window.__ftj, { state, seek, setPlaying, setFocus, setCam });

// ------------------------------------------------------------------ main loop
const clock = new THREE.Clock();
let shownScore = -1;
let frameCount = 0;
function tick() {
  const dt = Math.min(0.1, clock.getDelta());
  if (state.playing) {
    const t0 = state.t;
    state.t = Math.min(DURATION, state.t + dt * state.speed);
    fireEvents(t0, state.t);
    if (state.t >= DURATION) setPlaying(false);
  }
  const t = state.t;
  const now = performance.now() / 1000;

  let focusPose = startPose;
  drones.forEach((d, i) => {
    const run = runs[i];
    let { p, i: fi } = poseAt(run, t);
    if (DRONE_OVERRIDE && EXPLORE) {
      const [ox, oy, oz, oyaw = 0] = DRONE_OVERRIDE;
      p = [t, ox, oy, oz, oyaw, 0, 3, oz > 1 ? 1 : 0];
    }
    const [, x, y, z, yaw, roll, pitch, spin] = p;
    d.root.position.copy(W(x, y, z));
    d.root.rotation.y = THREE.MathUtils.degToRad(yaw);
    d.body.rotation.z = -THREE.MathUtils.degToRad(pitch);
    d.body.rotation.x = THREE.MathUtils.degToRad(roll);
    for (const pr of d.props) {
      if (spin) pr.rotation.y += pr.userData.dir * dt * 60;
      pr.userData.disc.visible = !!spin;
    }
    const [r, g, b] = run ? ledAt(run, t) : [255, 32, 32];
    d.ledMat.color.setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace);
    d.glow.material.color.copy(d.ledMat.color);
    d.glow.material.opacity = spin ? 0.85 : 0.35;
    const ground = surfaceAt(x, y);
    const pos = d.stick.geometry.attributes.position;
    pos.setXYZ(0, x, z + 0.5, -y); pos.setXYZ(1, x, ground + 0.6, -y);
    pos.needsUpdate = true;
    d.stick.computeLineDistances();
    d.stick.visible = d.root.visible && z - ground > 6 && !PHOTO;
    d.ring.visible = d.root.visible && !PHOTO;
    d.ring.position.set(x, ground + 0.8, -y);
    d.ring.scale.setScalar(1 + 0.15 * Math.sin(now * 4));
    if (d.tag) {
      d.tag.position.set(x, z + 24, -y);
      d.tag.visible = d.root.visible && state.race && runs.length > 1 && !(i === state.focus && (state.cam === 'chase' || state.cam === 'fpv'));
    }
    if (d.trail) d.trail.geometry.setDrawRange(0, run.frames.length ? fi + 1 : 0);
    if (i === state.focus) focusPose = p;
  });

  if (!EXPLORE) {
    const run = focusRun();
    const remaining = LIMIT - t;
    $('clock').textContent = mmss(Math.max(0, remaining));
    $('clock').classList.toggle('low', remaining < 10);
    const score = updateCard(run, t);
    if (score !== shownScore) { $('score').textContent = score; shownScore = score; }
    updateCode(run, t);
    updateConsole(run, t);
    updateFeed(run, t);
    const k = DURATION ? t / DURATION : 0;
    $('tlFill').style.width = `${k * 100}%`;
    $('tlHead').style.left = `${k * 100}%`;
    $('tNow').textContent = mmss(t);
  }

  if (++frameCount === 20) document.body.dataset.ready = '1';
  if (PHOTO && P.get('cam')) controls.enabled = false; else updateCamera(dt, focusPose);
  // labels right in front of the lens are just clutter
  if (state.labels) for (const l of labels.children) l.visible = l.position.distanceTo(camera.position) > 170;
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick();
