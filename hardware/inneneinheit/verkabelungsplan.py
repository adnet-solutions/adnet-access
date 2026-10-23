"""Verkabelungsplan der Inneneinheit als A4-PDF (quer), Gehäuse im Maßstab 1:1.

Zeigt jede Leitung im Gehäuse: nummerierte Adern (YSLY-JZ), Cat-7-Adern, Grove-Kabel zum Atom,
Litzen der DC-Buchse, Dioden/Dupont für LED/BEEP. Lagen kommen aus stl/innen_layout.json.
Aufruf: python3 hardware/inneneinheit/verkabelungsplan.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

BASE = Path(__file__).resolve().parent
L = json.loads((BASE / "stl" / "innen_layout.json").read_text())
OUT = BASE / "verkabelungsplan_inneneinheit_A4.pdf"
IN_W, IN_H = L["in_w"], L["in_h"]
MM = 1 / 25.4

fig = plt.figure(figsize=(297 * MM, 210 * MM))
# Zeichenfläche 1:1: Ursprung (Innenecke unten links) bei 34 mm / 52 mm vom Blattrand
ox, oy, aw, ah = 34, 52, 240, 150
ax = fig.add_axes([ox / 297, oy / 210, aw / 297, ah / 210])
ax.set_xlim(-8, aw - 8)
ax.set_ylim(-6, ah - 6)
ax.set_aspect("equal")
ax.axis("off")

# ---------------- Gehäuse und Bauteile ----------------
ax.add_patch(FancyBboxPatch((-2.4, -2.4), IN_W + 4.8, IN_H + 4.8, boxstyle="round,pad=0,rounding_size=10",
                            fc="#f7f7f5", ec="#444", lw=1.2))
for name, (x, y, w, h) in L["sd"].items():
    ax.add_patch(Rectangle((x, y), w, h, fc="#e8eef8" if "5 V" in name else "#f8e8e8", ec="#555", lw=0.8))
    ax.text(x + w / 2, y + h / 2, name.replace(" (", "\n("), ha="center", va="center", fontsize=8, weight="bold")
    ax.add_patch(Rectangle((x + w, y + 4), L["sd_term"], h - 8, fc="#333", ec="#333"))
TERM = {}     # Klemmen je Wandler (oben nach unten): V+, V-, Vin-, Vin+
for name, (x, y, w, h) in L["sd"].items():
    tx = x + w + L["sd_term"]
    ys = [y + h - 4 - (h - 8) * (i + 0.5) / 4 for i in range(4)]
    key = "12" if "12" in name else "5"
    for lab, yy in zip(("V+", "V−", "Vin−", "Vin+"), ys):
        TERM[(key, lab)] = (tx, yy)
        ax.text(tx - 1, yy, lab, ha="right", va="center", fontsize=5.5, color="white", weight="bold")

PORT = {}     # Wago-Klemmstellen: (Name, Index) -> Punkt an der Einführung
for col, entry_left in (("wago1", True), ("wago2", False)):
    for x, y, d, w, lab, n in L[col]:
        ax.add_patch(Rectangle((x, y), d, w, fc="#ffc878", ec="#a66", lw=0.8))
        ax.text(x + d / 2, y + w / 2, lab, ha="center", va="center", fontsize=7, weight="bold")
        for i in range(n):
            yy = y + w * (i + 0.5) / n
            px = x if entry_left else x + d
            PORT[(lab, i)] = (px, yy)
            ax.plot([px], [yy], marker="o", ms=2.2, color="#a66")

axx, ayy, aws = L["atom"]
ax.add_patch(Rectangle((axx, ayy), aws, aws, fc="#3a3a3a", ec="#222"))
ax.text(axx + aws / 2, ayy + aws / 2 + 3, "AtomS3\nLite", ha="center", va="center", fontsize=7, color="white",
        weight="bold")
ax.text(axx + aws / 2, ayy + aws + 2, "USB-C", ha="center", fontsize=5.5, color="#555")
GROVE = (axx + aws / 2, ayy)
ax.add_patch(Rectangle((GROVE[0] - 4, ayy - 2.5), 8, 2.5, fc="white", ec="#222", lw=0.6))
ax.text(GROVE[0] + 5, ayy - 1.6, "Grove", fontsize=5.5, va="center")
G5, G6 = (axx, ayy + 8), (axx, ayy + 14)
for p, t in ((G5, "G5"), (G6, "G6")):
    ax.text(p[0] + 1, p[1], t, fontsize=5.5, color="white", va="center")

bx, by, br = L["bore"]
ax.add_patch(Circle((bx, by), br, fc="white", ec="#444", lw=0.8))
ax.text(bx, by, "Außenkabel\n10 × 0,75\n(von hinten)", ha="center", va="center", fontsize=5.5)
jx, jd = L["jack"]
ax.add_patch(Rectangle((jx - 6, -2.4), 12, 9, fc="#555", ec="#222"))
ax.text(jx, -6.5, "DC-Buchse 24 V", ha="center", fontsize=6)

# ---------------- Leitungen ----------------
WIRES = []    # für die Legende/Liste


def wire(points, color, label=None, dash=None, lw=1.3, white_stripe=False, lpos=0.5):
    xs, ys = zip(*points)
    if white_stripe:          # weiß-X-Adern: weiß mit farbigen Streifen
        ax.plot(xs, ys, color=color, lw=lw + 0.9, solid_capstyle="round", zorder=4)
        ax.plot(xs, ys, color="white", lw=lw - 0.2, dashes=(2, 2), zorder=5)
    else:
        ax.plot(xs, ys, color=color, lw=lw, dashes=dash or (), solid_capstyle="round", zorder=4)
    if label:
        # Beschriftung auf dem längsten Teilstück
        segs = list(zip(points[:-1], points[1:]))
        a, b = max(segs, key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
        mx, my = a[0] + (b[0] - a[0]) * lpos, a[1] + (b[1] - a[1]) * lpos
        ax.text(mx, my, label, fontsize=5.5, ha="center", va="center", zorder=6, weight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=0.6))


GNYE = "#4c9a2a"
# DC-Buchse -> 24V+ / 24V-
p = PORT[("24V+", 0)]
wire([(jx - 2, 6.6), (jx - 2, p[1]), p], "#d22", "rot")
p = PORT[("24V-", 0)]
wire([(jx + 2, 6.6), (jx + 2, 22), (106, 22), (106, p[1]), p], "#111", "schwarz", lpos=0.3)
# Ader 1: 24V+ -> Vin+ beider Wandler, Ader 2: 24V- -> Vin-
for i, key, lane in ((1, "12", 98.5), (2, "5", 97.0)):
    p, t = PORT[("24V+", i)], TERM[(key, "Vin+")]
    wire([p, (lane, p[1]), (lane, t[1]), t], "#111", "1")
for i, key, lane in ((1, "12", 101.5), (2, "5", 100.0)):
    p, t = PORT[("24V-", i)], TERM[(key, "Vin−")]
    wire([p, (lane, p[1]), (lane, t[1]), t], "#111", "2")
# gn-ge: V- beider Wandler -> GND, Bruecke GND <-> GND 2
for i, key, lane in ((0, "12", 104.0), (1, "5", 103.0)):
    p, t = PORT[("GND", i)], TERM[(key, "V−")]
    wire([p, (lane, p[1]), (lane, t[1]), t], GNYE, "gn-ge")
wire([PORT[("GND", 4)], (108, PORT[("GND", 4)][1]), (108, PORT[("GND 2", 0)][1]), PORT[("GND 2", 0)]], GNYE,
     "gn-ge", lw=1.1)

# Aussenkabel YSLY-JZ 10 x 0,75 von der Bohrung (gleiche Nummern wie innen)
K = "#111"
wire([(bx - 4, by + 8), (bx - 4, 133 - 6), (110, 127), (110, PORT[("24V+", 4)][1]), PORT[("24V+", 4)]],
     K, "außen 1 (Ring +)", lpos=0.35)
wire([(bx - 2, by + 9), (bx - 2, 128.5), (109, 128.5), (109, PORT[("24V-", 4)][1]), PORT[("24V-", 4)]],
     K, "außen 2 (Ring −)", lpos=0.7)
wire([(bx - 6, by + 7), (bx - 6, 125.5), (111, 125.5), (111, PORT[("GND", 2)][1]), PORT[("GND", 2)]],
     GNYE, "außen gn-ge (Tastatur GND)", lpos=0.5)
t = TERM[("12", "V+")]
wire([(bx - 8, by + 5), (bx - 8, 130.5), (96, 130.5), (96, t[1]), t], K, "außen 3 (+12 V Tastatur)",
     lpos=0.25)
for lab, num, dy in (("D0 a", "5", -6), ("D1 a", "6", -3), ("LED", "7", 3), ("BEEP", "8", 6)):
    p = PORT[(lab, 1)]
    lane = 172 + (dy + 6) * 0.6
    names = {"D0 a": "D0", "D1 a": "D1", "LED": "LED", "BEEP": "BEEP"}
    wire([(bx - br + 1, by + dy), (lane, by + dy), (lane, p[1]), p], K, f"außen {num} ({names[lab]})",
         lpos=0.82 if lab in ("LED", "BEEP") else 0.5)

# Ader 5/6: Bruecke a <-> b (nur ohne Spannungsteiler)
for a, b, n in (("D0 a", "D0 b", "5"), ("D1 a", "D1 b", "6")):
    pa, pb = PORT[(a, 2)], PORT[(b, 0)]
    wire([pa, (168, pa[1]), (168, pb[1]), pb], "#111", n + " (ohne Teiler)", dash=(3, 2), lw=1.0)

# Grove: rot 5 V -> SD-5 V+, schwarz -> GND, weiß G1 -> D0 b, gelb G2 -> D1 b
# alle vier zuerst nach unten bis knapp ueber die Cat-7-Oeffnung, dann nach links in eigene Spuren
gx, gy = GROVE
Y0 = 71.0
t = TERM[("5", "V+")]
wire([(gx - 3, gy - 2.5), (gx - 3, Y0 - 3), (174, Y0 - 3), (174, 3.5), (95, 3.5), (95, t[1]), t], "#d22",
     "Grove rot (5 V)", lpos=0.4)
p = PORT[("GND", 3)]
wire([(gx - 1, gy - 2.5), (gx - 1, Y0 - 1), (138, Y0 - 1), (138, 70.4), (107, 70.4), (107, p[1]), p], "#111",
     "Grove schwarz (GND)", lpos=0.6)
p = PORT[("D0 b", 2)]
wire([(gx + 1, gy - 2.5), (gx + 1, Y0 + 1), (176.5, Y0 + 1), (176.5, p[1]), p], "#999", "Grove weiß → G1",
     lpos=0.5)
p = PORT[("D1 b", 2)]
wire([(gx + 3, gy - 2.5), (gx + 3, Y0 + 3), (170.5, Y0 + 3), (170.5, p[1]), p], "#e6c200", "Grove gelb → G2",
     lpos=0.5)

# LED/BEEP: Wago -> BAT85 -> Dupont -> G5/G6
for lab, g, yy in (("LED", G5, 0), ("BEEP", G6, 0)):
    p = PORT[(lab, 2)]
    mid = (180, p[1])
    wire([p, mid], "#666", lw=1.0)
    ax.add_patch(Rectangle((mid[0], mid[1] - 1.2), 5, 2.4, fc="#c33", ec="#600", zorder=6))
    ax.plot([mid[0] + 4.2, mid[0] + 4.2], [mid[1] - 1.2, mid[1] + 1.2], color="black", lw=1.2, zorder=7)
    wire([(mid[0] + 5, mid[1]), (190, mid[1]), (190, g[1]), g], "#666", "Dupont", lw=1.0, lpos=0.3)
ax.text(180, PORT[("LED", 2)][1] - 3.6, "BAT85, Ring zum Atom", fontsize=5, color="#600")

# ---------------- Texte ----------------
fig.text(12 * MM * 25.4 / 297, 0.955, "Verkabelungsplan Inneneinheit – AD.NET Access", fontsize=13, weight="bold",
         transform=fig.transFigure)
fig.text(12 / 297, 0.925, "Blick von vorn, Deckel ab · Gehäuse im Maßstab 1:1 (mit 100 % drucken) · "
         "Kabel laufen über die Wagos (darüber ca. 25 mm frei)", fontsize=7.5, transform=fig.transFigure)
legend = [
    ("1", "24 V + : außen Ring + · innen Wago 24V+ → Eingang Vin+ beider Wandler"),
    ("2", "24 V − : außen Ring − · innen Wago 24V− → Eingang Vin− beider Wandler"),
    ("3", "+12 V : SD-15B-12 Klemme +V → Tastatur rot"),
    ("gn-ge", "GND : Tastatur schwarz · innen Ausgang −V beider Wandler → GND, Brücke GND ↔ GND 2"),
    ("5 / 6", "D0 / D1 : Tastatur grün / weiß → Wago D0 a / D1 a · innen Brücke a ↔ b nur ohne Spannungsteiler"),
    ("7 / 8", "LED / BEEP : Tastatur blau / gelb → Wago LED / BEEP"),
    ("4, 9", "Reserve (4 innen ggf. als 5-V-Verlängerung)"),
]
y0 = 0.205
fig.text(12 / 297, y0, "Adern YSLY-JZ 10 × 0,75 mm² – außen und innen dieselben Nummern", fontsize=8, weight="bold")
for i, (n, t) in enumerate(legend):
    fig.text(12 / 297, y0 - 0.026 * (i + 1), n, fontsize=7.5, weight="bold")
    fig.text(28 / 297, y0 - 0.026 * (i + 1), t, fontsize=7.5)
fig.text(190 / 297, y0, "Hinweise", fontsize=8, weight="bold")
notes = ["Außenkabel: Belegung siehe README (1/2 = Ring 24 V).",
         "24 V− (Ring-Kreis) und GND sind getrennt – nicht verbinden.",
         "Klemmenreihenfolge der Wandler laut Aufdruck am Gerät",
         "  (Vin+/Vin− Eingang, +V/−V Ausgang).",
         "Vor dem Anschluss von Tastatur/Atom: 12 V / 5 V messen.",
         "LED/BEEP erst nach dem Messen anschließen."]
for i, t in enumerate(notes):
    fig.text(190 / 297, y0 - 0.026 * (i + 1), t, fontsize=7.5)
fig.savefig(OUT)
print("geschrieben:", OUT)
