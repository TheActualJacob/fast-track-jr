#!/usr/bin/env python3
"""
Build docs/Fast-Track-Jr-Mission-Guide.pdf (4 pages: mission, course map, code cheat sheet, submitting).

    python docs/guide/build_guide.py            renders + PDF (needs Google Chrome)
    python docs/guide/build_guide.py --no-render   reuse the existing renders

3D figures come straight from the simulator's viewer (photo mode), and every number in the
diagrams and tables is read from course/fast_track_jr.json, so the guide always matches the sim.
"""
import argparse
import datetime
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]

import figures  # noqa: E402
from fly import serve  # noqa: E402

IMG = os.path.join(HERE, "img")
OUT_PDF = os.path.join(ROOT, "docs", "Fast-Track-Jr-Mission-Guide.pdf")
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chrome") or "",
]
JR = "course/fast_track_jr.json"
REAL = "course/fast_track_2027.json"

# name: (course, camera "x,y,z,tx,ty,tz" in sim cm, drone "x,y,z,yaw" or None, fov)
SHOTS = {
    "overview": (JR, "-360,-470,438,125,-125,12", "0,0,0,0", 36),
}


def chrome():
    for c in CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    raise SystemExit("Google Chrome is needed to build the guide.")


def render(base_url):
    from PIL import Image, ImageChops

    os.makedirs(IMG, exist_ok=True)
    procs = []
    tmp = tempfile.mkdtemp(prefix="guide-chrome-")
    for name, (course, cam, drone, fov) in SHOTS.items():
        url = f"{base_url}/sim/viewer/index.html?photo=1&theme=light&labels=0&course={course}&cam={cam}&fov={fov}"
        if drone:
            url += f"&drone={drone}"
        png = os.path.join(tmp, name + ".png")
        cmd = [chrome(), "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
               "--hide-scrollbars", "--window-size=1600,1000", "--force-device-scale-factor=2",
               "--timeout=9000", f"--user-data-dir={os.path.join(tmp, 'p-' + name)}", f"--screenshot={png}", url]
        procs.append((name, png, subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)))
    deadline = time.time() + 90
    for name, png, p in procs:
        while p.poll() is None and not os.path.exists(png) and time.time() < deadline:
            time.sleep(0.5)
        time.sleep(0.5)
        p.kill()
        if not os.path.exists(png):
            print(f"  ! render failed: {name}")
            continue
        im = Image.open(png).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 10 else 0).getbbox()
        if box:
            pad = 30
            box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
            im = im.crop(box)
        im.save(os.path.join(IMG, name + ".jpg"), quality=88, optimize=True)
        print(f"  ✓ {name}  {im.width}×{im.height}")
    shutil.rmtree(tmp, ignore_errors=True)


def e(s):
    return html.escape(str(s))


def cm(v):
    return f"{v:g} cm"


def inch(v):
    return f"{v / 2.54:.1f} in"


def build_html(c, real=None):
    el = {x["id"]: x for x in c["elements"]}
    tasks = c["tasks"]
    ra, gk, cu, ba, yk, tu, lp = (el[k] for k in ("red_arch", "green_keyhole", "large_cube", "blue_arch",
                                                  "yellow_keyhole", "tunnel", "landing_pad"))
    corner = cu["center"][0]
    version = f"v1.0, {datetime.date.today():%m/%d/%Y}"

    def score_rows():
        rows = []
        for t in tasks:
            tag = ' <span class="tag">Bonus</span>' if t.get("bonus") else ""
            rows.append(f"<tr><td>{e(t['label'])}{tag}</td><td class='num'>{t['points']}</td></tr>")
        return "\n".join(rows)

    body = f"""
<section>
  <div class="eyebrow">Aerial Drone Club · Autonomous Flight Workshop</div>
  <h1>Fast Track Jr.</h1>
  <p class="lede">Write a Python program that flies the <b>CoDrone EDU</b> through this course <b>by itself</b>.
    You have <b>20 minutes</b>. Write and test it in the <b>Mission Lab</b> in your browser, submit it, and we'll replay
    everyone's flight on the big screen.</p>
  <div class="labline"><img src="img/lab-qr.svg" alt="QR code"><div><span>Mission Lab</span><b>theactualjacob.github.io/fast-track-jr</b></div></div>
  <img class="hero" src="img/overview.jpg">
  <div class="cols">
    <div>
      <h3>Scoring</h3>
      <table class="compact">
        <thead><tr><th>Task</th><th class="num">Points</th></tr></thead>
        <tbody>{score_rows()}</tbody>
      </table>
    </div>
    <div>
      <h3>Rules</h3>
      <ul class="rules">
        <li>The drone starts on the green square, facing the red arch.</li>
        <li>Fly through every gate <b>in the direction of its arrow</b>.</li>
        <li>After <span class="code">takeoff()</span> the drone hovers at about <b>{c['takeoff_height']} cm</b>.</li>
        <li><b>Hit anything and you crash.</b> The run ends, but you keep your points.</li>
        <li>Each gate scores up to 2 times. Only your <b>final</b> landing counts, and only one landing option.</li>
        <li>The match is <b>3 minutes</b>. Ties go to the faster run.</li>
      </ul>
    </div>
  </div>
</section>

<section class="page">
  <h2 class="section">Course Map</h2>
  <figure class="map">{figures.top_view(c)}</figure>
  <table class="compact">
    <thead><tr><th>Gate</th><th>Where (center)</th><th>How high</th><th>Fly</th></tr></thead>
    <tbody>
      <tr><td>Red arch</td><td>{ra['center'][0]:g} cm forward</td><td>opening up to {ra['inner_h']:g} cm</td><td>forward</td></tr>
      <tr><td>Green keyhole</td><td>{gk['center'][0]:g} cm forward</td><td><b>center {gk['center'][2]:g} cm</b></td><td>forward</td></tr>
      <tr><td>Large cube <span class="tag">Bonus</span></td><td>{corner:g} cm forward (the corner)</td><td>holes centered {cu['height'] / 2:g} cm, {cu['hole_d']:g} cm wide</td><td>in one side, out another</td></tr>
      <tr><td>Blue arch</td><td>corner, then {-ba['center'][1]:g} cm right</td><td>opening up to {ba['inner_h']:g} cm</td><td>right</td></tr>
      <tr><td>Yellow keyhole</td><td>corner, then {-yk['center'][1]:g} cm right</td><td><b>center {yk['center'][2]:g} cm</b></td><td>right</td></tr>
      <tr><td>Tunnel <span class="tag">Bonus</span></td><td>corner, then {-tu['center'][1]:g} cm right</td><td>{tu['bottom']:g}–{tu['bottom'] + tu['length']:g} cm (hangs over the pad)</td><td>straight down</td></tr>
      <tr><td>Landing pad</td><td>corner, then {-lp['center'][1]:g} cm right</td><td>floor · bullseye {lp['bullseye_d']:g} cm wide</td><td>land</td></tr>
    </tbody>
  </table>
  <p class="small">Keyhole and tunnel openings are about 60 cm wide and the drone is 14 cm, so aim within ±20 cm of the center.</p>
</section>

<section class="page">
  <h2 class="section">Code Cheat Sheet</h2>
  <div class="cols code-cols">
    <div>
      <h3>Every program looks like this</h3>
<pre>from codrone_edu.drone import *

drone = Drone()
drone.pair()

drone.takeoff()      # up to ~{c['takeoff_height']} cm

<span class="hl"># your moves go here</span>

drone.land()
drone.close()</pre>
    </div>
    <div>
      <h3>Which way is which</h3>
      <p>Moves go the way the drone is <b>facing</b> (at the start: toward the red arch). Distances are in <b>cm</b>.</p>
      <div class="dirs">
        <div><b>forward</b> · toward the red arch</div>
        <div><b>right</b> · toward the second mat</div>
        <div><b>up / down</b> · height</div>
      </div>
      <h3>Example: the first two gates</h3>
<pre>drone.move_upward(40)    # 80 → 120 cm
drone.move_forward(140)  # red arch + keyhole</pre>
    </div>
  </div>
  <h3>Commands</h3>
  <table class="compact cmds">
    <thead><tr><th>Command</th><th>What it does</th></tr></thead>
    <tbody>
      <tr><td class="code">drone.takeoff()</td><td>Take off and hover at about {c['takeoff_height']} cm.</td></tr>
      <tr><td class="code">drone.move_forward(100)</td><td>Fly forward 100 cm. Also <span class="code">move_backward</span>.</td></tr>
      <tr><td class="code">drone.move_right(50)</td><td>Fly sideways 50 cm without turning. Also <span class="code">move_left</span>.</td></tr>
      <tr><td class="code">drone.move_upward(40)</td><td>Climb 40 cm. Also <span class="code">move_downward</span>.</td></tr>
      <tr><td class="code">drone.turn_right(90)</td><td>Turn in place 90°. Also <span class="code">turn_left</span>.</td></tr>
      <tr><td class="code">drone.hover(1)</td><td>Hold still for 1 second.</td></tr>
      <tr><td class="code">drone.move_forward(100, "cm", 1)</td><td>Third value is the speed in m/s (default 0.5, max 2).</td></tr>
      <tr><td class="code">print(drone.get_pos_z())</td><td>Print the current height in cm.</td></tr>
      <tr><td class="code">drone.land()</td><td>Land right where the drone is.</td></tr>
    </tbody>
  </table>
  <h3>Watch out</h3>
  <ul class="rules two">
    <li>You start at 80 cm and the green keyhole is at 120 cm. <b>Climb first</b> or you'll crash.</li>
    <li>Spelling counts: <span class="code">move_foward</span> is an error.</li>
    <li>Turns can overshoot a few degrees. <span class="code">move_right()</span> is more accurate.</li>
    <li>Always finish with <span class="code">drone.land()</span>, or you get no landing points.</li>
  </ul>
</section>

<section class="page">
  <h2 class="section">Fly &amp; Submit</h2>
  <div class="lab-box">
    <img src="img/lab-qr.svg" alt="QR code for the Mission Lab">
    <div>
      <div class="eyebrow">Open the Mission Lab</div>
      <div class="lab-url">theactualjacob.github.io/fast-track-jr</div>
      <p>Runs in your browser. Nothing to install; Chromebooks are fine.</p>
    </div>
  </div>
  <ol class="steps">
    <li>Type your <b>GitHub username</b> in the top bar (no account? type your name).</li>
    <li>Fill in the TODOs in the editor, using the course map and the cheat sheet.</li>
    <li>Press <b>Fly</b> (or <b>Ctrl/⌘ + Enter</b>). Your flight replays in 3D and the running line lights up. A crash or bug
      points to its line. Fix it and fly again as many times as you like.</li>
    <li>Click <b>Submit</b>:
      <ul>
        <li><b>Open a pull request</b> if you have a GitHub account. Then click <b>Commit changes → Propose changes → Create pull request</b>.</li>
        <li><b>Copy share link</b> if you don't. Paste the link wherever your leader asks.</li>
      </ul>
    </li>
  </ol>
  <h2 class="section second">Hints</h2>
  <table class="compact hints">
    <tbody>
      <tr><td>Green keyhole</td><td>Climb 40 cm before you fly forward.</td></tr>
      <tr><td>The corner</td><td>It's {corner:g} cm ahead. Either <span class="code">turn_right(90)</span> then fly forward, or skip turning and use <span class="code">move_right()</span>.</td></tr>
      <tr><td>Yellow keyhole</td><td>It's 20 cm higher than the green one ({yk['center'][2]:g} cm).</td></tr>
      <tr><td>Tunnel over the pad</td><td><b>Safe:</b> drop below 85 cm before you reach it, then land. <b>Bonus:</b> climb above 150 cm, stop right over the pad and
        <span class="code">land()</span>. You drop through the tunnel for +{next(t['points'] for t in tasks if t['id'] == 'tunnel')}, and the bullseye if you're centered.</td></tr>
      <tr><td>Large cube (hard)</td><td>Holes are 30 cm wide and 25 cm off the floor. Get low before the cube, fly into the middle, then slide out a different side.</td></tr>
    </tbody>
  </table>
  <div class="note">After the session every flight is replayed in 3D, all racing at once, with your code on screen. The same file flies the
    <b>real</b> CoDrone EDU, so we'll try the best ones on the real field next.</div>
</section>
"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Fast Track Jr. Mission Guide</title>
<link rel="stylesheet" href="guide.css">
<style>
@page {{
  @bottom-left {{ content: "Fast Track Jr. Mission Guide {e(version)}\\A Aerial Drone Club workshop · not an official REC Foundation document";
    white-space: pre; font: 400 8.5pt/1.35 Roboto, "Helvetica Neue", Arial, sans-serif; color: #1c3563; vertical-align: top; padding-top: 10pt; }}
  @bottom-right {{ content: "FAST TRACK JR."; font: 900 12pt Roboto, "Helvetica Neue", Arial, sans-serif; letter-spacing: 1pt; color: #1c3563;
    vertical-align: top; padding-top: 10pt; }}
}}
</style>
</head><body>{body}</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    base = serve()
    if not a.no_render:
        print("Rendering figures…")
        render(base)
    with open(os.path.join(ROOT, JR)) as f:
        c = json.load(f)
    with open(os.path.join(ROOT, REAL)) as f:
        real = json.load(f)
    page = os.path.join(HERE, "guide.html")
    with open(page, "w") as f:
        f.write(build_html(c, real))
    print("Printing PDF…")
    rel = os.path.relpath(page, ROOT)
    tmp = tempfile.mkdtemp(prefix="guide-pdf-")
    cmd = [chrome(), "--headless=new", "--no-pdf-header-footer", f"--user-data-dir={tmp}", "--timeout=8000",
           f"--print-to-pdf={OUT_PDF}", f"{base}/{rel}"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < 60:
        time.sleep(0.5)
    p.kill()
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", os.path.relpath(OUT_PDF, ROOT))


if __name__ == "__main__":
    main()
