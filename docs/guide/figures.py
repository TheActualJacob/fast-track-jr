"""Print-style (white background) SVG figures for the course guide, drawn from the course JSON."""
import math

NAVY = "#1c3563"
INK = "#1f2733"
DIM = "#6b7482"
GRID = "#e6e9ee"
MAT = "#d9dde3"
RED = "#e0304e"


def _t(x, y, s, size=11, fill=INK, anchor="start", weight=400, extra=""):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{s}</text>')


def cm_in(v):
    return f"{v:g} cm ({v / 2.54:.1f} in)"


def top_view(c):
    """Dimensioned plan view of the Fast Track Jr. course with numbered callouts."""
    el = {e["id"]: e for e in c["elements"]}
    S = 1.9
    Y_MAX, X_MAX = 150, 292          # sim extents shown: +y = left edge of the page, +x = top
    OX, OY = 18, 16
    W, H = 900, 650

    def P(x, y):
        return OX + (Y_MAX - y) * S, OY + (X_MAX - x) * S

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Roboto, Helvetica Neue, Arial, sans-serif">',
         '<defs><marker id="dim" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         f'<path d="M0,2 L5,5 L0,8" fill="none" stroke="{INK}" stroke-width="1.4"/></marker>'
         f'<marker id="fly" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for x in range(-25, 291, 25):
        a_, b_ = P(x, Y_MAX), P(x, -305)
        o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{GRID}"/>')
    for y in range(-300, Y_MAX + 1, 25):
        a_, b_ = P(290, y), P(-30, y)
        o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{GRID}"/>')
    for m in c["mats"]:
        a_, b_ = P(m["x"][1], m["y"][1]), P(m["x"][0], m["y"][0])
        o.append(f'<rect x="{a_[0]:.1f}" y="{a_[1]:.1f}" width="{b_[0] - a_[0]:.1f}" height="{b_[1] - a_[1]:.1f}" fill="{MAT}" stroke="#aeb5bf"/>')
    sz = c["start_zone"]
    a_, b_ = P(sz["x"][1], sz["y"][1]), P(sz["x"][0], sz["y"][0])
    o.append(f'<rect x="{a_[0]:.1f}" y="{a_[1]:.1f}" width="{b_[0] - a_[0]:.1f}" height="{b_[1] - a_[1]:.1f}" fill="#39c46e" fill-opacity="0.55"/>')

    # draw overhead things (tunnel) last so they sit on top of the pad
    for e in sorted(c["elements"], key=lambda e: e["type"] == "tunnel"):
        col = e["color"]
        if e["type"] == "arch":
            band = e["outer_h"] - e["inner_h"]
            fx, fy = e["facing"]
            lx, ly = -fy, fx
            cx, cy = e["center"]
            for half, w, op in ((e["inner_w"] / 2 + band, 7, 0.35), (e["inner_w"] / 2, 3.2, 1)):
                a_, b_ = P(cx + lx * half, cy + ly * half), P(cx - lx * half, cy - ly * half)
                o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{col}" stroke-width="{w}" stroke-opacity="{op}" stroke-linecap="round"/>')
        elif e["type"] == "keyhole":
            fx, fy = e["facing"]
            lx, ly = -fy, fx
            cx, cy, _ = e["center"]
            r = e["outer_d"] / 2
            a_, b_ = P(cx + lx * r, cy + ly * r), P(cx - lx * r, cy - ly * r)
            o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{col}" stroke-width="7" stroke-linecap="round"/>')
            pc = P(cx, cy)
            o.append(f'<circle cx="{pc[0]:.1f}" cy="{pc[1]:.1f}" r="2.8" fill="{INK}"/>')
        elif e["type"] == "cube":
            h = e["size"] / 2
            a_ = P(e["center"][0] + h, e["center"][1] + h)
            o.append(f'<rect x="{a_[0]:.1f}" y="{a_[1]:.1f}" width="{2 * h * S:.1f}" height="{2 * h * S:.1f}" fill="#2a2e35" stroke="{col}" stroke-width="2.5" rx="3"/>')
        elif e["type"] == "landing_pad":
            pc = P(*e["center"])
            o.append(f'<circle cx="{pc[0]:.1f}" cy="{pc[1]:.1f}" r="{e["diameter"] / 2 * S:.1f}" fill="#23262c" stroke="{col}" stroke-width="2.5"/>')
            o.append(f'<circle cx="{pc[0]:.1f}" cy="{pc[1]:.1f}" r="{e["bullseye_d"] / 2 * S:.1f}" fill="none" stroke="{col}" stroke-width="2"/>')
        elif e["type"] == "tunnel":
            pc = P(*e["center"])
            o.append(f'<circle cx="{pc[0]:.1f}" cy="{pc[1]:.1f}" r="{e["diameter"] / 2 * S:.1f}" fill="none" stroke="#c3c9d1" stroke-width="2.4" stroke-dasharray="7 5"/>')
            sp = P(e["center"][0] + e["stand_offset"][0], e["center"][1] + e["stand_offset"][1])
            o.append(f'<circle cx="{sp[0]:.1f}" cy="{sp[1]:.1f}" r="2.8" fill="{INK}"/>')
    for e in c["elements"]:
        if e["type"] in ("arch", "keyhole"):
            cx, cy = e["center"][:2]
            fx, fy = e["facing"]
            a_, b_ = P(cx - fx * 32, cy - fy * 32), P(cx + fx * 22, cy + fy * 22)
            o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{RED}" stroke-width="2.6" marker-end="url(#fly)"/>')
    sx, sy = P(0, 0)
    o.append(f'<rect x="{sx - 5:.1f}" y="{sy - 5:.1f}" width="10" height="10" rx="2" fill="{INK}"/>')
    for dx in (-6.5, 6.5):
        for dy in (-6.5, 6.5):
            o.append(f'<circle cx="{sx + dx:.1f}" cy="{sy + dy:.1f}" r="4" fill="none" stroke="{INK}" stroke-width="1.4"/>')

    def ext(x1, y1, x2, y2):
        a_, b_ = P(x1, y1), P(x2, y2)
        o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{DIM}" stroke-width="0.8" stroke-dasharray="3 3"/>')

    def dim(p0, p1, label, lx, ly, anchor="middle", rot=0):
        a_, b_ = P(*p0), P(*p1)
        o.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" stroke="{INK}" stroke-width="1.1" marker-start="url(#dim)" marker-end="url(#dim)"/>')
        extra = f'transform="rotate({rot} {lx:.1f} {ly:.1f})"' if rot else ""
        o.append(f'<rect x="{lx - 26:.1f}" y="{ly - 9:.1f}" width="52" height="13" fill="#fff" {extra}/>')
        o.append(_t(lx, ly + 1.5, label, 11, INK, anchor, 500, extra))

    ra, gk, cu, ba, yk, tu, lp = (el[k] for k in ("red_arch", "green_keyhole", "large_cube", "blue_arch",
                                                  "yellow_keyhole", "tunnel", "landing_pad"))
    corner = cu["center"][0]
    # forward distances (left side, outside the red arch's leg)
    for i, x in enumerate((ra["center"][0], gk["center"][0], corner)):
        yd = 114 + 14 * i
        ext(0, 0, 0, yd + 5)
        ext(x, -20 if i < 2 else -22, x, yd + 5)
        a_, b_ = P(0, yd), P(x, yd)
        dim((0, yd), (x, yd), f"{x:g}", a_[0], (a_[1] + b_[1]) / 2 + 4, rot=-90)
    # rightward distances from the corner (above mat 2)
    for i, e in enumerate((ba, yk, lp)):
        y = e["center"][1]
        xd = 246 + 14 * i
        ext(corner, 0, xd + 5, 0)
        ext(corner if e is ba else e["center"][0] + 10, y, xd + 5, y)
        a_, b_ = P(xd, 0), P(xd, y)
        dim((xd, 0), (xd, y), f"{-y:g}", (a_[0] + b_[0]) / 2, a_[1] + 4)
    m1 = c["mats"][0]
    a_, b_ = P(-24, m1["y"][1]), P(-24, m1["y"][0])
    dim((-24, m1["y"][1]), (-24, m1["y"][0]), "107", (a_[0] + b_[0]) / 2, a_[1] + 4)

    # numbered callouts
    marks = [
        (1, (ra["center"][0] + 16, 36), "Red arch", f"{ra['center'][0]:g} cm ahead · opening {ra['inner_w']:g} × {ra['inner_h']:g} cm"),
        (2, (gk["center"][0], -52), "Green keyhole", f"{gk['center'][0]:g} cm ahead · center {gk['center'][2]:g} cm high"),
        (3, (corner, 36), "Large cube (bonus)", f"at the corner · {cu['size']:g} × {cu['size']:g} × {cu['height']:g} cm"),
        (4, (ba["center"][0] - 76 - 28 - 12, ba["center"][1]), "Blue arch", f"{-ba['center'][1]:g} cm right of the corner"),
        (5, (yk["center"][0] - 52, yk["center"][1]), "Yellow keyhole", f"{-yk['center'][1]:g} cm right · center {yk['center'][2]:g} cm high"),
        (6, (lp["center"][0] - 52, lp["center"][1]), "Landing pad + tunnel", f"{-lp['center'][1]:g} cm right · tunnel {tu['bottom']:g}–{tu['bottom'] + tu['length']:g} cm high"),
    ]
    for n, (x, y), _, _ in marks:
        px, py = P(x, y)
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="{NAVY}"/>')
        o.append(_t(px, py + 4, n, 11, "#fff", "middle", 700))
    o.append(_t(sx + 13, sy + 22, "START (0, 0)", 10.5, "#1d8a4a", "start", 700))

    # key, in the empty inside corner of the L
    kx, ky = P(100, -117)
    o.append(f'<rect x="{kx:.1f}" y="{ky:.1f}" width="{W - kx - 14:.1f}" height="{44 + len(marks) * 21 + 8 + 19 + 21 + 14}" fill="#fff" stroke="#cfd4db"/>')
    o.append(_t(kx + 14, ky + 22, "KEY  (all distances in cm, center to center)", 10, NAVY, "start", 700))
    for i, (n, _, name, detail) in enumerate(marks):
        yy = ky + 44 + i * 21
        o.append(f'<circle cx="{kx + 23:.1f}" cy="{yy - 4:.1f}" r="8" fill="{NAVY}"/>')
        o.append(_t(kx + 23, yy, n, 10, "#fff", "middle", 700))
        o.append(_t(kx + 38, yy, name, 11, INK, "start", 700))
        o.append(_t(kx + 160, yy, detail, 10, DIM))
    yy = ky + 44 + len(marks) * 21 + 8
    o.append(f'<line x1="{kx + 14:.1f}" y1="{yy - 4:.1f}" x2="{kx + 40:.1f}" y2="{yy - 4:.1f}" stroke="{RED}" stroke-width="2.4" marker-end="url(#fly)"/>')
    o.append(_t(kx + 48, yy, "direction you must fly", 10.5, INK))
    o.append(f'<circle cx="{kx + 196:.1f}" cy="{yy - 4:.1f}" r="2.8" fill="{INK}"/>')
    o.append(_t(kx + 206, yy, "stand / pole", 10.5, INK))
    yy += 19
    o.append(f'<line x1="{kx + 14:.1f}" y1="{yy - 4:.1f}" x2="{kx + 40:.1f}" y2="{yy - 4:.1f}" stroke="#c3c9d1" stroke-width="2.4" stroke-dasharray="7 5"/>')
    o.append(_t(kx + 48, yy, "tunnel, hanging above the pad", 10.5, INK))
    o.append(_t(kx + 14, yy + 21, "Grid squares are 25 cm. Forward is up the page.", 10, DIM))
    o.append("</svg>")
    return "\n".join(o)


def height_profile(c):
    """Side view along the flight path (unrolled at the corner), heights to scale."""
    el = {e["id"]: e for e in c["elements"]}
    corner = el["large_cube"]["center"][0]
    W, H = 900, 330
    L, R, T, B = 60, 20, 24, 60
    s_max = corner + 300
    kx = (W - L - R) / s_max
    kz = (H - T - B) / 200

    def X(s):
        return L + s * kx

    def Z(z):
        return H - B - z * kz

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Roboto, Helvetica Neue, Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for z in range(0, 201, 20):
        o.append(f'<line x1="{L}" y1="{Z(z):.1f}" x2="{W - R}" y2="{Z(z):.1f}" stroke="{GRID}"/>')
        o.append(_t(L - 8, Z(z) + 3.5, z, 10, DIM, "end"))
    o.append(_t(14, Z(100), "height (cm)", 10.5, DIM, "middle", 500, f'transform="rotate(-90 14 {Z(100):.1f})"'))
    o.append(f'<line x1="{L}" y1="{Z(0):.1f}" x2="{W - R}" y2="{Z(0):.1f}" stroke="{INK}" stroke-width="1.2"/>')

    def band(s0, s1, z0, z1, col, op=0.18, dash=False):
        d = ' stroke-dasharray="5 3"' if dash else ""
        o.append(f'<rect x="{X(s0):.1f}" y="{Z(z1):.1f}" width="{X(s1) - X(s0):.1f}" height="{Z(z0) - Z(z1):.1f}" fill="{col}" fill-opacity="{op}" stroke="{col}" stroke-width="1.4"{d}/>')

    def ring(s, cz, ri, ro, col):
        o.append(f'<rect x="{X(s) - 3:.1f}" y="{Z(cz + ro):.1f}" width="6" height="{Z(cz + ri) - Z(cz + ro):.1f}" fill="{col}"/>')
        o.append(f'<rect x="{X(s) - 3:.1f}" y="{Z(cz - ri):.1f}" width="6" height="{Z(cz - ro) - Z(cz - ri):.1f}" fill="{col}"/>')
        o.append(f'<line x1="{X(s) - 12:.1f}" y1="{Z(cz):.1f}" x2="{X(s) + 12:.1f}" y2="{Z(cz):.1f}" stroke="{col}" stroke-width="1" stroke-dasharray="2 2"/>')
        o.append(f'<line x1="{X(s):.1f}" y1="{Z(cz - ro):.1f}" x2="{X(s):.1f}" y2="{Z(0):.1f}" stroke="{INK}" stroke-width="1.2"/>')

    ra, gk, cu, ba, yk, tu, lp = (el[k] for k in ("red_arch", "green_keyhole", "large_cube", "blue_arch",
                                                  "yellow_keyhole", "tunnel", "landing_pad"))
    # arches: thin bars with the opening height
    for e, s in ((ra, ra["center"][0]), (ba, corner - ba["center"][1])):
        o.append(f'<rect x="{X(s) - 3:.1f}" y="{Z(e["outer_h"]):.1f}" width="6" height="{Z(e["inner_h"]) - Z(e["outer_h"]):.1f}" fill="{e["color"]}"/>')
        o.append(f'<line x1="{X(s):.1f}" y1="{Z(e["inner_h"]):.1f}" x2="{X(s):.1f}" y2="{Z(0):.1f}" stroke="{e["color"]}" stroke-width="1" stroke-dasharray="3 3"/>')
        o.append(_t(X(s), Z(e["outer_h"]) - 6, e["label"], 10.5, e["color"], "middle", 700))
        o.append(_t(X(s) + 7, Z(e["inner_h"]) + 12, f'{e["inner_h"]:g}', 10, DIM))
    ring(gk["center"][0], gk["center"][2], gk["inner_d"] / 2, gk["outer_d"] / 2, "#2e9a3f")
    o.append(_t(X(gk["center"][0]), Z(gk["center"][2] + gk["outer_d"] / 2) - 6, "Green keyhole", 10.5, "#2e9a3f", "middle", 700))
    o.append(_t(X(gk["center"][0]) + 14, Z(gk["center"][2]) + 3.5, f'{gk["center"][2]:g}', 10, DIM))
    s_y = corner - yk["center"][1]
    ring(s_y, yk["center"][2], yk["inner_d"] / 2, yk["outer_d"] / 2, "#b58f00")
    o.append(_t(X(s_y), Z(yk["center"][2] + yk["outer_d"] / 2) - 6, "Yellow keyhole", 10.5, "#b58f00", "middle", 700))
    o.append(_t(X(s_y) + 14, Z(yk["center"][2]) + 3.5, f'{yk["center"][2]:g}', 10, DIM))
    # cube with its hole
    h = cu["size"] / 2
    band(corner - h, corner + h, 0, cu["height"], "#2a2e35", 0.85)
    hr = cu["hole_d"] / 2
    o.append(f'<rect x="{X(corner - h) + 2:.1f}" y="{Z(cu["height"] / 2 + hr):.1f}" width="{X(corner + h) - X(corner - h) - 4:.1f}" height="{Z(cu["height"] / 2 - hr) - Z(cu["height"] / 2 + hr):.1f}" fill="#fff" fill-opacity="0.85"/>')
    o.append(_t(X(corner), Z(cu["height"]) - 6, "Large cube", 10.5, RED, "middle", 700))
    # tunnel + pad
    s_t = corner - tu["center"][1]
    band(s_t - tu["diameter"] / 2, s_t + tu["diameter"] / 2, tu["bottom"], tu["bottom"] + tu["length"], "#59606b", 0.25)
    o.append(_t(X(s_t), Z(tu["bottom"] + tu["length"]) - 6, "Tunnel", 10.5, "#3b4048", "middle", 700))
    o.append(_t(X(s_t + tu["diameter"] / 2) + 6, Z(tu["bottom"]) + 3.5, f'{tu["bottom"]:g}', 10, DIM))
    o.append(_t(X(s_t + tu["diameter"] / 2) + 6, Z(tu["bottom"] + tu["length"]) + 3.5, f'{tu["bottom"] + tu["length"]:g}', 10, DIM))
    s_p = corner - lp["center"][1]
    o.append(f'<rect x="{X(s_p - lp["diameter"] / 2):.1f}" y="{Z(0) - 4:.1f}" width="{lp["diameter"] * kx:.1f}" height="4" fill="{RED}"/>')
    o.append(_t(X(s_p), Z(0) + 16, "Landing pad", 10.5, RED, "middle", 700))
    # takeoff height + corner marker
    o.append(f'<line x1="{L}" y1="{Z(c["takeoff_height"]):.1f}" x2="{W - R}" y2="{Z(c["takeoff_height"]):.1f}" stroke="#1d8a4a" stroke-width="1.4" stroke-dasharray="7 4"/>')
    o.append(_t(W - R - 4, Z(c["takeoff_height"]) - 5, "takeoff hover ≈ 80 cm", 10.5, "#1d8a4a", "end", 600))
    o.append(f'<line x1="{X(corner):.1f}" y1="{Z(0):.1f}" x2="{X(corner):.1f}" y2="{Z(0) + 22:.1f}" stroke="{INK}"/>')
    o.append(_t(X(corner), Z(0) + 34, "corner: turn right", 10.5, INK, "middle", 600))
    o.append(_t(X(0), Z(0) + 16, "start", 10.5, INK, "middle", 600))
    for s, lbl in ((0, "0"), (corner, f"{corner:g}"), (s_max, "")):
        pass
    o.append(_t(L, H - 8, "distance along the course (cm): forward to the corner, then right", 10, DIM))
    o.append("</svg>")
    return "\n".join(o)


def axes_figure():
    """Tiny diagram of the drone's frame: forward / left / up."""
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200" font-family="Roboto, Helvetica Neue, Arial, sans-serif">
<defs><marker id="ax" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1c3563"/></marker></defs>
<rect width="300" height="200" fill="#fff"/>
<g transform="translate(150 118)">
  <rect x="-16" y="-16" width="32" height="32" rx="6" fill="#1f2733"/>
  <g fill="none" stroke="#1f2733" stroke-width="2.5">
    <circle cx="-22" cy="-22" r="11"/><circle cx="22" cy="-22" r="11"/><circle cx="-22" cy="22" r="11"/><circle cx="22" cy="22" r="11"/>
  </g>
  <rect x="-5" y="-16" width="10" height="5" fill="#e0304e"/>
  <line x1="0" y1="-40" x2="0" y2="-92" stroke="#1c3563" stroke-width="2.4" marker-end="url(#ax)"/>
  <line x1="-40" y1="0" x2="-100" y2="0" stroke="#1c3563" stroke-width="2.4" marker-end="url(#ax)"/>
  <line x1="40" y1="0" x2="100" y2="0" stroke="#9aa3af" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#ax)"/>
  <text x="8" y="-80" font-size="13" fill="#1c3563" font-weight="700">+x forward</text>
  <text x="-100" y="-10" font-size="13" fill="#1c3563" font-weight="700">+y left</text>
  <text x="100" y="-10" font-size="13" fill="#6b7482" text-anchor="end">−y right</text>
  <text x="0" y="62" font-size="12" fill="#6b7482" text-anchor="middle">top view · +z is up (out of the page)</text>
</g></svg>'''
