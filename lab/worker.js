// Runs the simulator's Python in the browser (Pyodide), off the main thread (a module worker).
// The page kills and restarts this worker if a mission never finishes (infinite loop).
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs';

const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';

const FILES = [
  'sim/__init__.py', 'sim/engine.py', 'sim/course.py', 'sim/runcore.py',
  'sim/fake/codrone_edu/__init__.py', 'sim/fake/codrone_edu/drone.py',
  'sim/fake/codrone_edu/protocol.py', 'sim/fake/codrone_edu/system.py',
];
let py = null;

async function init(base) {
  py = await loadPyodide({ indexURL: PYODIDE_URL });
  await Promise.all(FILES.map(async (f) => {
    const r = await fetch(new URL(f, base), { cache: 'no-cache' });
    if (!r.ok) throw new Error(`couldn't load ${f} (${r.status})`);
    const path = '/app/' + f;
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
    py.FS.writeFile(path, await r.text());
  }));
  py.runPython("import sys; sys.path[:0] = ['/app/sim/fake', '/app']\nimport sim.runcore");
}

self.onmessage = async (e) => {
  const m = e.data;
  if (m.type === 'init') {
    try {
      await init(m.base);
      postMessage({ type: 'ready' });
    } catch (err) {
      postMessage({ type: 'fatal', message: String(err) });
    }
    return;
  }
  if (m.type === 'run') {
    try {
      py.FS.mkdirTree('/mission');
      const path = '/mission/' + m.filename;
      py.FS.writeFile(path, m.code);
      py.globals.set('_job', JSON.stringify({ path, name: m.name, realistic: !!m.realistic, course: m.course }));
      const out = py.runPython(`
import json, zlib
from sim import runcore
_j = json.loads(_job)
json.dumps(runcore.run_mission(_j["path"], _j["course"], name=_j["name"], realistic=_j["realistic"],
                               seed=zlib.crc32(_j["name"].encode()), echo=False), separators=(",", ":"))
`);
      postMessage({ type: 'result', log: JSON.parse(out) });
    } catch (err) {
      postMessage({ type: 'error', message: String(err) });
    }
  }
};
