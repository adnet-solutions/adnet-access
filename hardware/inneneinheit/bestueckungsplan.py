"""Zeichnet den Bestückungsplan (images/bestueckung_plan.png) aus stl/innen_layout.json.
    python3 hardware/inneneinheit/generate_innen.py && python3 hardware/inneneinheit/bestueckungsplan.py"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

BASE = Path(__file__).resolve().parent
L = json.loads((BASE / "stl" / "innen_layout.json").read_text())
W, H = L["in_w"], L["in_h"]
fig, ax = plt.subplots(figsize=(14, 9), dpi=130)
ax.add_patch(FancyBboxPatch((-2.4, -2.4), W + 4.8, H + 4.8, boxstyle="round,pad=0,rounding_size=10",
                            fc="#f4f4f4", ec="#555", lw=2))


def comp(x, y, w, h, txt, fc, fs=11, tc="black"):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec="#333", lw=1.2))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, color=tc, weight="bold")


for name, (x, y, w, h) in L["sd"].items():
    v = "12 V (Tastatur)" if "12" in name else "5 V (Atom)"
    comp(x, y, w, h, f"Mean Well {name.split(' ')[0]}\n24 V → {v}", "#f7e3df" if "12" in name else "#dfe9f7")
    comp(x + w, y + 3, L["sd_term"], h - 6, "Klemmen", "#222", fs=7, tc="white")
for x, y, w, h, lbl, n in L["wago1"] + L["wago2"]:
    comp(x, y, w, h, f"{lbl}\n221-41{n}", "#ffc270" if n == 5 else "#ffd9a0", fs=9)
ax_, ay, aw = L["atom"]
comp(ax_, ay, aw, aw, "AtomS3\nLite", "#333", fs=9, tc="white")
ax.text(ax_ + aw / 2, ay - 2, "USB-C ↑ oben · Grove ↓ unten", ha="center", va="top", fontsize=7.5)
dx, dy, dw, dl = L["delock"]
comp(dx, dy, dw, dl, "Delock\n24 V IN", "#444", fs=8, tc="white")
bx, by, br = L["bore"]
ax.add_patch(Circle((bx, by), br, fc="white", ec="#333", lw=1.5))
ax.text(bx, by, "Cat 7\n(von hinten)", ha="center", va="center", fontsize=8)
ax.add_patch(Rectangle((L["notch"] - 5, -2.4), 10, 2.4, fc="#c33"))
ax.text(L["notch"], -6, "Kerbe Netzteilkabel", ha="center", fontsize=8, color="#c33")
ax.add_patch(Rectangle((L["pry"] - 5, -2.4), 10, 2.4, fc="#36c"))
ax.text(L["pry"], -6, "Hebelkerbe Deckel", ha="center", fontsize=8, color="#36c")
x0 = L["wago1"][0][0]
ax.annotate("", xy=(x0 - 0.5, 8), xytext=(x0 - 12, 8), arrowprops=dict(arrowstyle="->"))
ax.text(x0 - 6, 11, "Adern von links", ha="center", fontsize=7)
ax.text(W / 2, H + 6, "OBEN  (Kabelkerben zeigen nach unten)", ha="center", fontsize=11, weight="bold")
ax.text(W / 2, -12, "UNTEN", ha="center", fontsize=11, weight="bold")
ax.set_xlim(-8, W + 8); ax.set_ylim(-16, H + 12); ax.set_aspect("equal"); ax.axis("off")
ax.set_title("Inneneinheit – Bestückung (Blick von vorn, Deckel ab)", fontsize=14, weight="bold")
plt.tight_layout()
plt.savefig(BASE / "images" / "bestueckung_plan.png", facecolor="white")
print("ok", BASE / "images" / "bestueckung_plan.png")
