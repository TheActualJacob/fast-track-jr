"""
Runs ONE mission file inside the simulator and writes a flight log (JSON).

Always started in its own process by sim/runner.py, because it swaps out the `codrone_edu`
package and the clock (time.sleep / time.time) for virtual versions.

    python sim/bootstrap.py MISSION.py OUT.json [--name NAME] [--realistic] [--seed N] [--course FILE]
"""
import argparse
import json
import os
import sys
import threading
import _thread

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "sim", "fake"), ROOT]   # our codrone_edu wins over a real install

from sim.course import load_course  # noqa: E402
from sim.runcore import run_mission  # noqa: E402

WALL_CLOCK_LIMIT = 10.0   # real seconds before we assume an infinite loop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mission")
    ap.add_argument("out")
    ap.add_argument("--name", default=None)
    ap.add_argument("--realistic", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--course", default=None)
    a = ap.parse_args()

    # if the program spins forever without touching the drone, interrupt it
    finished = threading.Event()

    def watchdog():
        if not finished.wait(WALL_CLOCK_LIMIT):
            _thread.interrupt_main()

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        log = run_mission(a.mission, load_course(a.course), name=a.name, realistic=a.realistic,
                          seed=a.seed, root=ROOT)
    finally:
        finished.set()

    tmp = a.out + ".tmp"
    with open(tmp, "w") as f:
        json.dump(log, f, separators=(",", ":"))
    os.replace(tmp, a.out)


if __name__ == "__main__":
    main()
