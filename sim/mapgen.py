"""
Draw docs/course-map.svg from course/fast_track_jr.json (top view + heights).

    python sim/mapgen.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sim.course import load_course  # noqa: E402

S = 1.32                         # px per cm
TOP_X0, TOP_Y0 = 205, 84         # top-left of the top view
Y_MIN, Y_MAX = -330, 125         # sim y range shown (left = +y)
X_MIN, X_MAX = -40, 300          # sim x range shown (up = +x)
W, H = 1165, 700
BG, INK, DIM, FAINT = "#0f141b", "#e8ecf1", "#8a94a3", "#2a323d"


def P(x, y):
    """sim (x forward, y left) -> page. Forward is UP the page, right is to the right."""
    return TOP_X0 + (Y_MAX - y) * S, TOP_Y0 + (X_MAX - x) * S


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, t, size=12, fill=INK, anchor="start", weight=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{esc(t)}</text>')


def arrow(x1, y1, x2, y2, color, width=2.5):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{width}" marker-end="url(#a-{color[1:]})"/>')


def main():
    c = load_course()
    el = {e["id"]: e for e in c["elements"]}
    colors = {e["color"] for e in c["elements"]} | {"#ff5a5a", INK, DIM}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
           "<defs>"]
    for col in colors:
        out.append(f'<marker id="a-{col[1:]}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" '
                   f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    out.append("</defs>")
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>')
    out.append(text(24, 36, "FAST TRACK JR. — course map", 20, INK, weight=800))
    out.append(text(24, 56, "Top view. Distances in cm, measured from where the drone starts (0, 0), "
                            "facing up the page.", 12, DIM))

    # grid every 25 cm, labels every 50
    gx0, gy0 = P(X_MIN, Y_MAX)
    gx1, gy1 = P(X_MAX, Y_MIN)
    for x in range(-25, X_MAX + 1, 25):
        a, b = P(x, Y_MAX)[1], None
        out.append(f'<line x1="{gx0:.1f}" y1="{a:.1f}" x2="{gx1:.1f}" y2="{a:.1f}" stroke="{FAINT}" '
                   f'stroke-width="{1 if x % 50 else 1.4}"/>')
        if x % 50 == 0:
            out.append(text(gx1 + 6, a + 4, f"{x}", 10, DIM, "start"))
    for y in range(-325, Y_MAX + 1, 25):
        a = P(0, y)[0]
        out.append(f'<line x1="{a:.1f}" y1="{gy0:.1f}" x2="{a:.1f}" y2="{gy1:.1f}" stroke="{FAINT}" '
                   f'stroke-width="{1 if y % 50 else 1.4}"/>')
        if y % 50 == 0:
            lbl = "0" if y == 0 else (f"{-y} R" if y < 0 else f"{y} L")
            out.append(text(a, gy1 + 16, lbl, 10, DIM, "middle"))
    out.append(text(gx1 + 6, TOP_Y0 - 10, "↑ forward (x)", 10, DIM, "start"))
    out.append(text(gx1, gy1 + 30, "right →  (y counts negative to the right)", 10, DIM, "end"))

    # mats + start zone + pilot station
    for m in c["mats"]:
        x0, y0 = P(m["x"][1], m["y"][1])
        x1, y1 = P(m["x"][0], m["y"][0])
        out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" fill="#9aa0a8" '
                   f'fill-opacity="0.22" stroke="#9aa0a8" stroke-opacity="0.5"/>')
    sz = c["start_zone"]
    x0, y0 = P(sz["x"][1], sz["y"][1])
    x1, y1 = P(sz["x"][0], sz["y"][0])
    out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" fill="#2fd16f" fill-opacity="0.35"/>')

    # elements
    for e in c["elements"]:
        col = e["color"]
        if e["type"] == "arch":
            band = e["outer_h"] - e["inner_h"]
            half = e["inner_w"] / 2 + band
            fx, fy = e["facing"]
            lx, ly = -fy, fx
            cx, cy = e["center"]
            a = P(cx + lx * half, cy + ly * half)
            b = P(cx - lx * half, cy - ly * half)
            ia = P(cx + lx * e["inner_w"] / 2, cy + ly * e["inner_w"] / 2)
            ib = P(cx - lx * e["inner_w"] / 2, cy - ly * e["inner_w"] / 2)
            out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="7" stroke-linecap="round" stroke-opacity="0.45"/>')
            out.append(f'<line x1="{ia[0]:.1f}" y1="{ia[1]:.1f}" x2="{ib[0]:.1f}" y2="{ib[1]:.1f}" stroke="{col}" stroke-width="3" stroke-dasharray="2 5"/>')
        elif e["type"] == "keyhole":
            fx, fy = e["facing"]
            lx, ly = -fy, fx
            cx, cy, cz = e["center"]
            r = e["outer_d"] / 2
            a, b = P(cx + lx * r, cy + ly * r), P(cx - lx * r, cy - ly * r)
            out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="7" stroke-linecap="round"/>')
            p = P(cx, cy)
            out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="{INK}"/>')
        elif e["type"] == "cube":
            h = e["size"] / 2
            x0, y0 = P(e["center"][0] + h, e["center"][1] + h)
            out.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{2 * h * S:.1f}" height="{2 * h * S:.1f}" fill="#17191e" stroke="{col}" stroke-width="3" rx="4"/>')
        elif e["type"] == "landing_pad":
            p = P(*e["center"])
            out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{e["diameter"] / 2 * S:.1f}" fill="#101216" stroke="{col}" stroke-width="3"/>')
            out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{e["bullseye_d"] / 2 * S:.1f}" fill="{col}" fill-opacity="0.25" stroke="{col}" stroke-width="2"/>')
        elif e["type"] == "tunnel":
            p = P(*e["center"])
            out.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{e["diameter"] / 2 * S:.1f}" fill="none" stroke="#c7cdd6" stroke-width="2.5" stroke-dasharray="6 4"/>')
            sp = P(e["center"][0] + e["stand_offset"][0], e["center"][1] + e["stand_offset"][1])
            out.append(f'<circle cx="{sp[0]:.1f}" cy="{sp[1]:.1f}" r="3" fill="{INK}"/>')

    # fly-through direction arrows
    for e in c["elements"]:
        if e["type"] in ("arch", "keyhole"):
            cx, cy = e["center"][:2]
            fx, fy = e["facing"]
            a, b = P(cx - fx * 34, cy - fy * 34), P(cx + fx * 22, cy + fy * 22)
            out.append(arrow(a[0], a[1], b[0], b[1], "#ff5a5a", 2.5))

    # the drone at the start
    sx, sy = P(0, 0)
    out.append(f'<g transform="translate({sx:.1f},{sy:.1f})"><rect x="-8" y="-8" width="16" height="16" rx="4" fill="{INK}"/>'
               f'<circle cx="-8" cy="-8" r="4.5" fill="none" stroke="#4cc9f0" stroke-width="2"/><circle cx="8" cy="-8" r="4.5" fill="none" stroke="#4cc9f0" stroke-width="2"/>'
               f'<circle cx="-8" cy="8" r="4.5" fill="none" stroke="#4cc9f0" stroke-width="2"/><circle cx="8" cy="8" r="4.5" fill="none" stroke="#4cc9f0" stroke-width="2"/></g>')
    out.append(arrow(sx, sy - 14, sx, sy - 40, INK, 2))
    out.append(text(sx + 14, sy + 30, "START (0, 0)", 11, "#5ee08a", "start", 700))

    # callouts: (anchor point in cm, label position in px, lines)
    def call(x, y, tx, ty, lines, col):
        px, py = P(x, y)
        out.append(f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{col}" stroke-opacity="0.6"/>')
        anchor = "start" if tx >= px else "end"
        off = 4 if tx >= px else -4
        for i, (t, size, fill, w) in enumerate(lines):
            out.append(text(tx + off, ty + 4 + i * 15, t, size, fill, anchor, w))

    ra, gk, cu, ba, yk, tu, lp = (el[k] for k in ("red_arch", "green_keyhole", "large_cube", "blue_arch",
                                                  "yellow_keyhole", "tunnel", "landing_pad"))
    L = TOP_X0 - 12
    call(ra["center"][0], 104, L, P(ra["center"][0], 0)[1] - 6,
         [("RED ARCH  +5", 12, ra["color"], 800), ("30 ahead", 11, DIM, 400), ("160 tall inside", 11, DIM, 400)], ra["color"])
    call(gk["center"][0], gk["center"][1] + 38, L, P(gk["center"][0], 0)[1] - 6,
         [("GREEN KEYHOLE  +10", 12, gk["color"], 800), ("110 ahead", 11, DIM, 400), ("center 120 high", 11, DIM, 400)], gk["color"])
    call(cu["center"][0], cu["center"][1] + 21.5, L, P(cu["center"][0], 0)[1] - 6,
         [("LARGE CUBE  +25 bonus", 12, "#ff7a93", 800), ("175 ahead, on the floor", 11, DIM, 400),
          ("side holes 25 high", 11, DIM, 400), ("in one side, out another", 11, DIM, 400)], "#ff7a93")
    bx, by = P(279, -75)
    call(279, -75, bx + 16, by - 4, [("BLUE ARCH  +5", 12, ba["color"], 800), ("75 right of the corner", 11, DIM, 400)], ba["color"])
    yx, yy = P(yk["center"][0] + 38, yk["center"][1])
    call(yk["center"][0] + 38, yk["center"][1], yx + 40, yy - 50, [("YELLOW KEYHOLE  +20", 12, yk["color"], 800),
         ("160 right of the corner", 11, DIM, 400), ("center 140 high", 11, DIM, 400)], yk["color"])
    lx_, ly_ = P(lp["center"][0] - 38, lp["center"][1])
    call(lp["center"][0] - 38, lp["center"][1], lx_ - 30, ly_ + 60, [("LANDING PAD  +5 · bullseye +15", 12, "#ff7a93", 800),
         ("250 right of the corner", 11, DIM, 400),
         ("TUNNEL hangs above it, 95–143 high", 11, "#c7cdd6", 700),
         ("drop through it top → bottom: +15 bonus", 11, DIM, 400)], "#ff7a93")

    # corner marker
    kx, ky = P(175.5, 0)
    out.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="5" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="2 2"/>')
    out.append(text(kx + 34, ky - 4, "the corner", 10, INK, "start", 600))
    out.append(text(kx + 34, ky + 9, "(175, 0)", 10, DIM))

    # ---------------- heights panel ----------------
    HX, HY, HW, HH = 862, 100, 292, 470
    out.append(f'<rect x="{HX}" y="{HY - 20}" width="{HW}" height="{HH + 105}" rx="10" fill="#141a22" stroke="{FAINT}"/>')
    out.append(text(HX + 14, HY + 4, "HEIGHTS (cm above the floor)", 12, INK, "start", 800))
    zmax = 200
    base = HY + HH + 10

    def Z(z):
        return base - z / zmax * (HH - 30)
    for z in range(0, zmax + 1, 20):
        out.append(f'<line x1="{HX + 44}" y1="{Z(z):.1f}" x2="{HX + HW - 14}" y2="{Z(z):.1f}" stroke="{FAINT}"/>')
        out.append(text(HX + 38, Z(z) + 4, str(z), 10, DIM, "end"))
    cols = [HX + 66, HX + 118, HX + 170, HX + 222, HX + 270]

    def bar(i, lo, hi, col, name, sub=None, dashed=False):
        x = cols[i]
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        out.append(f'<rect x="{x - 14}" y="{Z(hi):.1f}" width="28" height="{Z(lo) - Z(hi):.1f}" rx="4" fill="{col}" fill-opacity="0.22" stroke="{col}" stroke-width="1.5"{dash}/>')
        out.append(text(x, base + 18, name, 10, col, "middle", 700))
        if sub:
            out.append(text(x, base + 31, sub, 10, DIM, "middle"))

    bar(0, 0, ra["inner_h"], ra["color"], "arches", "0–160")
    g_lo, g_hi = gk["center"][2] - gk["inner_d"] / 2, gk["center"][2] + gk["inner_d"] / 2
    bar(1, g_lo, g_hi, gk["color"], "green", "90–150")
    y_lo, y_hi = yk["center"][2] - yk["inner_d"] / 2, yk["center"][2] + yk["inner_d"] / 2
    bar(2, y_lo, y_hi, yk["color"], "yellow", "110–170")
    bar(3, tu["bottom"], tu["bottom"] + tu["length"], "#c7cdd6", "tunnel", "95–143", dashed=True)
    bar(4, cu["hole_d"] / 2 * 0 + cu["height"] / 2 - cu["hole_d"] / 2, cu["height"] / 2 + cu["hole_d"] / 2, "#ff7a93", "cube", "10–40")
    for x, z in ((cols[1], gk["center"][2]), (cols[2], yk["center"][2])):
        out.append(f'<line x1="{x - 18}" y1="{Z(z):.1f}" x2="{x + 18}" y2="{Z(z):.1f}" stroke="{INK}" stroke-width="1.5"/>')
    out.append(f'<line x1="{HX + 44}" y1="{Z(c["takeoff_height"]):.1f}" x2="{HX + HW - 14}" y2="{Z(c["takeoff_height"]):.1f}" '
               f'stroke="#5ee08a" stroke-width="2" stroke-dasharray="6 4"/>')
    out.append(text(HX + HW - 16, Z(c["takeoff_height"]) - 6, "takeoff hover ≈ 80", 10, "#5ee08a", "end", 700))
    out.append(text(HX + 14, base + 52, "Openings are ~60 cm wide and the drone is", 10, DIM))
    out.append(text(HX + 14, base + 65, "14 cm, so you get about ±20 cm of wiggle room.", 10, DIM))

    out.append("</svg>")
    path = os.path.join(ROOT, "docs", "course-map.svg")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
