"""Belegungsschild zum Einkleben innen in den Deckel (70 x 108 x 1,6 mm).

Erzeugt stl/belegung_schild.stl (Schrift 0,6 mm vertieft) und stl/belegung_schild_schrift.stl
(passende Einlage fuer zweifarbigen Druck: beide zusammen als ein Objekt laden).
"""
from pathlib import Path

import trimesh
from manifold3d import CrossSection, FillRule, JoinType
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

BASE = Path(__file__).resolve().parent
OUT = BASE / "stl"
FONT = str(BASE / "fonts" / "Inter-SemiBold.otf")
W, H, T, DEPTH = 70.0, 108.0, 1.6, 0.6
CAP, LINE = 3.0, 5.0


def text_cs(s, cap):
    tp = TextPath((0, 0), s, size=100, prop=FontProperties(fname=FONT))
    polys = [p for p in tp.to_polygons(closed_only=True) if len(p) > 2]
    cs = CrossSection(polys, fillrule=FillRule.EvenOdd)
    ref = TextPath((0, 0), "H", size=100, prop=FontProperties(fname=FONT)).get_extents().height
    return cs.scale((cap / ref, cap / ref))


ADERN = [("gn-ge", "GND / alle Minus"), ("1", "24 V +"), ("2", "24 V −"), ("3", "12 V + Tastatur"),
         ("4", "5 V + Atom"), ("5", "D0"), ("6", "D1"), ("7", "LED"), ("8", "BEEP"), ("9", "Reserve")]
ATOM = [("G1", "D0 (Grove)"), ("G2", "D1 (Grove)"), ("5V/GND", "Grove"), ("G5", "LED über BAT85"),
        ("G6", "BEEP über BAT85"), ("G7", "Temp. DS18B20")]

x0, x1 = 5.0, 25.0
y = H - 8.0
txt = CrossSection()
txt += text_cs("Belegung Inneneinheit", 3.4).translate((x0, y))
y -= LINE + 2.0
txt += text_cs("Ader", 2.6).translate((x0, y)) + text_cs("Funktion", 2.6).translate((x1, y))
for a, f in ADERN:
    y -= LINE
    txt += text_cs(a, CAP).translate((x0, y)) + text_cs(f, CAP).translate((x1, y))
y -= LINE + 3.0
txt += text_cs("Atom", 2.6).translate((x0, y)) + text_cs("Signal", 2.6).translate((x1, y))
for a, f in ATOM:
    y -= LINE
    txt += text_cs(a, CAP).translate((x0, y)) + text_cs(f, CAP).translate((x1, y))
assert y > 3.0, f"Text zu lang (y={y:.1f})"
b = txt.bounds()
assert b[2] < W - 3, f"Text zu breit ({b[2]:.1f} mm)"

plate = (CrossSection.square((W - 6, H - 6)).offset(3, JoinType.Round, circular_segments=32)
         .translate((3, 3))).extrude(T)
# Trennlinie zwischen den Tabellen
inlay = txt.extrude(DEPTH).translate((0, 0, T - DEPTH))
plate -= txt.extrude(DEPTH + 0.01).translate((0, 0, T - DEPTH))


def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts)
    tm.export(OUT / name)
    bb = tm.bounds
    print(f"{name:30s} {' x '.join(f'{v:.1f}' for v in bb[1] - bb[0])} mm  {'ok' if tm.is_watertight else 'NICHT WASSERDICHT'}")


save(plate, "belegung_schild.stl")
save(inlay, "belegung_schild_schrift.stl")
print(f"Text endet bei y={y:.1f} mm, breiteste Zeile {b[2]:.1f} mm")
