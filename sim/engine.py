"""
The virtual CoDrone EDU.

We don't simulate propellers. The real drone's firmware already runs a velocity/position
loop off its optical-flow sensor, so from Python it behaves like a point that *tries* to hit
whatever velocity or position you ask for, with a bit of lag. That's what this models.

Time is virtual: every blocking library call (and time.sleep) advances the simulation
clock instead of waiting, so a 3-minute mission simulates in well under a second.

All distances are in cm, angles in degrees, time in seconds.
"""
import math
import os
import random
import sys

from sim.course import BODY_DZ, Course, Scorer

# ---------------------------------------------------------------------------------------
# Tunables. These are sensible guesses; calibrate them against your real drone if you like
# (e.g. time how far set_pitch(50) + move(1) actually goes on the practice mat).
# ---------------------------------------------------------------------------------------
STICK_CM_S = 1.0        # horizontal cm/s per stick unit: set_pitch(50) ~ 50 cm/s
THROTTLE_CM_S = 0.8     # vertical cm/s per throttle unit
YAW_DEG_S = 1.5         # deg/s per yaw unit
VEL_TAU = 0.22          # s, how sluggishly the drone reaches a new velocity
YAW_TAU = 0.12
MAX_ACCEL = 350.0       # cm/s^2
POS_KP = 2.2            # position-hold stiffness, 1/s
POS_DECEL = 120.0       # cm/s^2 used to brake before a position target
TAKEOFF_CLIMB = 60.0    # cm/s
LAND_DESCENT = 35.0     # cm/s
GRAVITY = 981.0
BATTERY_DRAIN = 0.24    # %/s while the motors spin (~7 min flight)
DT = 0.01               # physics step
FRAME_EVERY = 4         # record every 4th step -> 25 frames/s for the replay

_SESSION = None


def current():
    if _SESSION is None:
        raise RuntimeError("The simulator isn't running. Use:  python fly.py missions/<you>.py")
    return _SESSION


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def rot(x, y, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return c * x - s * y, s * x + c * y


class SimEnded(BaseException):
    """Stops the participant's program (BaseException so a bare `except Exception` can't eat it)."""

    def __init__(self, reason, message=""):
        super().__init__(message or reason)
        self.reason = reason
        self.message = message


class Session:
    def __init__(self, course_data, mission_path, name="pilot", realistic=False, seed=0):
        global _SESSION
        _SESSION = self
        self.cd = course_data
        self.course = Course(course_data)
        self.scorer = Scorer(course_data)
        self.mission = os.path.realpath(mission_path)
        self.name = name
        self.realistic = realistic
        rng = random.Random(seed)
        self.rng = rng

        st = course_data["start"]
        self.t = 0.0
        self.p = [float(st["x"]), float(st["y"]), 0.0]
        self.v = [0.0, 0.0, 0.0]
        self.yaw = float(st["yaw"])
        self.yaw_rate = 0.0
        self.home = (self.p[0], self.p[1], 0.0, self.yaw)        # takeoff frame (resets at each takeoff)
        self.origin = None                                        # first takeoff frame (send_absolute_position)
        self.mode = "landed"          # landed | takeoff | flying | landing | falling | crashed | dropped
        self.ctrl = "hover"           # hover | sticks | position
        self.sticks = [0, 0, 0, 0]    # roll, pitch, yaw, throttle
        self.hold = list(self.p)
        self.target = None
        self.target_speed = 50.0
        self.yaw_target = None
        self.yaw_speed = 120.0
        self.takeoff_target = 0.0
        self.takeoff_t0 = 0.0
        self.t_landed = None
        self.fall_result = "crashed"
        self.land_line = None
        self.tilt = [0.0, 0.0]        # roll, pitch (visual only)
        self.tumble = [0.0, 0.0]
        self.flip = None              # (t0, axis sign)
        self.battery = 100.0
        self.led = [255, 30, 30]

        # realism knobs (only with --realistic): the real drone never flies perfectly
        if realistic:
            a = rng.uniform(0, 360)
            m = rng.uniform(1.5, 4.0)
            self.drift = (m * math.cos(math.radians(a)), m * math.sin(math.radians(a)))
            self.move_scale = rng.uniform(0.93, 1.07)
            self.yaw_scale = rng.uniform(0.95, 1.05)
            self.takeoff_h = course_data["takeoff_height"] + rng.uniform(-7, 7)
        else:
            self.drift = (0.0, 0.0)
            self.move_scale = 1.0
            self.yaw_scale = 1.0
            self.takeoff_h = float(course_data["takeoff_height"])

        # combo tasks like the spiral bonus: gates flown in a row with nothing else scored in between
        self.sequences = {t["id"]: {"seq": t["sequence"], "i": 0}
                          for t in course_data["tasks"] if t.get("sequence")}
        self.frames = []
        self.events = []
        self.calls = []
        self.console = []
        self.sounds = []
        self.leds = [{"t": 0.0, "rgb": list(self.led)}]
        self.warned = set()
        self.depth = 0
        self.cur_line = None
        self.cur_outer = []
        self.paired = False
        self.closed = False
        self.ever_flew = False
        self.crash = None
        self.error = None
        self.step_i = 0
        self.hard_limit = course_data["time_limit_s"] + 30
        self._prev_c = None
        self._record()

    # ---------------------------------------------------------------- bookkeeping
    def caller_lines(self):
        """Line numbers in the mission file on the current call stack, innermost first."""
        out = []
        f = sys._getframe(1)
        while f is not None:
            if os.path.realpath(f.f_code.co_filename) == self.mission and f.f_lineno not in out:
                out.append(f.f_lineno)
            f = f.f_back
        return out

    def caller_line(self):
        lines = self.caller_lines()
        return lines[0] if lines else None

    def event(self, kind, text, **extra):
        ev = {"t": round(self.t, 2), "type": kind, "text": text, "line": self.cur_line}
        if self.cur_outer:
            ev["outer"] = list(self.cur_outer)
        ev.update(extra)
        self.events.append(ev)
        return ev

    def warn_once(self, key, text):
        if key in self.warned:
            return
        self.warned.add(key)
        self.event("warn", text)
        print(f"[sim] ⚠️  {text}", file=sys.__stderr__)

    def _record(self):
        spinning = 1 if self.mode in ("takeoff", "flying", "landing") else 0
        roll, pitch = self.tilt
        if self.flip is not None:
            k = (self.t - self.flip[0]) / 0.6
            if 0 <= k <= 1:
                ang = 360 * (0.5 - 0.5 * math.cos(math.pi * k))
                if self.flip[1] in ("left", "right"):
                    roll += ang if self.flip[1] == "right" else -ang
                else:
                    pitch += ang if self.flip[1] == "front" else -ang
        self.frames.append([round(self.t, 3), round(self.p[0], 1), round(self.p[1], 1), round(self.p[2], 1),
                            round(self.yaw, 1), round(roll, 1), round(pitch, 1), spinning])

    # ---------------------------------------------------------------- time
    def advance(self, dt):
        if dt is None or dt <= 0:
            return
        end = self.t + dt
        while self.t < end - 1e-9:
            h = min(DT, end - self.t)
            self._step(h)
            self.t += h
            self.step_i += 1
            if self.step_i % FRAME_EVERY == 0:
                self._record()
            self._check()
            if self.t > self.hard_limit:
                raise SimEnded("timeout", f"Stopped the program at {self.hard_limit:.0f} s of flight time "
                                          "(the match is only 3:00).")

    # ---------------------------------------------------------------- physics
    def _step(self, h):
        m = self.mode
        if m in ("landed", "crashed", "dropped"):
            self.v = [0.0, 0.0, 0.0]
            self.yaw_rate = 0.0
            return

        if m == "falling":
            self.v[2] -= GRAVITY * h
            self.v[0] *= 1 - 1.5 * h
            self.v[1] *= 1 - 1.5 * h
            for i in range(3):
                self.p[i] += self.v[i] * h
            self.tilt[0] += self.tumble[0] * h
            self.tilt[1] += self.tumble[1] * h
            ground = self.course.surface(self.p[0], self.p[1])
            if self.p[2] <= ground:
                self.p[2] = ground
                self.v = [0.0, 0.0, 0.0]
                self.mode = self.fall_result
                if self.mode == "landed":
                    self.tilt = [0.0, 0.0]
                    self.t_landed = self.t
                else:
                    # come to rest on the floor: sometimes upside down, usually just tipped over
                    self.tilt = [180.0 if self.rng.random() < 0.35 else self.rng.uniform(-18, 18),
                                 self.rng.uniform(-12, 12)]
            return

        self.battery = max(0.0, self.battery - BATTERY_DRAIN * h)
        vdes = [0.0, 0.0, 0.0]
        rate_des = 0.0

        if m == "takeoff":
            vdes[0] = POS_KP * (self.hold[0] - self.p[0])
            vdes[1] = POS_KP * (self.hold[1] - self.p[1])
            if self.t - self.takeoff_t0 > 0.35:  # motors spool up first
                vdes[2] = max(-TAKEOFF_CLIMB, min(TAKEOFF_CLIMB, 2.5 * (self.takeoff_target - self.p[2])))
            if abs(self.takeoff_target - self.p[2]) < 0.6 and self.t - self.takeoff_t0 > 1.2:
                self.mode = "flying"
                self.ctrl = "hover"
                self.hold = list(self.p)
                self.hold[2] = self.takeoff_target
        elif m == "landing":
            ground = self.course.surface(self.p[0], self.p[1])
            vdes[0] = POS_KP * (self.hold[0] - self.p[0])
            vdes[1] = POS_KP * (self.hold[1] - self.p[1])
            vdes[2] = -min(LAND_DESCENT, max(12.0, 1.6 * (self.p[2] - ground)))
            if self.p[2] <= ground + 0.3:
                self.p[2] = ground
                self.v = [0.0, 0.0, 0.0]
                self.mode = "landed"
                self.tilt = [0.0, 0.0]
                self.t_landed = self.t
                ev = self.event("info", "Touched down.")
                ev["line"] = self.land_line
                return
        elif m == "flying":
            if self.ctrl == "sticks":
                r, pch, yw, th = self.sticks
                bx = pch * STICK_CM_S * self.move_scale
                by = -r * STICK_CM_S * self.move_scale
                vdes[0], vdes[1] = rot(bx, by, self.yaw)
                vdes[2] = th * THROTTLE_CM_S
                rate_des = yw * YAW_DEG_S * self.yaw_scale
            else:
                tgt = self.target if self.ctrl == "position" else self.hold
                spd = self.target_speed if self.ctrl == "position" else 60.0
                e = [tgt[i] - self.p[i] for i in range(3)]
                d = math.sqrt(sum(x * x for x in e))
                if d > 1e-6:
                    vm = min(spd, math.sqrt(2 * POS_DECEL * d), POS_KP * d)
                    vdes = [x / d * vm for x in e]
            if self.yaw_target is not None and self.ctrl != "sticks":
                err = wrap180(self.yaw_target - self.yaw)
                rate_des = max(-self.yaw_speed, min(self.yaw_speed, 4.0 * err))
            vdes[0] += self.drift[0]
            vdes[1] += self.drift[1]

        # the firmware chases the requested velocity with some lag and limited acceleration
        a = 1 - math.exp(-h / VEL_TAU)
        acc = [0.0, 0.0, 0.0]
        for i in range(3):
            dv = (vdes[i] - self.v[i]) * a
            dv = max(-MAX_ACCEL * h, min(MAX_ACCEL * h, dv))
            self.v[i] += dv
            acc[i] = dv / h
        self.yaw_rate += (rate_des - self.yaw_rate) * (1 - math.exp(-h / YAW_TAU))
        for i in range(3):
            self.p[i] += self.v[i] * h
        self.yaw = wrap180(self.yaw + self.yaw_rate * h)

        # lean into the motion (purely cosmetic)
        bvx, bvy = rot(self.v[0], self.v[1], -self.yaw)
        bax, bay = rot(acc[0], acc[1], -self.yaw)
        tp = max(-28.0, min(28.0, 0.06 * bvx + 0.035 * bax))
        tr = max(-28.0, min(28.0, -0.06 * bvy - 0.035 * bay))
        k = 1 - math.exp(-h / 0.08)
        self.tilt[1] += (tp - self.tilt[1]) * k
        self.tilt[0] += (tr - self.tilt[0]) * k

    def _check(self):
        m = self.mode
        c = (self.p[0], self.p[1], self.p[2] + BODY_DZ)
        if m in ("takeoff", "flying", "landing"):
            skip_cube_top = m in ("takeoff", "landing") and self.course.surface(self.p[0], self.p[1]) > 0
            hit = None
            for e in self.course.solids:
                if skip_cube_top and e in self.course.cubes:
                    continue
                if e.hits(c, 7.5):
                    hit = e.label
                    break
            if hit is None:
                (x0, x1), (y0, y1), zmax = self.course.zone
                if not (x0 < c[0] < x1 and y0 < c[1] < y1) or c[2] > zmax:
                    hit = "the safety net (left the flight zone)"
            if hit is None and m == "flying" and self.p[2] < -0.5:
                hit = "the floor"
            if hit:
                self._crash(hit)
            if m == "takeoff" and self.p[2] > 1.0 and self.scorer.counts["takeoff"] == 0:
                self._award("takeoff")
            if self._prev_c is not None:
                for el, kind in self.course.crossings(self._prev_c, c):
                    if kind == "pass":
                        self._passed(el.task)
                    elif kind == "reverse":
                        self.event("warn", f"Went through the {el.label} backwards — no points. "
                                           f"Fly through it in the direction of the arrow.")
                    elif kind == "same_side" and el.task in self.scorer.tasks:
                        self.event("warn", f"Went into the {el.label} and came back out the same side — "
                                           f"leave through a different side to score.")
        self._prev_c = c

    def _passed(self, task):
        if task in self.scorer.tasks:
            self._award(task)
        for combo, st in self.sequences.items():
            seq = st["seq"]
            if task == seq[st["i"]]:
                st["i"] += 1
                if st["i"] == len(seq):
                    st["i"] = 0
                    self._award(combo)
            else:
                st["i"] = 1 if task == seq[0] else 0

    def _award(self, task):
        ev, why = self.scorer.award(task, self.t, self.cur_line)
        if ev:
            self.event("score", f"+{ev['points']}  {ev['label']}", task=task, points=ev["points"])
        else:
            self.event("info", f"{self.scorer.tasks[task]['label']}: {why}")

    def _crash(self, what):
        self.crash = {"t": round(self.t, 2), "what": what, "line": self.cur_line}
        if self.cur_outer:
            self.crash["outer"] = list(self.cur_outer)
        self.event("crash", f"CRASH! Hit {what}.", what=what)
        self.mode = "falling"
        self.fall_result = "crashed"
        self.v = [self.v[0] * -0.3, self.v[1] * -0.3, min(self.v[2], 0.0)]
        self.tumble = [self.rng.uniform(200, 500) * self.rng.choice((-1, 1)), self.rng.uniform(100, 400)]
        t_end = self.t + 3
        while self.mode == "falling" and self.t < t_end:
            self._step(DT)
            self.t += DT
            self.step_i += 1
            if self.step_i % FRAME_EVERY == 0:
                self._record()
        self._record()
        raise SimEnded("crash", f"Crashed into {what}")

    # ---------------------------------------------------------------- commands
    def flying(self):
        return self.mode in ("flying", "takeoff")

    def cmd_takeoff(self):
        if self.mode in ("flying", "takeoff", "landing"):
            return
        if self.mode in ("crashed",):
            return
        self.mode = "takeoff"
        self.ever_flew = True
        self.takeoff_t0 = self.t
        self.tilt = [0.0, 0.0]
        ground = self.course.surface(self.p[0], self.p[1])
        self.p[2] = ground
        self.hold = list(self.p)
        self.takeoff_target = ground + self.takeoff_h
        self.home = (self.p[0], self.p[1], ground, self.yaw)
        if self.origin is None:
            self.origin = self.home
        self.ctrl = "hover"
        self.sticks = [0, 0, 0, 0]
        self.yaw_target = None

    def cmd_land(self):
        if self.mode not in ("flying", "takeoff"):
            return
        self.mode = "landing"
        self.land_line = self.cur_line
        self.ctrl = "hover"
        self.sticks = [0, 0, 0, 0]
        self.hold = list(self.p)
        self.yaw_target = None

    def cmd_stop(self):
        if self.mode in ("landed", "crashed", "dropped"):
            return
        drop = self.p[2] - self.course.surface(self.p[0], self.p[1])
        self.event("warn", f"Emergency stop! Motors off {drop:.0f} cm above the ground.")
        self.mode = "falling"
        self.fall_result = "landed" if drop < 20 else "dropped"
        self.tumble = [0.0, 0.0] if drop < 20 else [self.rng.uniform(150, 350), self.rng.uniform(80, 250)]

    def cmd_sticks(self, roll, pitch, yaw, throttle):
        self.sticks = [roll, pitch, yaw, throttle]
        if self.mode != "flying":
            return
        if any(self.sticks):
            self.ctrl = "sticks"
            self.yaw_target = None
        else:
            self.cmd_hover()

    def cmd_hover(self):
        if self.mode != "flying":
            return
        if self.ctrl != "hover":
            # stop about where the current momentum carries us instead of snapping back
            self.hold = [self.p[i] + self.v[i] * VEL_TAU for i in range(3)]
        self.ctrl = "hover"
        self.sticks = [0, 0, 0, 0]

    def cmd_relative(self, fwd, left, up, speed):
        """Move by (fwd, left, up) cm in the drone's own frame. speed in cm/s."""
        if self.mode != "flying":
            return
        wx, wy = rot(fwd * self.move_scale, left * self.move_scale, self.yaw)
        self.target = [self.p[0] + wx, self.p[1] + wy, self.p[2] + up * self.move_scale]
        self.target_speed = max(1.0, speed)
        self.ctrl = "position"
        self.hold = list(self.target)

    def cmd_absolute(self, x, y, z, speed, heading, yaw_speed):
        """Absolute position (cm) in the first-takeoff frame."""
        if self.mode != "flying":
            return
        ox, oy, oz, oyaw = self.origin or self.home
        wx, wy = rot(x, y, oyaw)
        self.target = [ox + wx, oy + wy, oz + z]
        self.target_speed = max(1.0, speed)
        self.ctrl = "position"
        self.hold = list(self.target)
        if yaw_speed:
            self.yaw_target = wrap180(oyaw + heading)
            self.yaw_speed = abs(yaw_speed)

    def cmd_flip(self, direction):
        if self.mode != "flying":
            return
        self.flip = (self.t, direction)
        self.event("info", f"Flip ({direction})!")

    # ---------------------------------------------------------------- sensors
    def local_pos(self):
        hx, hy, hz, hyaw = self.home
        x, y = rot(self.p[0] - hx, self.p[1] - hy, -hyaw)
        return x, y, self.p[2] - hz

    def angle_z(self):
        return wrap180(self.yaw - self.home[3])

    def height(self):
        if self.mode in ("landed", "crashed", "dropped"):
            return 0.0
        return max(0.0, self.p[2] - self.course.surface(self.p[0], self.p[1]))

    def front_range(self):
        dx, dy = rot(1.0, 0.0, self.yaw)
        o = (self.p[0] + dx * 7.0, self.p[1] + dy * 7.0, self.p[2] + BODY_DZ)
        return self.course.ray(o, (dx, dy, 0.0), max_range=150.0)

    def ground_colors(self):
        if self.mode not in ("landed", "dropped"):
            return None
        x, y = self.p[0], self.p[1]
        for pad in self.course.pads:
            k = pad.landing(x, y)
            if k == "land_bullseye":
                return "red"
            if k == "land_pad":
                return "black"
        if self.p[2] > 1:
            return "red"  # on top of a cube
        for m in self.cd["mats"]:
            if m["x"][0] <= x <= m["x"][1] and m["y"][0] <= y <= m["y"][1]:
                return "white"
        return "gray"

    # ---------------------------------------------------------------- the end
    def finish(self):
        # let a landing / takeoff / fall that is still happening play out
        try:
            waited = 0.0
            while self.mode in ("landing", "takeoff", "falling") and waited < 10:
                self.advance(0.1)
                waited += 0.1
            if self.mode == "flying":
                self.event("warn", "Your program ended while the drone was still in the air. "
                                   "No landing points — end with drone.land().")
                self.advance(2.0)
        except SimEnded:
            pass
        landing = None
        if self.mode == "landed" and self.ever_flew and self.crash is None:
            landing = self.course.landing_task(self.p[0], self.p[1], self.p[2])
            if landing:
                ev, why = self.scorer.award(landing, self.t_landed, None)
                if ev:
                    self.events.append({"t": round(self.t_landed, 2), "type": "score",
                                        "text": f"+{ev['points']}  {ev['label']}", "task": landing,
                                        "points": ev["points"], "line": None})
                else:
                    self.events.append({"t": round(self.t_landed, 2), "type": "info",
                                        "text": f"Landing: {why}", "line": None})
            else:
                self.events.append({"t": round(self.t_landed, 2), "type": "info",
                                    "text": "Landed on the floor — no landing points.", "line": None})
        self._record()
        self.events.sort(key=lambda e: e["t"])
        if self.crash:
            end_t = self.crash["t"]
        elif self.mode == "landed" and self.t_landed is not None:
            end_t = self.t_landed
        else:
            end_t = self.t
        return {
            "score": self.scorer.total,
            "finish_time": round(end_t, 2),
            "status": ("crashed" if self.crash else
                       "error" if self.error else
                       "landed" if self.mode == "landed" and self.ever_flew else
                       "never took off" if not self.ever_flew else
                       "still flying" if self.mode == "flying" else self.mode),
            "landing": landing,
            "breakdown": self.scorer.breakdown(),
            "scores": self.scorer.events,
        }
