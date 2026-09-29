#!/usr/bin/env python3
"""
Fly a mission in the Fast Track Jr. simulator and watch the 3D replay.

    python fly.py missions/alex.py                 fly one mission, open the 3D replay
    python fly.py missions/*.py                    fly several -> leaderboard + race mode
    python fly.py missions/alex.py --watch         re-fly every time you save the file
    python fly.py missions/alex.py --realistic     add real-drone wobble (drift, turn errors)
    python fly.py training/me.py --field real      fly on the official Mission 2027 solo field
    python fly.py --course                         just explore the course (add --field real for the real one)
    python fly.py missions/alex.py --no-open       text results only

Needs only Python 3.9+ (no pip installs). The replay opens in your web browser.
"""
import argparse
import functools
import glob
import http.server
import json
import os
import socket
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from sim.runner import RUNS, credit_line, ending, field_path, leaderboard_text, markdown_report, simulate, text_report  # noqa: E402

SESSION = os.path.join(RUNS, "_session.json")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        if str(path).endswith(".js"):
            return "text/javascript"
        return super().guess_type(path)


def free_port(start=8765):
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port found for the viewer.")


def serve():
    port = free_port()
    handler = functools.partial(QuietHandler, directory=ROOT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"


def write_session(logs, title, extra=None):
    runs = []
    for log in logs:
        meta = {"file": log["_path"], "name": log["name"]}
        meta.update((extra or {}).get(log["name"], {}))
        runs.append(meta)
    with open(SESSION, "w") as f:
        json.dump({"title": title, "stamp": time.time(), "runs": runs}, f, indent=1)
    return os.path.relpath(SESSION, ROOT)


def fly_all(files, realistic, quiet=False, field=None):
    logs = []
    for path in files:
        log = simulate(path, realistic=realistic, field=field)
        logs.append(log)
        if not quiet:
            out = log["_stdout"].strip()
            if out:
                print("\n".join("  │ " + ln for ln in out.splitlines()[-25:]))
            print(text_report(log, color=sys.stdout.isatty()))
            print()
    if len(logs) > 1 and not quiet:
        print(leaderboard_text(logs))
    return logs


def annotation(log):
    """A GitHub Actions workflow command, so the result shows up right on the PR's diff."""
    def clean(t):
        return str(t).replace("%", "%25").replace("\r", "").replace("\n", " ").replace("::", ": :")
    path = log.get("mission_file", "")
    r = log["result"]
    if log.get("error"):
        e = log["error"]
        return f"::error file={path},line={e.get('line') or 1},title=Bug in your mission::{clean(e['type'] + ': ' + e['message'])}"
    if log.get("crash"):
        c = log["crash"]
        return (f"::warning file={path},line={credit_line(log, c) or 1},title=Crash ({r['score']} points)::"
                f"{clean('Hit ' + c['what'] + ' during this line.')}")
    return f"::notice file={path},line=1,title={r['score']} points::{clean(ending(log))}"


def keep_open(url):
    print(f"\n🌐 Replay: {url}")
    print("   (keep this window open while you watch — press Ctrl+C to stop)")
    webbrowser.open(url)


def main():
    sys.stdout.reconfigure(line_buffering=True)  # show results right away, even when piped
    ap = argparse.ArgumentParser(description="Fast Track Jr. drone simulator")
    ap.add_argument("missions", nargs="*", help="mission .py files")
    ap.add_argument("--realistic", action="store_true", help="add drift and small errors like a real drone")
    ap.add_argument("--watch", action="store_true", help="re-fly whenever a mission file is saved")
    ap.add_argument("--course", "--explore", action="store_true", help="open the course explorer (no mission needed)")
    ap.add_argument("--field", default="jr", help="'jr' (workshop course, default), 'real' (official Mission 2027 field) or a course .json")
    ap.add_argument("--no-open", action="store_true", help="don't open the 3D viewer")
    ap.add_argument("--ci", action="store_true", help="print a Markdown report (for GitHub Actions)")
    a = ap.parse_args()

    files = []
    for m in a.missions:
        files.extend(sorted(glob.glob(m)) or [m])
    files = [f for f in files if os.path.basename(f) != "_template.py" or len(a.missions) == 1]
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit(f"Can't find: {', '.join(missing)}")

    if a.course or not files:
        if not files and not a.course:
            ap.print_help()
            print("\nTip: python fly.py --course   opens the course so you can look around.")
            return
        course_rel = os.path.relpath(field_path(a.field), ROOT)
        url = serve() + "/sim/viewer/index.html?course=" + course_rel
        keep_open(url)
        _wait()
        return

    if a.ci:
        logs = fly_all(files, a.realistic, quiet=True, field=a.field)
        report = "\n".join(markdown_report(log) for log in logs)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(report + "\n")
            for log in logs:
                print(annotation(log))
        else:
            print(report)
        # a Python error in the mission turns the PR check red; a crash is just a bad flight
        sys.exit(1 if any(log.get("error") for log in logs) else 0)

    logs = fly_all(files, a.realistic, field=a.field)
    if a.no_open:
        return
    title = logs[0]["name"] if len(logs) == 1 else "Showdown"
    session = write_session(logs, title)
    url = f"{serve()}/sim/viewer/index.html?runs={session}"
    if a.watch:
        url += "&watch=1"
    keep_open(url)

    if not a.watch:
        _wait()
        return
    print("👀 Watching for changes… save a mission file to re-fly it.")
    mtimes = {f: os.path.getmtime(f) for f in files}
    try:
        while True:
            time.sleep(0.5)
            changed = [f for f in files if os.path.getmtime(f) != mtimes[f]]
            if not changed:
                continue
            time.sleep(0.2)  # let the editor finish writing
            for f in files:
                mtimes[f] = os.path.getmtime(f)
            print(f"\n↻ {', '.join(changed)} changed — flying again…\n")
            logs = fly_all(files, a.realistic, field=a.field)
            write_session(logs, title)
    except KeyboardInterrupt:
        print()


def _wait():
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
