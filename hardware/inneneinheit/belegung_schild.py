"""Belegungsschild zum Einkleben innen in den Deckel (74 x 114 x 1,6 mm).

Schrift: Inter ExtraBold, 3,5 mm Versalhoehe -> Strichstaerke ca. 0,8 mm (2 Linien mit 0,4er-Duese).

Erzeugt stl/belegung_schild.stl (Schrift 0,6 mm vertieft) und stl/belegung_schild_schrift.stl
(passende Einlage fuer zweifarbigen Druck: beide zusammen als ein Objekt laden).
Die Schrift liegt auf der Unterseite (Druckbett) und ist gespiegelt - nach dem Druck umdrehen.
"""
from pathlib import Path

import trimesh
from manifold3d import CrossSection, FillRule, JoinType
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

BASE = Path(__file__).resolve().parent
OUT = BASE / "stl"
FONT = str(BASE / "fonts" / "Inter-ExtraBold.otf")
W, H, T, DEPTH = 74.0, 114.0, 1.6, 0.6
CAP, LINE = 3.5, 5.3


def text_cs(s, cap):
    tp = TextPath((0, 0), s, size=100, prop=FontProperties(fname=FONT))
    polys = [p for p in tp.to_polygons(closed_only=True) if len(p) > 2]
    cs = CrossSection(polys, fillrule=FillRule.EvenOdd)
    ref = TextPath((0, 0), "H", size=100, prop=FontProperties(fname=FONT)).get_extents().height
    return cs.scale((cap / ref, cap / ref))


ADERN = [("gn-ge", "GND / alle Minus"), ("1", "24 V +"), ("2", "24 V −"), ("3", "12 V + Tastatur"),
         ("4", "5 V + Atom"), ("5", "D0"), ("6", "D1"), ("7", "LED"), ("8", "BEEP"), ("9", "Reserve")]
ATOM = [("G1", "D0 (Grove)"), ("G2", "D1 (Grove)"), ("5V+GND", "Grove"), ("G5", "LED (BAT85)"),
        ("G6", "BEEP (BAT85)"), ("G7", "Temp. DS18B20")]

x0, x1 = 4.0, 27.0
y = H - 8.5
txt = CrossSection()
txt += text_cs("Belegung", 4.0).translate((x0, y))
y -= LINE + 1.5
txt += text_cs("Ader", 3.0).translate((x0, y)) + text_cs("Funktion", 3.0).translate((x1, y))
for a, f in ADERN:
    y -= LINE
    txt += text_cs(a, CAP).translate((x0, y)) + text_cs(f, CAP).translate((x1, y))
y -= LINE + 2.0
txt += text_cs("Atom", 3.0).translate((x0, y)) + text_cs("Signal", 3.0).translate((x1, y))
for a, f in ATOM:
    y -= LINE
    txt += text_cs(a, CAP).translate((x0, y)) + text_cs(f, CAP).translate((x1, y))
assert y > 2.5, f"Text zu lang (y={y:.1f})"
b = txt.bounds()
assert b[2] < W - 3, f"Text zu breit ({b[2]:.1f} mm)"

plate = (CrossSection.square((W - 6, H - 6)).offset(3, JoinType.Round, circular_segments=32)
         .translate((3, 3))).extrude(T)
# Trennlinie zwischen den Tabellen
# Schrift liegt UNTEN (Sichtseite auf dem Druckbett, gespiegelt): erste Schichten = scharfe Kanten,
# kein Glaetten noetig, kein Verschmieren der Farbe. Nach dem Druck umdrehen.
mtxt = txt.mirror((1, 0)).translate((W, 0))
inlay = mtxt.extrude(DEPTH)
plate -= mtxt.extrude(DEPTH + 0.01).translate((0, 0, -0.01))


def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts)
    tm.export(OUT / name)
    bb = tm.bounds
    print(f"{name:30s} {' x '.join(f'{v:.1f}' for v in bb[1] - bb[0])} mm  {'ok' if tm.is_watertight else 'NICHT WASSERDICHT'}")


save(plate, "belegung_schild.stl")
save(inlay, "belegung_schild_schrift.stl")
print(f"Text endet bei y={y:.1f} mm, breiteste Zeile {b[2]:.1f} mm")
