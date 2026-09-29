"""
Course geometry: collisions, "did it fly through?" checks, landing surfaces, and the scorer.

Everything is in centimetres. World frame (same as the drone's takeoff frame):
    x = forward from the start, y = left, z = up.

The drone is modelled as a sphere of radius DRONE_R whose centre sits BODY_DZ above
the drone's reported height (the height is measured at the bottom of the drone).
"""
import json
import math
import os

DRONE_R = 7.5      # CoDrone EDU is 13.9 cm across its prop guards
BODY_DZ = 2.5      # sphere centre above the bottom of the drone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_COURSE = os.path.join(ROOT, "course", "fast_track_jr.json")


def load_course(path=None):
    with open(path or DEFAULT_COURSE) as f:
        return json.load(f)


def _unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n)


class Element:
    label = "?"
    task = None

    def hits(self, p, r):
        return False

    def crossing(self, p0, p1):
        """Return 'pass', 'reverse' or None for the segment p0 -> p1 (sphere centres)."""
        return None

    def surface(self, x, y):
        return None


class Gate(Element):
    """Shared plane-crossing logic for arches and keyholes."""

    def __init__(self, d):
        self.id = d["id"]
        self.task = d["id"]
        self.label = d["label"]
        self.cx, self.cy = d["center"][0], d["center"][1]
        self.F = _unit(d["facing"])            # direction you must fly
        self.L = (-self.F[1], self.F[0])       # in-plane horizontal axis

    def local(self, p):
        dx, dy = p[0] - self.cx, p[1] - self.cy
        return dx * self.F[0] + dy * self.F[1], dx * self.L[0] + dy * self.L[1]

    def opening(self, p):
        raise NotImplementedError

    def crossing(self, p0, p1):
        n0, _ = self.local(p0)
        n1, _ = self.local(p1)
        if (n0 < 0) == (n1 < 0) or n0 == n1:
            return None
        s = n0 / (n0 - n1)
        pc = [p0[i] + (p1[i] - p0[i]) * s for i in range(3)]
        if not self.opening(pc):
            return None
        return "pass" if n0 < 0 else "reverse"


class Arch(Gate):
    """Fabric arch: a band between two half-ellipses standing on the floor.

    The manual's outer width (102") is measured across the feet, so the fabric band itself is
    modelled as uniformly (outer_h - inner_h) thick.
    """
    THICK = 4.0

    def __init__(self, d):
        super().__init__(d)
        band = d["outer_h"] - d["inner_h"]
        self.a_in, self.b_in = d["inner_w"] / 2, d["inner_h"]
        self.a_out, self.b_out = self.a_in + band, d["outer_h"]

    @staticmethod
    def _ell(u, z, a, b):
        # approximate signed distance to the ellipse (u/a)^2 + (z/b)^2 = 1  (>0 outside)
        rho = math.sqrt((u / a) ** 2 + (z / b) ** 2)
        if rho < 1e-9:
            return -min(a, b)
        g = math.hypot(u / (a * a * rho), z / (b * b * rho))
        return (rho - 1) / g

    def hits(self, p, r):
        n, u = self.local(p)
        dn = abs(n) - self.THICK / 2
        if dn > r or p[2] < -r:
            return False
        rr = math.sqrt(max(r * r - max(dn, 0) ** 2, 0.0))
        z = max(p[2], 0.0)
        return self._ell(u, z, self.a_in, self.b_in) > -rr and self._ell(u, z, self.a_out, self.b_out) < rr

    def opening(self, p):
        _, u = self.local(p)
        return p[2] >= 0 and (u / self.a_in) ** 2 + (p[2] / self.b_in) ** 2 < 1


class Keyhole(Gate):
    """A ring on a pole."""
    THICK = 3.0
    POLE_R = 1.5

    def __init__(self, d):
        super().__init__(d)
        self.cz = d["center"][2]
        self.r_in, self.r_out = d["inner_d"] / 2, d["outer_d"] / 2
        # most rings sit on top of their pole; some hang off the side of one (spiral, yellow keyhole)
        self.px, self.py = d.get("pole", [self.cx, self.cy])
        self.pole_top = d.get("pole_top", self.cz - self.r_out)

    def hits(self, p, r):
        n, u = self.local(p)
        q = math.hypot(u, p[2] - self.cz)
        dn = max(abs(n) - self.THICK / 2, 0)
        dq = max(self.r_in - q, q - self.r_out, 0)
        if math.hypot(dn, dq) < r:
            return True
        # the stand
        return math.hypot(p[0] - self.px, p[1] - self.py) < r + self.POLE_R and p[2] < self.pole_top + r

    def opening(self, p):
        _, u = self.local(p)
        return math.hypot(u, p[2] - self.cz) < self.r_in


class Cube(Element):
    """Hollow cube on the floor with a round hole in each side and a solid top."""
    WALL = 2.5

    def __init__(self, d):
        self.id = d["id"]
        self.task = d["id"]
        self.label = d["label"]
        self.cx, self.cy = d["center"]
        self.h = d["size"] / 2
        self.H = d["height"]
        self.hole_r = 0.0 if d.get("solid_sides") else d["hole_d"] / 2
        self.hole_z = self.H / 2
        self._inside = False
        self._entry = None

    def hits(self, p, r):
        dx, dy, z = p[0] - self.cx, p[1] - self.cy, p[2]
        h, H = self.h, self.H
        if abs(dx) > h + r + self.WALL or abs(dy) > h + r + self.WALL or z > H + r + 2 or z < -r:
            return False
        # side walls: (distance to wall plane, coordinate along the wall)
        for dn, along in ((abs(abs(dx) - h), dy), (abs(abs(dy) - h), dx)):
            dn -= self.WALL / 2
            if dn >= r:
                continue
            rr = math.sqrt(max(r * r - max(dn, 0) ** 2, 0.0))
            if math.hypot(along, z - self.hole_z) + rr < self.hole_r:
                continue  # sliding through the hole
            if abs(along) < h + rr and -rr < z < H + rr:
                return True
        # top
        dn = abs(z - H) - 1.0
        if dn < r:
            rr = math.sqrt(max(r * r - max(dn, 0) ** 2, 0.0))
            if abs(dx) < h + rr and abs(dy) < h + rr:
                return True
        return False

    def _face(self, p):
        dx, dy = p[0] - self.cx, p[1] - self.cy
        if p[2] >= self.H:
            return "top"
        ex, ey = abs(dx) - self.h, abs(dy) - self.h
        if ex >= ey:
            return "+x" if dx > 0 else "-x"
        return "+y" if dy > 0 else "-y"

    def _is_inside(self, p):
        return abs(p[0] - self.cx) < self.h and abs(p[1] - self.cy) < self.h and 0 <= p[2] < self.H

    def crossing(self, p0, p1):
        now = self._is_inside(p1)
        result = None
        if now and not self._inside:
            self._entry = self._face(p0)
        elif self._inside and not now:
            result = "pass" if self._face(p1) != self._entry else "same_side"
            self._entry = None
        self._inside = now
        return result

    def surface(self, x, y):
        if abs(x - self.cx) < self.h + 2 and abs(y - self.cy) < self.h + 2:
            return self.H
        return None


class Tunnel(Element):
    """Upright fabric tube hanging on a stand. Scores when you drop through it top -> bottom."""
    WALL = 1.0
    POLE_R = 1.5

    def __init__(self, d):
        self.id = d["id"]
        self.task = d["id"]
        self.label = d["label"]
        self.cx, self.cy = d["center"]
        self.R = d["diameter"] / 2
        self.zb = d["bottom"]
        self.zt = d["bottom"] + d["length"]
        self.zm = (self.zb + self.zt) / 2
        ox, oy = d.get("stand_offset", [45, 0])
        self.px, self.py = self.cx + ox, self.cy + oy
        n = math.hypot(ox, oy)
        self.ax, self.ay = self.cx + ox / n * self.R, self.cy + oy / n * self.R   # where the arm meets the tube
        self._armed = False

    def hits(self, p, r):
        dx, dy, z = p[0] - self.cx, p[1] - self.cy, p[2]
        q = math.hypot(dx, dy)
        dq = max(abs(q - self.R) - self.WALL / 2, 0)
        dz = max(self.zb - z, z - self.zt, 0)
        if math.hypot(dq, dz) < r:
            return True
        # stand pole
        if math.hypot(p[0] - self.px, p[1] - self.py) < r + self.POLE_R and z < self.zm + r:
            return True
        # horizontal arm from the pole to the tube
        vx, vy = self.px - self.ax, self.py - self.ay
        L2 = vx * vx + vy * vy
        s = max(0.0, min(1.0, ((p[0] - self.ax) * vx + (p[1] - self.ay) * vy) / L2))
        cxs, cys = self.ax + vx * s, self.ay + vy * s
        return math.sqrt((p[0] - cxs) ** 2 + (p[1] - cys) ** 2 + (z - self.zm) ** 2) < r + 1.2

    def crossing(self, p0, p1):
        q = math.hypot(p1[0] - self.cx, p1[1] - self.cy)
        if p0[2] > self.zt >= p1[2] and q < self.R:
            self._armed = True
        elif p0[2] <= self.zt < p1[2]:
            self._armed = False
        elif self._armed and p0[2] >= self.zb > p1[2]:
            self._armed = False
            if q < self.R:
                return "pass"
        return None


class LandingPad(Element):
    FOOT_R = 7.0      # footprint radius of the drone
    LINE = 0.6        # "the line of the ring is considered part of the bullseye"

    def __init__(self, d):
        self.id = d["id"]
        self.label = d["label"]
        self.cx, self.cy = d["center"]
        self.R = d["diameter"] / 2
        self.Rb = d["bullseye_d"] / 2

    def landing(self, x, y):
        d = math.hypot(x - self.cx, y - self.cy)
        if d + self.FOOT_R <= self.Rb + self.LINE:
            return "land_bullseye"
        if d - self.FOOT_R < self.R:
            return "land_pad"
        return None


TYPES = {"arch": Arch, "keyhole": Keyhole, "cube": Cube, "tunnel": Tunnel, "landing_pad": LandingPad}


class Course:
    def __init__(self, data):
        self.data = data
        self.elements = [TYPES[e["type"]](e) for e in data["elements"]]
        self.solids = [e for e in self.elements if not isinstance(e, LandingPad)]
        self.pads = [e for e in self.elements if isinstance(e, LandingPad)]
        self.cubes = [e for e in self.elements if isinstance(e, Cube)]
        z = data["flight_zone"]
        self.zone = (z["x"], z["y"], z["z_max"])

    def reset_tracking(self):
        for e in self.elements:
            if isinstance(e, Cube):
                e._inside, e._entry = False, None
            if isinstance(e, Tunnel):
                e._armed = False

    def collision(self, c, r=DRONE_R):
        """Label of whatever the sphere at c touches, or None."""
        for e in self.solids:
            if e.hits(c, r):
                return e.label
        (x0, x1), (y0, y1), zmax = self.zone
        if not (x0 < c[0] < x1 and y0 < c[1] < y1) or c[2] > zmax:
            return "the safety net (left the flight zone)"
        return None

    def crossings(self, p0, p1):
        out = []
        for e in self.solids:
            k = e.crossing(p0, p1)
            if k:
                out.append((e, k))
        return out

    def surface(self, x, y):
        best = 0.0
        for e in self.cubes:
            s = e.surface(x, y)
            if s is not None:
                best = max(best, s)
        return best

    def landing_task(self, x, y, z):
        for c in self.cubes:
            if c.surface(x, y) is not None and abs(z - c.H) < 3:
                return "land_cube"
        if z < 3:
            for p in self.pads:
                k = p.landing(x, y)
                if k:
                    return k
        return None

    def ray(self, o, d, max_range=150.0, step=1.5):
        """Distance from o along unit vector d to the first solid thing (or the floor)."""
        s = 0.0
        (x0, x1), (y0, y1), zmax = self.zone
        while s <= max_range:
            p = (o[0] + d[0] * s, o[1] + d[1] * s, o[2] + d[2] * s)
            if p[2] <= 0:
                return s
            # gym walls sit 1 m outside the flight zone
            if not (x0 - 100 < p[0] < x1 + 100 and y0 - 100 < p[1] < y1 + 100):
                return s
            for e in self.solids:
                if e.hits(p, 0.5):
                    return s
            s += step
        return None


class Scorer:
    def __init__(self, course_data):
        self.tasks = {t["id"]: t for t in course_data["tasks"]}
        self.limit = course_data["time_limit_s"]
        self.counts = {k: 0 for k in self.tasks}
        self.groups_used = set()
        self.events = []

    @property
    def total(self):
        return sum(e["points"] for e in self.events)

    def award(self, task_id, t, line=None):
        task = self.tasks[task_id]
        if t > self.limit:
            return None, "after the 3:00 buzzer — doesn't count"
        g = task.get("group")
        if g and g in self.groups_used:
            return None, "already scored"
        if self.counts[task_id] >= task["max"]:
            return None, f"already scored {task['max']}x (max)"
        self.counts[task_id] += 1
        if g:
            self.groups_used.add(g)
        ev = {"t": round(t, 2), "task": task_id, "label": task["label"], "points": task["points"], "line": line}
        self.events.append(ev)
        return ev, None

    def breakdown(self):
        rows = []
        for tid, task in self.tasks.items():
            n = self.counts[tid]
            rows.append({"task": tid, "label": task["label"], "points": task["points"],
                         "count": n, "max": task["max"], "bonus": bool(task.get("bonus")),
                         "group": task.get("group")})
        return rows
