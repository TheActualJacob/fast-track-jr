"""
Fly one mission file inside the simulator and return its flight log (a dict).

Shared by sim/bootstrap.py (a subprocess on your computer) and the browser Mission Lab
(Pyodide in a web worker). Expects sim/fake to be first on sys.path so that
`import codrone_edu` gets the simulated library.
"""
import datetime
import io
import os
import runpy
import sys
import time
import traceback

from sim import engine

INFINITE_LOOP_MSG = ("Your program ran for a long time without finishing. Is there an infinite loop "
                     "(e.g. `while True:`) that never calls the drone or never breaks?")


class ConsoleTee(io.TextIOBase):
    """Collect print() output with the (virtual) time and code line it came from."""

    def __init__(self, session, real):
        self.S, self.real, self.buf = session, real, ""

    def writable(self):
        return True

    def write(self, s):
        if self.real is not None:
            self.real.write(s)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if len(self.S.console) < 2000:
                self.S.console.append({"t": round(self.S.t, 2), "text": line[:300], "line": self.S.caller_line()})
        return len(s)

    def flush(self):
        if self.real is not None:
            self.real.flush()


def _error_line(S, exc):
    line = None
    for fr in traceback.extract_tb(exc.__traceback__):
        if os.path.realpath(fr.filename) == S.mission:
            line = fr.lineno
    return line


def run_mission(mission, course, name=None, realistic=False, seed=0, echo=True, root=None):
    mission = os.path.abspath(mission)
    name = name or os.path.splitext(os.path.basename(mission))[0]
    with open(mission, encoding="utf-8", errors="replace") as f:
        source = f.read()

    S = engine.Session(course, mission, name=name, realistic=realistic, seed=seed)

    # virtual clock: sleeping flies the drone instead of waiting
    saved = (time.sleep, time.time, time.monotonic, time.perf_counter)
    epoch = time.time()

    def v_sleep(seconds):
        S.advance(float(seconds))

    def v_time():
        S.advance(0.001)  # even a busy loop that only reads the clock moves time forward
        return epoch + S.t

    def v_mono():
        S.advance(0.001)
        return 1000.0 + S.t

    time.sleep, time.time, time.monotonic, time.perf_counter = v_sleep, v_time, v_mono, v_mono

    real_stdout = sys.stdout
    sys.stdout = ConsoleTee(S, real_stdout if echo else None)
    mission_dir = os.path.dirname(mission)
    sys.path.insert(2, mission_dir)
    end_reason, end_message = "finished", ""
    try:
        runpy.run_path(mission, run_name="__main__")
    except engine.SimEnded as e:
        end_reason, end_message = e.reason, e.message
    except SystemExit:
        pass
    except KeyboardInterrupt as e:
        end_reason, end_message = "error", INFINITE_LOOP_MSG
        line = _error_line(S, e) or S.cur_line
        S.cur_line = line
        S.error = {"type": "InfiniteLoop", "message": INFINITE_LOOP_MSG, "line": line, "traceback": ""}
        S.event("error", INFINITE_LOOP_MSG)
    except BaseException as e:  # a bug in the participant's code
        end_reason = "error"
        line = _error_line(S, e)
        if isinstance(e, SyntaxError) and e.lineno:
            line = e.lineno
        tb = "".join(traceback.format_exception_only(type(e), e)).strip()
        S.error = {"type": type(e).__name__, "message": str(e), "line": line, "traceback": tb}
        S.cur_line = line
        S.event("error", f"{type(e).__name__}: {e}")
        end_message = tb
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        sys.stdout = real_stdout
        time.sleep, time.time, time.monotonic, time.perf_counter = saved
        if mission_dir in sys.path:
            sys.path.remove(mission_dir)

    result = S.finish()
    if root and mission.startswith(root):
        mission_file = os.path.relpath(mission, root)
    else:
        mission_file = os.path.basename(mission)
    return {
        "version": 1,
        "name": name,
        "mission_file": mission_file,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "realistic": realistic,
        "end_reason": end_reason,
        "end_message": end_message,
        "result": result,
        "crash": S.crash,
        "error": S.error,
        "course": course,
        "source": source,
        "frames": S.frames,
        "events": S.events,
        "calls": S.calls,
        "console": S.console,
        "leds": S.leds,
        "sounds": S.sounds,
    }
