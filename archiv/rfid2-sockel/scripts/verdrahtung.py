"""Zeichnet den Verdrahtungsplan des Zutrittsmoduls -> zutritt/images/verdrahtung.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "images" / "verdrahtung.png"
fig, ax = plt.subplots(figsize=(15, 10.2), dpi=110)
ax.set_xlim(0, 150); ax.set_ylim(-3, 104); ax.axis("off")
INK, MUTED = "#222326", "#6b6e75"
C = {"24": "#d1453b", "gnd": "#222326", "5v": "#e08a1e", "sda": "#2f7fd6", "scl": "#3aa564", "din": "#8a5cc9"}


def block(x, y, w, h, title, sub="", fc="#f4f4f2", ec=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=10.5, weight="bold", color=INK)
    if sub:
        ax.text(x + w / 2, y + h - 5.6, sub, ha="center", va="top", fontsize=8.5, color=MUTED)


def wire(pts, c, label=None, lpos=0, dy=0.9):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=c, lw=2.2, solid_capstyle="round", zorder=3)
    if label:
        (x0, y0), (x1, y1) = pts[lpos], pts[lpos + 1]
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + dy, label, ha="center", va="bottom", fontsize=7.8, color=c, zorder=4)


# Zonen
ax.add_patch(plt.Rectangle((0, 0), 74, 100, fc="#fbfbfa", ec="none"))
ax.add_patch(plt.Rectangle((80, 0), 70, 100, fc="#eef1f4", ec="none"))
ax.add_patch(plt.Rectangle((74, 0), 6, 100, fc="#cfccc6", ec="none", hatch="///"))
ax.text(37, 101.5, "INNEN  (Inneneinheit an der Innenwand)", ha="center", fontsize=11, weight="bold", color=MUTED)
ax.text(115, 101.5, "AUSSEN  (Sockel unter der Klingelplatte)", ha="center", fontsize=11, weight="bold", color=MUTED)
ax.text(77, 99.6, "Wand", rotation=0, ha="center", va="center", fontsize=9, color=MUTED)


def dot(x, y, c):
    ax.plot([x], [y], "o", color=c, ms=6, zorder=5)


# Bloecke innen
block(4, 82, 18, 12, "Netzteil 24 V DC", "Mean Well GST36E24", fc="#ffffff")
block(4, 63, 18, 12, "Hohlstecker-", "Adapter auf\nSchraubklemme")
block(30, 80, 12, 10, "Wago", "221-414\n+24 V", fc="#fdf0dd")
block(46, 78, 12, 10, "Wago", "221-414\nGND", fc="#fdf0dd")
block(28, 62, 16, 9, "Sicherung", "0,5 A träge")
block(26, 40, 20, 13, "Wandler 24→5 V", "Schraubklemme rein\nUSB-C raus")
block(40, 14, 30, 22, "AtomS3 Lite", "ESPHome · WLAN → HA\n\nGrove:  GND  5V  G2  G1", fc="#e9ebee")
# Bloecke aussen
block(86, 76, 58, 22, "Ring links / Ring rechts", "Klemmen an der Klingel")
block(100, 40, 30, 17, "Unit RFID2", "WS1850S · I²C 0x28\nim Sockel unter der Platte")
block(86, 3, 58, 11, "NFC-Aufkleber unter dem Dach", "kein Strom, kein Kabel · Handy oben aufs Dach legen", fc="#ffffff")

# 24 V
wire([(13, 82), (13, 75)], C["24"]); ax.text(14, 78.5, "Hohlstecker", fontsize=7.8, color=C["24"], va="center")
wire([(22, 71), (26, 71), (26, 86), (30, 86)], C["24"])
wire([(22, 67), (24, 67), (24, 58), (52, 58), (52, 78)], C["gnd"])
wire([(52, 58), (52, 47), (46, 47)], C["gnd"]); dot(52, 58, C["gnd"])
wire([(36, 80), (36, 71)], C["24"])
wire([(36, 62), (36, 53)], C["24"])
wire([(36, 40), (36, 20), (40, 20)], C["5v"]); ax.text(35, 30, "USB-C\n5 V", fontsize=7.8, color=C["5v"], ha="right", va="center")
# Kabel 1 zu den Klingeln
wire([(33, 90), (33, 95), (86, 95)], C["24"])
wire([(39, 90), (39, 92.5), (86, 92.5)], C["24"])
wire([(58, 85), (86, 85)], C["gnd"])
wire([(58, 81), (86, 81)], C["gnd"])
for y, t in ((95, "L+"), (92.5, "R+"), (85, "L−"), (81, "R−")):
    ax.text(87.2, y, t, va="center", fontsize=8, color=INK, weight="bold")
# Kabel 2 zum Leser
for i, (k, t) in enumerate((("gnd", "GND"), ("5v", "5V"), ("sda", "SDA"), ("scl", "SCL"))):
    y, x = 29 - i * 1.6, 106 + i * 4
    wire([(70, y), (x, y), (x, 40)], C[k])
    ax.text(x + 0.6, 36, t, fontsize=6.8, color=C[k], rotation=90, va="top")
# EIN Kabel durch EINE Bohrung: Mantel als graues Band
ax.add_patch(FancyBboxPatch((71.5, 22.5), 11, 74, boxstyle="round,pad=0.2,rounding_size=4", fc="#9a9ca1", ec="none",
                            alpha=0.35, zorder=2))
ax.text(77, 55, "1 Bohrung · 1 Kabel\nJ-Y(St)Y 4×2×0,6\n(alle 8 Adern)", ha="center", va="center", fontsize=7.8,
        color=INK, bbox=dict(fc="white", ec=MUTED, lw=0.8, boxstyle="round,pad=0.35"), zorder=6)

ax.text(1, -2.5, "Alle Verbindungen ohne Löten: Wago-Hebelklemmen (24 V), Grove-auf-Dupont-Kabel (Buchsen stecken direkt auf "
        "den 0,6-mm-Adern, mit Schrumpfschlauch sichern).   Der Shelly am Motorschloss hängt NICHT hier dran, HA schaltet ihn per WLAN.",
        fontsize=8.2, color=MUTED)
fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print("ok", OUT)
