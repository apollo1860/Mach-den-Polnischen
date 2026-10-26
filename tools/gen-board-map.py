#!/usr/bin/env python3
"""Erzeugt assets/board-map.svg – die stilisierte Nacht-Karte von München,
die als Hintergrund in der Mitte des Spielbretts liegt.

Als Vektorgrafik bleibt sie bei jedem Zoom und jeder Pixeldichte scharf
(im Gegensatz zum früheren 2000×2000-Rasterbild). Aufruf aus dem Repo-Root:

    python3 tools/gen-board-map.py

Fester Zufalls-Seed → bei gleichem Skript entsteht exakt dieselbe Datei.
"""
import math
import random
from pathlib import Path

W = H = 1700          # entspricht COLS*TILE bzw. ROWS*TILE (17 × 100 px)
rnd = random.Random(1860)

# ---------- Farben ----------
BG_TOP, BG_BOTTOM = "#141b35", "#101a2e"
STREET_GOLD, STREET_TEAL = (226, 172, 92), (92, 178, 178)
MAIN_ROAD = "#f2bd63"
RIVER, RIVER_EDGE = "#24427a", "#4d7cc9"
PARK, PARK_EDGE, PARK_PATH = "#173a33", "#2d6a54", "#3f8a6c"
LAKE = "#22477f"


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def pts(points):
    return " ".join(f"{f(x)},{f(y)}" for x, y in points)


def catmull(points, closed=False):
    """Glatte Kurve (Catmull-Rom → kubische Béziers) durch alle Punkte."""
    p = list(points)
    if closed:
        p = [p[-1]] + p + [p[0], p[1]]
    else:
        p = [p[0]] + p + [p[-1]]
    d = f"M{f(p[1][0])},{f(p[1][1])}"
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}"
    return d + ("Z" if closed else "")


def blob(cx, cy, rx, ry, n=10, wobble=0.12, rot=0.0):
    """Unregelmäßige, geschlossene Form (Parks, Seen)."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + rnd.uniform(-wobble, wobble)
        x, y = math.cos(a) * rx * r, math.sin(a) * ry * r
        out.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return catmull(out, closed=True)


# ---------- Voronoi-Bezirke (Sutherland-Hodgman an Mittelsenkrechten) ----------
def clip_halfplane(poly, a, b, c):
    """Behält den Teil von poly mit a*x + b*y <= c."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if fp * fq < 0:
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


CENTER = (800, 830)   # Marienplatz
# (x, y, Straßenwinkel°, Abstand) – je Bezirk eine eigene Rasterrichtung
SEEDS = [
    (800, 830, 8, 17),     # Altstadt
    (560, 640, -18, 26),   # Maxvorstadt
    (860, 470, 4, 27),     # Schwabing
    (620, 330, 22, 30),    # Schwabing-West
    (330, 520, -6, 33),    # Neuhausen
    (330, 860, 12, 31),    # Westend / Laim
    (560, 990, 34, 25),    # Ludwigsvorstadt
    (690, 1240, -24, 27),  # Isarvorstadt
    (430, 1330, 10, 31),   # Sendling
    (800, 1500, 28, 33),   # Untergiesing
    (1260, 1130, -12, 29), # Haidhausen-Süd
    (1240, 820, 6, 27),    # Haidhausen / Bogenhausen
    (1360, 480, -28, 33),  # Bogenhausen-Nord
    (1430, 1450, 18, 34),  # Ramersdorf
    (180, 230, 30, 36),    # Moosach
    (1500, 230, 12, 36),   # Oberföhring
    (210, 1550, -20, 36),  # Fürstenried
]


def voronoi_cell(i):
    poly = [(0, 0), (W, 0), (W, H), (0, H)]
    xi, yi = SEEDS[i][:2]
    for j, (xj, yj, *_ ) in enumerate(SEEDS):
        if j == i:
            continue
        a, b = xj - xi, yj - yi
        c = (xj * xj + yj * yj - xi * xi - yi * yi) / 2
        poly = clip_halfplane(poly, a, b, c)
    return poly


def wavy_line(x0, y0, x1, y1, amp, freq, phase, n=4):
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    return [(x0 + dx * k / n + nx * amp * math.sin(freq * k / n * math.pi * 2 + phase),
             y0 + dy * k / n + ny * amp * math.sin(freq * k / n * math.pi * 2 + phase))
            for k in range(n + 1)]


def district_streets(cell, ang, sp):
    """Zwei sich kreuzende, gewellte Straßenscharen; Quer- und teils auch
    Längsstraßen sind in Stücke gebrochen, damit unregelmäßige Blöcke
    entstehen. Erzeugt wird nur so viel, wie den Bezirk abdeckt."""
    cx = sum(x for x, _ in cell) / len(cell)
    cy = sum(y for _, y in cell) / len(cell)
    R = max(math.hypot(x - cx, y - cy) for x, y in cell) + 12
    bend = rnd.uniform(-0.35, 0.35) / R     # ganze Schar leicht gebogen
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)      # entlang der Straße
    vx, vy = -uy, ux                       # quer dazu

    def warp(line):
        return [(x + vx * bend * ((x - cx) * ux + (y - cy) * uy) ** 2,
                 y + vy * bend * ((x - cx) * ux + (y - cy) * uy) ** 2) for x, y in line]
    long_d, short_d = [], []
    freq, phase = rnd.uniform(0.5, 1.2), rnd.uniform(0, 6)
    off = -R
    while off < R:
        ox, oy = cx + vx * off, cy + vy * off
        # Nachbarstraßen schwingen fast gleich → sie kreuzen sich nicht
        line = wavy_line(ox - ux * R, oy - uy * R, ox + ux * R, oy + uy * R,
                         sp * rnd.uniform(0.1, 0.22), freq, phase + rnd.uniform(-0.4, 0.4), n=14)
        line = warp(line)
        # gelegentlich Lücken (Sackgassen, Plätze)
        pieces, cur = [], []
        for pt in line:
            cur.append(pt)
            if len(cur) > 2 and rnd.random() < 0.09:
                pieces.append(cur); cur = []
        if len(cur) > 1:
            pieces.append(cur)
        (long_d if rnd.random() < 0.8 else short_d).extend(pieces)
        off += sp * rnd.uniform(0.7, 1.35)
    off = -R
    while off < R:
        ox, oy = cx + ux * off, cy + uy * off
        t = -R
        while t < R:
            seg = sp * rnd.uniform(1.5, 4.5)
            if rnd.random() < 0.85:
                short_d.append(warp(wavy_line(ox + vx * t, oy + vy * t,
                                              ox + vx * (t + seg), oy + vy * (t + seg),
                                              rnd.uniform(0, 3), 0.5, rnd.uniform(0, 6))))
            t += seg
        off += sp * rnd.uniform(0.9, 1.6)
    return long_d, short_d


def poly_d(lines):
    return "".join("M" + "L".join(f"{f(x)},{f(y)}" for x, y in ln) for ln in lines)


def mix(c1, c2, t):
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


# ---------- Geografie ----------
ISAR = [(1030, 1760), (985, 1560), (1005, 1380), (965, 1200), (995, 1030),
        (975, 900), (1010, 760), (1065, 600), (1110, 450), (1175, 300),
        (1265, 170), (1350, 40), (1400, -60)]
AUER_BACH = [(990, 1760), (948, 1560), (960, 1390), (930, 1220), (955, 1060)]
ALTSTADT_RING = [(675, 760), (730, 690), (845, 680), (925, 735), (935, 870),
                 (880, 960), (760, 975), (680, 905)]
MITTLERER_RING = [(330, 430), (620, 230), (980, 210), (1290, 330), (1430, 640),
                  (1450, 990), (1300, 1310), (1000, 1430), (650, 1440),
                  (370, 1280), (250, 950), (240, 640)]
RADIALS = [
    [(830, 690), (840, 520), (865, 330), (880, 140), (890, -20)],     # Ludwig-/Leopoldstraße
    [(680, 800), (500, 815), (300, 835), (100, 860), (-20, 870)],     # Landsberger Straße
    [(720, 950), (620, 1100), (520, 1290), (430, 1500), (370, 1720)], # Lindwurmstraße
    [(925, 870), (1080, 930), (1260, 1030), (1480, 1160), (1720, 1270)],  # Rosenheimer Straße
    [(890, 790), (1000, 795), (1110, 790), (1170, 800)],               # Maximilianstraße
    [(925, 735), (1100, 700), (1350, 690), (1720, 700)],               # Prinzregentenstraße
    [(700, 745), (560, 600), (380, 400), (200, 210), (60, 60)],        # Dachauer Straße
    [(850, 975), (880, 1150), (900, 1380), (910, 1720)],               # Fraunhoferstr. → Tegernseer
]
ENGLISCHER_GARTEN = [(925, 690), (985, 650), (1035, 520), (1080, 400), (1130, 260),
                     (1180, 120), (1110, 80), (1040, 200), (985, 330), (950, 470),
                     (915, 590)]


def svg():
    o = []
    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'width="{W}" height="{H}">')
    o.append("<defs>")
    o.append(f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>'
             f'</linearGradient>')
    o.append('<radialGradient id="glow" cx="0.47" cy="0.49" r="0.55">'
             '<stop offset="0" stop-color="#ffcf7a" stop-opacity=".16"/>'
             '<stop offset=".45" stop-color="#ffb04d" stop-opacity=".05"/>'
             '<stop offset="1" stop-color="#ffb04d" stop-opacity="0"/></radialGradient>')
    o.append('<radialGradient id="vignette" cx="0.5" cy="0.5" r="0.72">'
             '<stop offset=".6" stop-color="#070b1a" stop-opacity="0"/>'
             '<stop offset="1" stop-color="#070b1a" stop-opacity=".55"/></radialGradient>')
    for i in range(len(SEEDS)):
        o.append(f'<clipPath id="d{i}"><polygon points="{pts(voronoi_cell(i))}"/></clipPath>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')

    # Nebenstraßen je Bezirk – innen golden, außen türkis
    maxd = math.hypot(W, H) / 2
    for i, (cx, cy, ang, sp) in enumerate(SEEDS):
        t = min(1, math.hypot(cx - CENTER[0], cy - CENTER[1]) / (maxd * 0.85))
        col = mix(STREET_GOLD, STREET_TEAL, t)
        long_d, short_d = district_streets(voronoi_cell(i), ang, sp)
        o.append(f'<g clip-path="url(#d{i})" fill="none" stroke="{col}" stroke-linecap="round">')
        o.append(f'<path d="{poly_d(short_d)}" stroke-width="1.3" stroke-opacity=".34"/>')
        o.append(f'<path d="{poly_d(long_d)}" stroke-width="1.9" stroke-opacity=".5"/>')
        o.append("</g>")
    # Bezirksgrenzen als etwas breitere Straßen
    o.append(f'<g fill="none" stroke="{mix(STREET_GOLD, STREET_TEAL, .45)}" stroke-width="3" '
             f'stroke-opacity=".35" stroke-linejoin="round">')
    for i in range(len(SEEDS)):
        o.append(f'<polygon points="{pts(voronoi_cell(i))}"/>')
    o.append("</g>")

    # Bahngleise zum Hauptbahnhof
    o.append('<g fill="none" stroke="#9aa6c4" stroke-opacity=".38" stroke-width="1.4">')
    for k in range(-4, 5):
        o.append(f'<path d="M-20,{f(790 + k * 9)} C250,{f(790 + k * 7)} 450,{f(785 + k * 4)} '
                 f'640,{f(790 + k * 2.2)}"/>')
    o.append("</g>")
    o.append('<g fill="none" stroke="#9aa6c4" stroke-opacity=".38" stroke-width="5" '
             'stroke-dasharray="1.4 9">')
    o.append('<path d="M-20,790 C250,790 450,785 640,790"/></g>')
    o.append('<rect x="610" y="770" width="58" height="42" rx="5" fill="#2a3352" '
             'stroke="#aab6d6" stroke-opacity=".5" stroke-width="2"/>')

    # Parks
    def park(d, paths=4, bbox=None):
        o.append(f'<path d="{d}" fill="{PARK}" stroke="{PARK_EDGE}" stroke-width="3" '
                 f'stroke-opacity=".8"/>')
    park(catmull(ENGLISCHER_GARTEN, closed=True))
    o.append(f'<path d="{catmull([(945, 660), (990, 560), (1010, 450), (1060, 330), (1110, 200), (1140, 110)])}" '
             f'fill="none" stroke="{PARK_PATH}" stroke-width="2" stroke-opacity=".7" stroke-dasharray="7 6"/>')
    o.append(f'<path d="{catmull([(960, 600), (1010, 520), (1000, 420), (1040, 300)])}" '
             f'fill="none" stroke="{PARK_PATH}" stroke-width="1.5" stroke-opacity=".5"/>')
    o.append(f'<path d="{blob(1060, 330, 34, 20, 8, .15, -.6)}" fill="{LAKE}" '
             f'stroke="{RIVER_EDGE}" stroke-opacity=".6" stroke-width="2"/>')   # Kleinhesseloher See
    park(blob(870, 705, 42, 26, 8, .08))                                     # Hofgarten
    park(blob(500, 330, 120, 85, 12, .1, .2))                                # Olympiapark
    o.append(f'<path d="{blob(510, 380, 72, 22, 10, .2, .15)}" fill="{LAKE}" '
             f'stroke="{RIVER_EDGE}" stroke-opacity=".6" stroke-width="2"/>')   # Olympiasee
    park(blob(275, 640, 105, 60, 10, .06))                                   # Nymphenburger Park
    o.append(f'<path d="M190,640 L360,640" stroke="{RIVER_EDGE}" stroke-opacity=".7" stroke-width="5"/>')
    park(blob(330, 1220, 90, 40, 10, .12, -.15))                             # Westpark
    park(blob(1140, 1500, 55, 75, 10, .12))                                  # Ostpark
    o.append(f'<path d="{catmull([(1000, 1700), (960, 1470), (985, 1300)])}" fill="none" '
             f'stroke="{PARK}" stroke-width="80" stroke-linecap="round" stroke-opacity=".85"/>')  # Isarauen

    # Theresienwiese
    o.append('<ellipse cx="590" cy="1065" rx="70" ry="98" fill="#2a2a3a" stroke="#c9a35a" '
             'stroke-opacity=".55" stroke-width="3"/>')
    o.append('<ellipse cx="590" cy="1065" rx="44" ry="70" fill="none" stroke="#c9a35a" '
             'stroke-opacity=".3" stroke-width="1.5" stroke-dasharray="5 6"/>')

    # Isar mit Auer Mühlbach
    isar = catmull(ISAR)
    o.append(f'<path d="{catmull(AUER_BACH)}" fill="none" stroke="{RIVER_EDGE}" '
             f'stroke-width="5" stroke-opacity=".6" stroke-linecap="round"/>')
    o.append(f'<path d="{isar}" fill="none" stroke="{RIVER_EDGE}" stroke-width="46" '
             f'stroke-opacity=".55" stroke-linecap="round"/>')
    o.append(f'<path d="{isar}" fill="none" stroke="{RIVER}" stroke-width="38" stroke-linecap="round"/>')
    o.append(f'<path d="{isar}" fill="none" stroke="#7fb0ff" stroke-width="2" '
             f'stroke-opacity=".35" stroke-dasharray="26 34"/>')
    o.append(f'<path d="{blob(992, 905, 13, 52, 8, .1, .12)}" fill="#1b2846" '
             f'stroke="{RIVER_EDGE}" stroke-width="2"/>')                        # Museumsinsel

    # Hauptstraßen mit weichem Leuchten (breiter, transparenter Strich statt Filter)
    roads = [catmull(MITTLERER_RING, closed=True)] + [catmull(r) for r in RADIALS]
    ring = catmull(ALTSTADT_RING, closed=True)
    o.append(f'<g fill="none" stroke="{MAIN_ROAD}" stroke-linecap="round" stroke-linejoin="round">')
    for d in roads:
        o.append(f'<path d="{d}" stroke-width="16" stroke-opacity=".08"/>')
    o.append(f'<path d="{ring}" stroke-width="20" stroke-opacity=".1"/>')
    for d in roads:
        o.append(f'<path d="{d}" stroke-width="5" stroke-opacity=".75"/>')
    o.append(f'<path d="{ring}" stroke-width="6.5" stroke-opacity=".9"/>')
    for d in roads:
        o.append(f'<path d="{d}" stroke="#fff3d6" stroke-width="1.2" stroke-opacity=".55"/>')
    o.append("</g>")

    # Marienplatz-Leuchten
    o.append(f'<rect width="{W}" height="{H}" fill="url(#glow)"/>')
    o.append('<circle cx="800" cy="830" r="11" fill="#ffd27a" fill-opacity=".9"/>')
    o.append('<circle cx="800" cy="830" r="24" fill="none" stroke="#ffd27a" stroke-opacity=".5" stroke-width="2.5"/>')
    o.append('<circle cx="800" cy="830" r="40" fill="none" stroke="#ffd27a" stroke-opacity=".22" stroke-width="2"/>')
    # Olympiaturm
    o.append('<circle cx="455" cy="300" r="6" fill="#e9eefc"/>'
             '<circle cx="455" cy="300" r="14" fill="none" stroke="#e9eefc" stroke-opacity=".45" stroke-width="2"/>')

    o.append(f'<rect width="{W}" height="{H}" fill="url(#vignette)"/>')
    o.append("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets" / "board-map.svg"
    out.write_text(svg(), encoding="utf-8")
    print(f"{out} ({out.stat().st_size // 1024} KB)")
