# Leader guide

How to run the Fast Track Jr. workshop. Participants only need a GitHub account and a browser. All the
simulating happens on your laptop.

## The Mission Lab (what participants use)

**https://theactualjacob.github.io/fast-track-jr/** is a GitHub Pages site built from this repo (`index.html` +
`lab/`). It's a code editor, the same simulator running in the browser (Pyodide, which is Python compiled to
WebAssembly), and the 3D replay side by side. Nothing to install; it works on Chromebooks. The first load downloads
about 10 MB, which the browser then caches, so it needs internet.

Participants submit in one of two ways:

- **Pull request**: *Submit → Open a pull request* opens GitHub's "new file" page with their code already filled in.
- **Share link** (no GitHub account): *Submit → Copy share link* packs the code into a URL. Collect the links, e.g. in a
  Google Form or the group chat, and paste them into a text file, one per line. Opening a link flies that mission in the
  Lab straight away, and `python review_prs.py --links links.txt` flies them all alongside the PRs, with one leaderboard.

Scores shown in the Lab are computed in the participant's browser, so treat them as practice. The official scores are
the ones `review_prs.py` computes on your laptop.

## How it fits together

```
participant ──(browser)──► missions/<username>.py ──► pull request
                                                         │
                     GitHub Action flies it headless ◄───┤  (instant ✅/❌ + score on the PR)
                                                         │
your laptop:  python review_prs.py  ◄────────────────────┘  downloads every PR's mission,
                                                             flies them in YOUR copy of the sim,
                                                             opens the 3D replay + leaderboard
```

- `sim/fake/codrone_edu/` is a stand-in for the real `codrone_edu` library, with the same function names, arguments
  and roughly the same timing (checked against codrone-edu 2.10). The same mission file flies the real drone.
- `sim/engine.py` is the drone model. `sim/course.py` does collisions and scoring. `course/fast_track_jr.json`
  is the course.
- `sim/viewer/` is the 3D replay (Three.js is bundled, so it works without internet).
- No pip installs anywhere. It only needs Python 3.9+ and, for `review_prs.py`, the GitHub CLI (`gh`).

## The printed handout

`docs/Fast-Track-Jr-Mission-Guide.pdf` is four pages: the mission and scoring, the course map with every measurement,
a one-page code cheat sheet, and how to submit (with hints). Print one per pair.

To rebuild it after changing the course (it needs Google Chrome):

```bash
python docs/guide/build_guide.py
```

The 3D picture comes straight from the simulator, and every number in the map and tables is read from
`course/fast_track_jr.json`, so the handout always matches the sim.

## One-time setup

1. Put this folder on GitHub (public is easiest, since anyone can then open a PR from a fork):
   ```bash
   gh repo create <you-or-club-org>/fast-track-jr --public --source . --push
   ```
   For a private repo, add each member as a collaborator instead.
2. **Settings → Actions → General → Fork pull request workflows**: GitHub asks you to approve workflow runs for
   first-time contributors. Either click **Approve and run** on each PR during the workshop, or loosen that
   setting beforehand. Without the Action, nothing breaks: participants just don't get instant feedback on the PR.
3. Optional: protect `main` (Settings → Branches) so nobody merges by accident.
4. Try it:
   ```bash
   python fly.py --course                          # look around the course
   python fly.py leader/solutions/*.py             # reference runs: 65 and 100 points
   python fly.py leader/test_missions/*.py         # typical beginner bugs (crash, typo, infinite loop…)
   ```

`leader/` is in `.gitignore`, so the reference solutions stay on your laptop and never get pushed.

## Suggested 60 minutes

| Time | What |
|---|---|
| 0–8 | The real Mission 2027 autonomous field. Put `python fly.py --course` on the projector, orbit around, walk through the map and the scoring. |
| 8–15 | Live demo: `python fly.py examples/live_demo.py --watch`. It crashes into the green keyhole. Add `drone.move_upward(40)`, save, and watch it re-fly. |
| 15–20 | Show the submit flow from the README: Add file → Create new file → Propose changes → Create PR. |
| 20–40 | Coding. The README has four hints, fold-out style. |
| 40–45 | Last PRs in. |
| 45–58 | Showcase: `python review_prs.py`. Race everyone, then replay the top 3 one at a time with their code on screen. |
| 58–60 | Winners. Next time: the same files on the real drones. |

## The showcase

```bash
python review_prs.py              # all open PRs
python review_prs.py 12 15        # just some
python review_prs.py --comment    # also post each score on its PR (asks first)
python review_prs.py --state all  # include merged/closed PRs (e.g. a later session)
python review_prs.py --realistic  # "what would a real drone do?" round, with drift and small errors
python review_prs.py --links links.txt            # PRs + Mission Lab share links (one per line)
python review_prs.py --links links.txt --no-prs   # share links only
```

In the replay:

| Key | Does |
|---|---|
| `Space` | play / pause |
| `N` / `P` | next / previous pilot (or click the leaderboard) |
| `1` `2` `3` `4` | broadcast · chase · top · drone camera |
| `←` `→` | seek 2 s (hold Shift for 10 s) |
| `C` | hide/show the code panel |
| `L` / `M` | labels / sound |
| `F` | fullscreen |

- **Race all** (the checkbox above the leaderboard) shows every drone at once. Untick it to watch one.
- The code panel highlights the line that's running. Lines that scored get a green `+10` chip, and the line
  that crashed gets 💥. That's the best moment to teach from.
- `print()` output shows up in the console panel at the moment it happened.

## Safety note

The simulator runs participants' Python on your computer. `review_prs.py` protects you in a few ways:

- It downloads **only** the mission files from each PR, never the PR's copy of the sim, so nobody can edit the scoring.
- It flags any mission that imports something besides `codrone_edu`, `time`, `math` or `random`, or calls things
  like `open`, `exec` or `eval`, and asks before flying it.
- Each mission runs in its own process, with no keyboard input and a 10-second infinite-loop watchdog.

It is **not** a sandbox. If something gets flagged, look at the PR first.

## What the simulator models

- Timing: `takeoff()` and `land()` take ~4 s each. `move_forward(d)` takes d/speed + 1.1 s. Turns use the same
  gyro loop as the library, so **they overshoot 1–3°**.
- Takeoff hovers at 80 cm. Default move speed is 0.5 m/s (as in library 2.10).
- `set_roll/pitch/yaw/throttle` values persist between `move()` calls, just like the real library. That's a
  classic bug, and the sim reproduces it.
- `get_height()` returns 999.9 above 150 cm, and `get_front_range()` returns 999 when nothing is within 150 cm.
- The sim scores the same way a referee would: it checks the direction through each gate, allows each gate 2×,
  counts only the final landing, and ignores anything after 3:00. If the drone's 15 cm sphere touches anything,
  that's a crash.
- `--realistic` adds constant drift (1.5–4 cm/s), ±7 % distance error, ±5 % turn error and ±7 cm takeoff
  height. Each pilot gets their own fixed random mix.

**Tuning:** the constants at the top of `sim/engine.py` (e.g. `STICK_CM_S`, how fast `set_pitch(50)` goes) are
educated guesses. Time a few moves on your real drone and adjust them.

**Changing the course:** edit `course/fast_track_jr.json` (positions and heights), then run
`python sim/mapgen.py` to redraw `docs/course-map.svg`, and update the numbers in the README.

## Training on the official Mission 2027 field

`course/fast_track_2027.json` is the full official solo field. It was laid out from the REC Foundation's *Game Element
Assembly & Field Setup Instructions* v1.0: three mats, the spiral of mini keyholes with its bonus, the tunnel on the yellow
keyhole's pole above the small cube, and the landing pad just past the red arch. Everything that's the same as the real
game scores the same.

```bash
python fly.py --course --field real                      # look around (hover things for measurements)
python fly.py training/you.py --field real               # fly a mission on it
python review_prs.py --field real                        # fly PRs on it
```

Start from `training/_template_real.py`, which lists every element's position. A few things aren't stated in the setup PDF,
so they're my best reading of the figures (see `notes` in the JSON). The main one: **which way you fly through the
yellow keyhole**. It's modelled as going forward/north, across the short mat section. If a referee reads it differently,
flip its `facing` in the JSON.

## Photo mode

Add `?photo=1&theme=light&labels=0` to a viewer URL for a clean white-background render (that's how the handout's picture
is made). `&cam=x,y,z,tx,ty,tz` (cm) sets the camera and `&drone=x,y,z,yaw` places a drone.

## Files

| Path | What |
|---|---|
| `README.md` | participant instructions (map, scoring, how to PR, hints) |
| `docs/Fast-Track-Jr-Mission-Guide.pdf` | 4-page printed handout (built by `docs/guide/build_guide.py`) |
| `docs/cheatsheet.md` | CoDrone EDU Python cheat sheet |
| `docs/course-map.svg` | generated course map |
| `missions/_template.py` | starter file participants copy |
| `examples/` | demo missions for the intro |
| `index.html`, `lab/` | the Mission Lab (GitHub Pages): editor + in-browser sim + replay |
| `fly.py` | fly mission file(s) locally → 3D replay (`--watch`, `--realistic`, `--course`) |
| `review_prs.py` | fly every PR → leaderboard + replay |
| `.github/workflows/simulate.yml` | flies each PR, reports the score and puts any bug on the PR itself |
| `course/fast_track_jr.json` | the workshop course |
| `course/fast_track_2027.json` | the official Mission 2027 solo field |
| `training/` | missions for the official field (`_template_real.py`) |
| `sim/` | simulator, fake `codrone_edu`, viewer |
| `runs/` | flight logs (git-ignored) |
| `leader/` | reference solutions + bug demos (git-ignored) |
