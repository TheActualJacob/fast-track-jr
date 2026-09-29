"""Run missions in the simulator (each in its own process) and format the results."""
import json
import os
import re
import subprocess
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "runs")
BOOT = os.path.join(ROOT, "sim", "bootstrap.py")


def slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s).strip("-") or "pilot"


FIELDS = {"jr": os.path.join(ROOT, "course", "fast_track_jr.json"),
          "real": os.path.join(ROOT, "course", "fast_track_2027.json")}


def field_path(field):
    """'jr', 'real', or a path to a course .json"""
    if field in (None, ""):
        return FIELDS["jr"]
    if field in FIELDS:
        return FIELDS[field]
    if os.path.isfile(field):
        return os.path.abspath(field)
    raise SystemExit(f"Unknown field '{field}'. Use one of: {', '.join(FIELDS)} (or a path to a course .json).")


def simulate(mission, name=None, realistic=False, out=None, timeout=45, field=None):
    """Fly one mission file. Returns the flight log (dict)."""
    mission = os.path.abspath(mission)
    name = name or os.path.splitext(os.path.basename(mission))[0]
    os.makedirs(RUNS, exist_ok=True)
    out = out or os.path.join(RUNS, slug(name) + ".json")
    seed = zlib.crc32(name.encode())
    cmd = [sys.executable, "-X", "utf8", BOOT, mission, out, "--name", name, "--seed", str(seed),
           "--course", field_path(field)]
    if realistic:
        cmd.append("--realistic")
    if os.path.exists(out):
        os.remove(out)
    try:
        proc = subprocess.run(cmd, cwd=os.path.dirname(mission), capture_output=True, text=True,
                              stdin=subprocess.DEVNULL,
                              timeout=timeout, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        stdout, stderr = "", "The simulation timed out."
    if not os.path.exists(out):
        # the bootstrap itself died; make a minimal log so the leaderboard still works
        log = {"version": 1, "name": name, "mission_file": os.path.relpath(mission, ROOT),
               "end_reason": "error", "end_message": stderr.strip()[-2000:],
               "result": {"score": 0, "finish_time": 0, "status": "error", "breakdown": [], "scores": []},
               "error": {"type": "SimulatorError", "message": stderr.strip()[-500:], "line": None},
               "crash": None, "frames": [], "events": [], "calls": [], "console": [], "leds": [], "sounds": [],
               "source": open(mission, encoding="utf-8", errors="replace").read()}
        with open(out, "w") as f:
            json.dump(log, f)
    with open(out) as f:
        log = json.load(f)
    log["_path"] = os.path.relpath(out, ROOT)
    log["_stdout"] = stdout
    log["_stderr"] = stderr
    return log


def mmss(t):
    t = max(0.0, t or 0.0)
    return f"{int(t // 60)}:{t % 60:04.1f}"


def credit_line(log, ev):
    """Line to blame/credit: a helper function's line credits the place it was called from."""
    line = (ev or {}).get("line")
    outer = (ev or {}).get("outer") or []
    if not line or not outer:
        return line
    callers = {tuple(c.get("outer") or [])[:1] for c in log.get("calls", []) if c.get("line") == line and c.get("outer")}
    return outer[0] if len(callers) > 1 else line


def _call_at(log, line):
    src = log.get("source", "").splitlines()
    if line and 0 < line <= len(src):
        return src[line - 1].strip()
    return ""


def ending(log):
    """One line describing how the flight ended."""
    r = log["result"]
    if log.get("crash"):
        c = log["crash"]
        ln = credit_line(log, c)
        where = f" (line {ln}: {_call_at(log, ln)})" if ln else ""
        return f"💥 Crashed into {c['what']} at {mmss(c['t'])}{where}"
    if log.get("error"):
        e = log["error"]
        where = f" on line {e['line']}" if e.get("line") else ""
        return f"🐞 {e['type']}{where}: {e['message']}"
    if r["status"] == "landed":
        land = {"land_bullseye": "on the BULLSEYE 🎯", "land_pad": "on the landing pad",
                "land_cube": "on top of the cube"}.get(r.get("landing"), "on the floor")
        return f"🛬 Landed {land} at {mmss(r['finish_time'])}"
    if r["status"] == "never took off":
        return "😴 The drone never took off (did you call drone.takeoff()?)"
    return f"🚁 Program ended with the drone {r['status']}"


def text_report(log, color=True):
    B = "\033[1m" if color else ""
    G = "\033[32m" if color else ""
    D = "\033[2m" if color else ""
    X = "\033[0m" if color else ""
    r = log["result"]
    field = (log.get("course") or {}).get("name", "Fast Track Jr.")
    out = [f"{B}━━━ {field} · {log['name']} ━━━{X}"]
    for row in r.get("breakdown", []):
        if row["count"]:
            pts = row["points"] * row["count"]
            times = f" x{row['count']}" if row["count"] > 1 else ""
            out.append(f"  {G}✓{X} {row['label']:<34}{times:<4} {G}+{pts}{X}")
        elif not row.get("group"):
            tag = " (bonus)" if row.get("bonus") else ""
            out.append(f"  {D}· {row['label'] + tag:<34}      {row['points']}{X}")
    for ev in log.get("events", []):
        if ev["type"] == "warn":
            out.append(f"  ⚠️  {ev['text']}")
    out.append("  " + ending(log))
    out.append(f"{B}  SCORE {r['score']}   ·   time {mmss(r['finish_time'])}{X}")
    return "\n".join(out)


def rank(logs):
    return sorted(logs, key=lambda l: (-l["result"]["score"], l["result"]["finish_time"] or 9999))


def leaderboard_text(logs):
    lines = ["", "🏆  LEADERBOARD", f"  {'#':>2}  {'pilot':<22}{'score':>6}  {'time':>7}  result"]
    for i, l in enumerate(rank(logs), 1):
        r = l["result"]
        how = ending(l)
        lines.append(f"  {i:>2}  {l['name'][:22]:<22}{r['score']:>6}  {mmss(r['finish_time']):>7}  {how[:60]}")
    return "\n".join(lines)


def markdown_report(log):
    r = log["result"]
    rows = ["| Task | Points |", "|---|---:|"]
    for row in r.get("breakdown", []):
        if row["count"]:
            x = f" ×{row['count']}" if row["count"] > 1 else ""
            rows.append(f"| ✅ {row['label']}{x} | +{row['points'] * row['count']} |")
        elif not row.get("group"):
            rows.append(f"| ⬜ {row['label']}{' *(bonus)*' if row.get('bonus') else ''} | {row['points']} |")
    warns = [f"> ⚠️ {e['text']}" for e in log.get("events", []) if e["type"] == "warn"]
    return "\n".join([
        f"### 🚁 `{log.get('mission_file', log['name'])}` — **{r['score']} points** in {mmss(r['finish_time'])}",
        "", ending(log), "", *rows, "", *warns, ""])
