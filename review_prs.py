#!/usr/bin/env python3
"""
Leader tool: fly every open pull request's mission in the simulator and show them on the big screen.

    python review_prs.py                 every open PR -> leaderboard + 3D replay (race mode)
    python review_prs.py 12 15           just PRs #12 and #15
    python review_prs.py --state all     include closed / merged PRs too
    python review_prs.py --comment       also post each score as a comment on its PR (asks first)
    python review_prs.py --realistic     fly with real-drone wobble
    python review_prs.py --field real    fly them on the official Mission 2027 field
    python review_prs.py --no-open       text leaderboard only
    python review_prs.py --links links.txt   also fly Mission Lab share links (one per line)
    python review_prs.py --links links.txt --no-prs   only the share links

Needs the GitHub CLI (`gh`), logged in. Only the mission files are downloaded from each PR; they
run on YOUR copy of the simulator, so a PR can't change the rules or the scoring.
"""
import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from fly import keep_open, serve, write_session, _wait  # noqa: E402
from sim import sharelink  # noqa: E402
from sim.runner import RUNS, leaderboard_text, markdown_report, simulate, slug, text_report  # noqa: E402

PR_DIR = os.path.join(RUNS, "prs")
ALLOWED_IMPORTS = {"codrone_edu", "codrone_edu.drone", "codrone_edu.protocol", "codrone_edu.system",
                   "time", "math", "random"}
RISKY_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "setattr",
               "getattr", "delattr", "vars"}


def gh(*args):
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("The GitHub CLI isn't installed. Get it from https://cli.github.com and run `gh auth login`.")
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout


def safety_check(source):
    """Things a drone mission has no business doing. Not a sandbox — just a heads-up."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # the simulator will report it nicely
    notes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in ALLOWED_IMPORTS:
                    notes.append(f"line {node.lineno}: import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") not in ALLOWED_IMPORTS:
                notes.append(f"line {node.lineno}: from {node.module} import …")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in RISKY_CALLS:
            notes.append(f"line {node.lineno}: {node.func.id}(…)")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr != "__name__":
            notes.append(f"line {node.lineno}: .{node.attr}")
    return notes


def fetch_prs(repo, numbers, state):
    fields = "number,title,author,headRefOid,url,files,state"
    if numbers:
        return [json.loads(gh("pr", "view", str(n), "--repo", repo, "--json", fields)) for n in numbers]
    return json.loads(gh("pr", "list", "--repo", repo, "--state", state, "--limit", "200", "--json", fields))


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description="Fly every PR's mission in the simulator")
    ap.add_argument("prs", nargs="*", type=int, help="PR numbers (default: all open PRs)")
    ap.add_argument("--repo", help="owner/name (default: the GitHub repo of this folder)")
    ap.add_argument("--state", default="open", choices=["open", "closed", "merged", "all"])
    ap.add_argument("--realistic", action="store_true")
    ap.add_argument("--field", default="jr", help="'jr' (default), 'real', or a course .json")
    ap.add_argument("--comment", action="store_true", help="post each result as a PR comment")
    ap.add_argument("--yes", action="store_true", help="don't stop to ask about flagged code")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--links", help="text file of Mission Lab share links (one per line), flown alongside the PRs")
    ap.add_argument("--no-prs", action="store_true", help="skip GitHub; only fly --links")
    a = ap.parse_args()

    repo = a.repo
    if a.no_prs:
        repo = repo or "(share links)"
    elif not repo:
        try:
            repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
        except RuntimeError as e:
            raise SystemExit(f"Couldn't work out the GitHub repo ({e}).\nRun this inside your clone, or pass --repo owner/name.")
    prs = []
    if not a.no_prs:
        print(f"📥 Fetching pull requests from {repo}…")
        prs = fetch_prs(repo, a.prs, a.state)
        if not prs and not a.links:
            raise SystemExit("No pull requests found.")

    os.makedirs(PR_DIR, exist_ok=True)
    jobs = []  # (pr, path_in_repo, local_file, name)
    for pr in sorted(prs, key=lambda p: p["number"]):
        login = (pr.get("author") or {}).get("login") or "someone"
        paths = [f["path"] for f in pr.get("files", [])]
        missions = [p for p in paths if p.startswith("missions/") and p.endswith(".py")
                    and not os.path.basename(p).startswith("_")]
        others = [p for p in paths if not p.startswith("missions/")]
        tag = f"#{pr['number']} {login}"
        if others:
            print(f"   ⚠️  {tag} also changes files outside missions/: {', '.join(others[:5])}")
        if not missions:
            print(f"   ·  {tag}: no mission file in this PR — skipped")
            continue
        for path in missions:
            try:
                src = gh("api", "-H", "Accept: application/vnd.github.raw",
                         f"repos/{repo}/contents/{path}?ref={pr['headRefOid']}")
            except RuntimeError:
                print(f"   ·  {tag}: couldn't download {path} (deleted?) — skipped")
                continue
            stem = os.path.splitext(os.path.basename(path))[0]
            name = login if len(missions) == 1 else f"{login}/{stem}"
            local = os.path.join(PR_DIR, f"pr{pr['number']}-{slug(stem)}.py")
            with open(local, "w", encoding="utf-8") as f:
                f.write(src)
            jobs.append((pr, path, local, name))
    if a.links:
        link_dir = os.path.join(RUNS, "links")
        os.makedirs(link_dir, exist_ok=True)
        with open(a.links, encoding="utf-8") as f:
            links = [ln.strip() for ln in f if "#m=" in ln]
        seen = {}
        for i, link in enumerate(links, 1):
            try:
                shared = sharelink.decode(link)
            except Exception as e:
                print(f"   ⚠️  link {i} couldn't be read ({e}) — skipped")
                continue
            name = slug(shared["name"])
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:        # the same person sent several links: keep them apart
                name = f"{name}-{seen[name]}"
            local = os.path.join(link_dir, f"{name}.py")
            with open(local, "w", encoding="utf-8") as f:
                f.write(shared["code"])
            fake_pr = {"number": None, "url": link, "title": "share link", "author": {"login": name}}
            jobs.append((fake_pr, f"share link · {name}.py", local, name))
        print(f"🔗 {len(links)} share link(s) read from {a.links}")
    if not jobs:
        raise SystemExit("Nothing to fly.")

    flagged = [(pr, path, notes) for pr, path, local, _ in jobs
               if (notes := safety_check(open(local, encoding="utf-8").read()))]

    def tag(pr):
        return f"PR #{pr['number']}" if pr.get("number") else "Link"
    if flagged:
        print("\n🔎 Some missions use things a drone mission normally doesn't need:")
        for pr, path, notes in flagged:
            print(f"   {tag(pr)} {path}: " + "; ".join(notes[:6]))
        print("   The simulator runs this code on your computer. Have a look at the PR if you're unsure.")
        if not a.yes and input("   Fly them anyway? [y/N] ").strip().lower() != "y":
            skip = {(pr["number"], path) for pr, path, _ in flagged}
            jobs = [j for j in jobs if (j[0]["number"], j[1]) not in skip]
            print("   Skipping the flagged ones.")

    print(f"\n🚁 Flying {len(jobs)} mission(s)…\n")
    logs, meta = [], {}
    for pr, path, local, name in jobs:
        prefix = f"pr{pr['number']}" if pr.get("number") else "link"
        log = simulate(local, name=name, realistic=a.realistic, field=a.field,
                       out=os.path.join(RUNS, f"{prefix}-{slug(name)}.json"))
        log["mission_file"] = path
        logs.append(log)
        meta[name] = {"pr": pr["number"], "url": pr["url"], "title": pr["title"],
                      "author": (pr.get("author") or {}).get("login")}
        print(f"{tag(pr)} · {pr['title']}")
        print(text_report(log, color=sys.stdout.isatty()))
        print()
        # keep the PR path in the replay's file label
        with open(os.path.join(ROOT, log["_path"])) as f:
            data = json.load(f)
        data["mission_file"] = path
        with open(os.path.join(ROOT, log["_path"]), "w") as f:
            json.dump(data, f, separators=(",", ":"))

    print(leaderboard_text(logs))

    if a.comment:
        print(f"\nAbout to post a results comment on {len(logs)} PR(s) in {repo}.")
        if input("Post them? [y/N] ").strip().lower() == "y":
            for log in logs:
                n = meta[log["name"]]["pr"]
                if not n:
                    continue
                body = markdown_report(log) + "\n_Flown in the Fast Track Jr. simulator._\n"
                with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
                    f.write(body)
                try:
                    gh("pr", "comment", str(n), "--repo", repo, "--body-file", f.name)
                    print(f"   💬 commented on #{n}")
                except RuntimeError as e:
                    print(f"   couldn't comment on #{n}: {e}")
                finally:
                    os.remove(f.name)

    if a.no_open:
        return
    session = write_session(logs, f"PR showdown · {repo}", meta)
    url = f"{serve()}/sim/viewer/index.html?runs={session}"
    keep_open(url)
    print("   Keys: Space play/pause · N/P next/prev pilot · 1-4 cameras · ←/→ seek · F fullscreen")
    _wait()


if __name__ == "__main__":
    main()
