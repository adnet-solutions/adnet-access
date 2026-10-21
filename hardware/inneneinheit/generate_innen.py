"""Inneneinheit des Zutrittsmoduls (Version 2): flaches, weisses Aufputzgehaeuse an der Innenwand.

Inhalt (alles ohne Loeten, jedes Teil hat eine eigene Aufnahme):
  - DC-Einbaubuchse 5,5 x 2,1 (Loch 11 mm, mit angeloeteten Adern) in der Unterseite: Netzteil GST60A24 wird von aussen eingesteckt
  - Mean Well SD-15B-12 (24 -> 12 V, Wiegand-Tastatur) und SD-15B-5 (24 -> 5 V, Atom)
  - M5Stack AtomS3 Lite (ESPHome)
  - 3 x WAGO 221-415 (24 V+, 24 V-, GND) + 7 x WAGO 221-413 (GND 2, Spannungsteiler D0/D1, LED, BEEP)
  - Atom auf einem 16 mm hohen Podest: unten frei fuer zwei Dupont-Stecker (G5 = LED, G6 = BEEP ueber BAT85)
  - Oeffnung ueber der Wandbohrung (Cat-7-Kabel von hinten), Kerbe fuer das Netzteilkabel

Druckteile:  innen_unterteil.stl, innen_deckel.stl, innen_niederhalter.stl (2 x drucken)
Deckel:      wird aufgeschnappt (6 Rasthaken), Oeffnen mit Schlitzschraubendreher an der Kerbe unten Mitte
Schrauben:   4 x 2,9 x 13 Linsenkopf (Niederhalter), 2 x 4 x 30 + Duebel (Wand)

Koordinaten: Blick von vorn auf das geoeffnete Gehaeuse, Ursprung = linke untere Innenecke.
    python3 hardware/inneneinheit/generate_innen.py
"""
import json

import numpy as np
from pathlib import Path

import trimesh
from manifold3d import Manifold, CrossSection, JoinType, FillRule

BASE = Path(__file__).resolve().parent
OUT = BASE / "stl"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------- Bauteilmasse (vor dem Druck am echten Teil pruefen!) ----------------
SD_L, SD_W, SD_H = 78.0, 51.0, 28.0        # Mean Well SD-15 (Datenblatt 78 x 51 x 28)
ATOM = 24.0                                # AtomS3 Lite 24 x 24 x 9.5
DELOCK_L, DELOCK_W, DELOCK_H = 27.0, 18.0, 15.0
WAGO_D, WAGO_H = 18.6, 8.4                 # WAGO 221: Tiefe (Leitereinfuehrung -> Rueckseite), Hoehe (Datenblatt)
WAGO_W = {3: 18.6, 5: 29.6}                # Breite je Polzahl: 221-413 nachgemessen 18,56; 221-415 hochgerechnet
SD_TERM = 12.5                             # Klemmleiste ragt ueber das Blechgehaeuse hinaus (nachgemessen: 90,5 mm gesamt)
WIRE_ROOM = 17.5                           # Platz fuer Adern zwischen Klemmleiste und Wagos
CLR = 0.5                                  # Spiel in allen Aufnahmen
WCLR = 0.3                                 # Spiel der Wagos quer
WNOSE = 0.9                                # Rastnasen an den Wago-Seitenwaenden

# ---------------- Gehaeuse ----------------
IN_W, IN_H = 224.0, 132.0                  # Innenraum (x, y)
WALL, FLOOR, LID = 2.4, 2.4, 2.4
IN_Z = SD_H + 4.0 + 2.0                    # lichte Hoehe: Wandler + Niederhalter + Luft = 34 mm
R_OUT = 10.0                               # grosse Eckenradien wie die Klingelplatte
BOSS_D, BOSS_HOLE = 8.0, 2.5               # Schraubdome fuer 2,9er Blechschrauben

BORE = (202.0, 52.0)                       # Mitte der Wandbohrung (Cat 7 kommt von hinten)
BORE_OPEN = 22.0
NOTCH_X = 103.0                            # DC-Einbaubuchse unten im Adergang links der Wagos -> kurze Wege zu 24V+/24V-
JACK_D, JACK_Z = 8.3, 22.0                 # Loch DC-Einbaubuchse DC-099 (M8); fuer M11-Typen auf 11,4 aufbohren; Hoehe Mitte


def rrect(w, h, r, n=48):
    return CrossSection.square((w - 2 * r, h - 2 * r), center=True).offset(r, JoinType.Round, circular_segments=n)


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cyl(x, y, r, z0, z1, n=48):
    return Manifold.cylinder(z1 - z0, r, r, n).translate((x, y, z0))


Z0 = FLOOR                                 # Oberkante Boden innen
H_OUT = FLOOR + IN_Z
cx, cy = IN_W / 2, IN_H / 2

shell = rrect(IN_W + 2 * WALL, IN_H + 2 * WALL, R_OUT).extrude(H_OUT).translate((cx, cy, 0))
shell -= rrect(IN_W, IN_H, R_OUT - WALL).extrude(H_OUT).translate((cx, cy, FLOOR))
parts_demo = []   # Platzhalter fuer die Vorschau


def frame(x0, y0, w, h, wall_h, sides="LRBT", gap=None, t=1.6):
    """Aufnahme: niedrige Rahmenwaende um eine Grundflaeche (x0,y0,w,h). gap = Aussparungen [(seite, von, bis)]."""
    m = Manifold()
    s = {"L": box(x0 - t, x0, y0 - t, y0 + h + t, Z0 - 0.01, Z0 + wall_h),
         "R": box(x0 + w, x0 + w + t, y0 - t, y0 + h + t, Z0 - 0.01, Z0 + wall_h),
         "B": box(x0 - t, x0 + w + t, y0 - t, y0, Z0 - 0.01, Z0 + wall_h),
         "T": box(x0 - t, x0 + w + t, y0 + h, y0 + h + t, Z0 - 0.01, Z0 + wall_h)}
    for k in sides:
        m += s[k]
    for (side, a, b) in (gap or []):
        if side in "BT":
            yy = y0 - t - 1 if side == "B" else y0 + h - 1
            m -= box(x0 + a, x0 + b, yy, yy + t + 2, Z0, Z0 + wall_h + 1)
        else:
            xx = x0 - t - 1 if side == "L" else x0 + w - 1
            m -= box(xx, xx + t + 2, y0 + a, y0 + b, Z0, Z0 + wall_h + 1)
    return m


def snap_noses(x0, y0, w, h, z_top, along="y", depth=0.6, length=6.0):
    """Kleine Rastnasen oben an zwei gegenueberliegenden Waenden (halten Wago/Atom nach dem Eindruecken)."""
    m = Manifold()
    if along == "y":   # Nasen an linker und rechter Wand
        yc = y0 + h / 2
        m += box(x0 - 0.01, x0 + depth, yc - length / 2, yc + length / 2, z_top - 1.2, z_top)
        m += box(x0 + w - depth, x0 + w + 0.01, yc - length / 2, yc + length / 2, z_top - 1.2, z_top)
    else:              # Nasen an unterer und oberer Wand
        xc = x0 + w / 2
        m += box(xc - length / 2, xc + length / 2, y0 - 0.01, y0 + depth, z_top - 1.2, z_top)
        m += box(xc - length / 2, xc + length / 2, y0 + h - depth, y0 + h + 0.01, z_top - 1.2, z_top)
    return m


# ---------------- Mean Well SD-15B: zwei Wandler links uebereinander, Klemmen zeigen nach rechts ----------------
SD_X = 3.0
HOLD_OFF, HOLD_R = 4.6, 3.8                 # Dom-Abstand zum Wandler, Dom-Radius
SD_GAP = 2 * (HOLD_OFF)                     # Platz zwischen den Wandlern fuer die Dome
_y_lo = HOLD_OFF + HOLD_R + 0.2
SD_POS = {"SD-15B-5 (5 V)": (SD_X, _y_lo), "SD-15B-12 (12 V)": (SD_X, _y_lo + SD_W + 2 * CLR + SD_GAP)}
SD_BAR_F = {"SD-15B-5 (5 V)": 0.35, "SD-15B-12 (12 V)": 0.65}   # Niederhalter versetzt, damit sich die Dome nicht treffen
HOLD = []
for name, (x, y) in SD_POS.items():
    w, h = SD_L + 2 * CLR, SD_W + 2 * CLR
    # Eckwinkel (8 mm hoch), rechte Seite frei fuer die Schraubklemmen
    shell += frame(x, y, w, h, 8.0, sides="LBT", gap=[("B", 14, w - 14), ("T", 14, w - 14)])
    # vierte Seite (Klemmenseite): nur niedrige Eckanschlaege, damit Klemmen und Adern frei bleiben
    for yy in (y - 1.6, y + h - 2.4):
        shell += box(x + w, x + w + 1.6, yy, yy + 4.0, Z0 - 0.01, Z0 + 2.5)
    bx = x + w * SD_BAR_F[name]
    HOLD += [(bx, y - HOLD_OFF), (bx, y + h + HOLD_OFF)]
    parts_demo.append({"kind": "buck", "w": SD_L, "h": SD_W, "d": SD_H, "x": x + w / 2, "y": y + h / 2, "z": Z0})
assert SD_POS["SD-15B-12 (12 V)"][1] + SD_W + 2 * CLR + HOLD_OFF + HOLD_R <= IN_H, "Wandler passen nicht in die Hoehe"
for (bx, by) in HOLD:
    shell += cyl(bx, by, HOLD_R, Z0 - 0.01, Z0 + SD_H)
    shell -= cyl(bx, by, BOSS_HOLE / 2, Z0 + 4, Z0 + SD_H + 1)

# ---------------- WAGO-Aufnahmen: mittlere Spalte, Leitereinfuehrung zeigt nach links (zu den Wandlern) ----------------
WAGO_X = SD_X + SD_L + 2 * CLR + SD_TERM + WIRE_ROOM   # 112: linke Kante (Einfuehrungsseite)
# Spalte 1: 3 x 221-415 + 1 x 221-413 (GND 2: Bruecke + untere Teilerwiderstaende)
wago_slots, _y = [], 4.0
for _n, _l in ((5, "24V+"), (5, "24V-"), (5, "GND"), (3, "GND 2")):
    wago_slots.append((_n, _y, _l))
    _y += WAGO_W[_n] + WCLR + 4.4
LABEL_GAP = 12.0                  # Gang zwischen den Spalten (Beschriftung Spalte 2)
WAGO2_X = WAGO_X + WAGO_D + CLR + 1.6 + LABEL_GAP + 1.6   # Spalte 2: Einfuehrung zeigt nach RECHTS (Cat 7, Atom)
PITCH2 = WAGO_W[3] + WCLR + 1.6   # 20.6 mm: benachbarte Aufnahmen teilen sich eine Wand
wago_slots2 = [(3, 4.0 + i * PITCH2, lbl) for i, lbl in enumerate(["D0 a", "D0 b", "D1 a", "D1 b", "LED", "BEEP"])]
for _n, _y, _l in wago_slots:
    assert _y + WAGO_W[_n] + WCLR + 1.6 <= IN_H, f"Wago {_l} passt nicht"
for _n, _y, _l in wago_slots2:
    assert _y + WAGO_W[_n] + WCLR + 1.6 <= IN_H, f"Wago {_l} passt nicht"
WALL_H_WAGO = 5.0
for col_x, slots, sides in ((WAGO_X, wago_slots, "RBT"), (WAGO2_X, wago_slots2, "LBT")):
    for (n, y, lbl) in slots:
        w = WAGO_W[n] + WCLR                   # entlang y
        d = WAGO_D + CLR                       # entlang x
        # Spalte 1: Rueckwand rechts, Adern von links (Wandler); Spalte 2: Rueckwand links, Adern von rechts
        shell += frame(col_x, y, d, w, WALL_H_WAGO, sides=sides)
        shell += snap_noses(col_x, y, d, w, Z0 + WALL_H_WAGO, along="x", depth=WNOSE, length=8.0)
        parts_demo.append({"kind": "wago", "w": WAGO_D, "h": WAGO_W[n], "d": WAGO_H,
                           "x": col_x + d / 2, "y": y + w / 2, "z": Z0})

# ---------------- AtomS3 Lite: rechts oben auf einem Podest ----------------
# Die freien Pins (G5-G8, G38, G39, 5V, GND) sind Buchsen an der Unterseite. Der Atom liegt deshalb 16 mm hoch auf
# vier Eckauflagen; darunter ist Platz fuer gerade Dupont-Stecker, die Kabel gehen seitlich durch Fenster raus.
# USB-C zeigt nach oben (zum Flashen erreichbar), Grove nach unten.
ATOM_X, ATOM_Y = 195.0, 96.0
ATOM_LIFT = 16.0
aw = ATOM + CLR
PT = 1.6                                    # Wandstaerke Podest
pod = box(ATOM_X - PT, ATOM_X + aw + PT, ATOM_Y - PT, ATOM_Y + aw + PT, Z0 - 0.01, Z0 + ATOM_LIFT + 6.0)
pod -= box(ATOM_X, ATOM_X + aw, ATOM_Y, ATOM_Y + aw, Z0, Z0 + ATOM_LIFT + 7)
for (cx0, cy0) in ((ATOM_X, ATOM_Y), (ATOM_X + aw - 4.0, ATOM_Y), (ATOM_X, ATOM_Y + aw - 4.0),
                   (ATOM_X + aw - 4.0, ATOM_Y + aw - 4.0)):      # Eckauflagen 4 x 4 mm, Mitte bleibt frei
    pod += box(cx0, cx0 + 4.0, cy0, cy0 + 4.0, Z0, Z0 + ATOM_LIFT)
# Kabelfenster unter der Auflage auf allen vier Seiten, oben Aussparungen fuer USB-C und Grove
for side in ("L", "R"):
    xx = ATOM_X - PT - 1 if side == "L" else ATOM_X + aw - 1
    pod -= box(xx, xx + PT + 2, ATOM_Y + 4.0, ATOM_Y + aw - 4.0, Z0 + 2.0, Z0 + ATOM_LIFT - 1.0)
for side in ("B", "T"):
    yy = ATOM_Y - PT - 1 if side == "B" else ATOM_Y + aw - 1
    pod -= box(ATOM_X + 4.0, ATOM_X + aw - 4.0, yy, yy + PT + 2, Z0 + 2.0, Z0 + ATOM_LIFT - 1.0)
    pod -= box(ATOM_X + 6.0, ATOM_X + aw - 6.0, yy, yy + PT + 2, Z0 + ATOM_LIFT, Z0 + ATOM_LIFT + 7)
shell += pod
shell += snap_noses(ATOM_X, ATOM_Y, aw, aw, Z0 + ATOM_LIFT + 6.0, along="y", length=8.0)
assert ATOM_LIFT + 9.5 + 2.0 <= IN_Z, "Atom stoesst am Deckel an"
parts_demo.append({"kind": "atom", "w": ATOM, "h": ATOM, "d": 9.5, "x": ATOM_X + aw / 2, "y": ATOM_Y + aw / 2,
                   "z": Z0 + ATOM_LIFT})

# ---------------- DC-Einbaubuchse in der Unterseite (Netzteil wird von aussen eingesteckt) ----------------
_jack = Manifold.cylinder(WALL + 4, JACK_D / 2, JACK_D / 2, 64).rotate((-90, 0, 0)).translate((NOTCH_X, -WALL - 1, Z0 + JACK_Z))
_pad = Manifold.cylinder(1.6, 7.5, 7.5, 64).rotate((-90, 0, 0)).translate((NOTCH_X, -0.01, Z0 + JACK_Z))  # Verstaerkung innen
shell += _pad - box(NOTCH_X - 12, NOTCH_X + 12, -1, 3, -5, Z0)       # nicht unter den Boden ragen
shell -= _jack
DL_X, DL_Y, dw, dl = NOTCH_X - 8.0, 0.0, 16.0, 18.0                  # Bereich der Buchse innen (fuer Plan/Beschriftung)
parts_demo.append({"kind": "delock", "w": 14.0, "h": 16.0, "d": 14.0, "x": NOTCH_X, "y": 9.0, "z": Z0 + JACK_Z - 7})

# ---------------- Wanddurchbruch (Cat 7) mit Kragen + Kabelbinder-Bruecken ----------------
shell += cyl(*BORE, BORE_OPEN / 2 + 1.6, Z0 - 0.01, Z0 + 3.0)
shell -= cyl(*BORE, BORE_OPEN / 2, -1, Z0 + 4)


def tie_bridge(x, y, along_x=True):
    if along_x:
        b = box(x - 4, x + 4, y - 3, y + 3, Z0 - 0.01, Z0 + 3.6) - box(x - 2.6, x + 2.6, y - 4, y + 4, Z0 - 0.5, Z0 + 1.8)
    else:
        b = box(x - 3, x + 3, y - 4, y + 4, Z0 - 0.01, Z0 + 3.6) - box(x - 4, x + 4, y - 2.6, y + 2.6, Z0 - 0.5, Z0 + 1.8)
    return b


for (tx, ty, ax) in ((BORE[0], BORE[1] + 24, True), (190.0, 86.0, False), (NOTCH_X, 30.0, True)):
    shell += tie_bridge(tx, ty, ax)

# ---------------- Kerbe fuer das Netzteilkabel (Unterkante, zum Deckel hin offen) ----------------

# ---------------- Schnapp-Deckel: Rasthaken am Deckel, Nuten in der Gehaeusewand ----------------
# Positionen symmetrisch, weil der Deckel zum Drucken gewendet wird (x gespiegelt).
HOOK_W, HOOK_T, HOOK_L, BUMP = 10.0, 1.6, 10.0, 1.0
LIP_IN = 0.35                               # Abstand Haken-Aussenseite zur Innenwand
HOOKS = [("B", 16.0), ("B", IN_W - 16.0), ("T", 16.0), ("T", IN_W - 16.0), ("L", IN_H / 2), ("R", IN_H / 2)]
# Lage der Rastnase relativ zur Deckelunterseite (installiert, nach unten gemessen)
BUMP_TOP = HOOK_L - 3.2                     # Haltekante
BUMP_BOT = HOOK_L - 0.4
for side, pos in HOOKS:
    z1, z0 = H_OUT - BUMP_TOP + 0.3, H_OUT - BUMP_BOT - 0.3
    if side == "B":
        shell -= box(pos - HOOK_W / 2 - 0.6, pos + HOOK_W / 2 + 0.6, -1.2, 0.01, z0, z1)
    elif side == "T":
        shell -= box(pos - HOOK_W / 2 - 0.6, pos + HOOK_W / 2 + 0.6, IN_H - 0.01, IN_H + 1.2, z0, z1)
    elif side == "L":
        shell -= box(-1.2, 0.01, pos - HOOK_W / 2 - 0.6, pos + HOOK_W / 2 + 0.6, z0, z1)
    else:
        shell -= box(IN_W - 0.01, IN_W + 1.2, pos - HOOK_W / 2 - 0.6, pos + HOOK_W / 2 + 0.6, z0, z1)
# Hebelkerbe zum Oeffnen: unten Mitte, aussen in der Oberkante
PRY_W = 10.0
shell -= box(cx - PRY_W / 2, cx + PRY_W / 2, -WALL - 1, -WALL + 1.0, H_OUT - 1.6, H_OUT + 1)

# ---------------- Vorgeprägte Bohrstellen fuer Kabelverschraubung M12 (optional, z. B. eigenes Ring-Kabel) ----------------
# Aussen 12,2 mm Kreis, 1,6 mm tief, innen bleibt 0,8 mm Wand stehen -> bleibt dicht, bis man aufbohrt (Stufenbohrer).
KO_D, KO_LEFT, KO_Z = 12.2, 0.8, 17.0
KNOCKOUTS = [("R", 25.0), ("T", 180.0), ("B", 180.0)]     # rechts unten, oben rechts, unten rechts (innen frei)


def knockout(side, pos):
    depth = WALL - KO_LEFT
    c = Manifold.cylinder(depth + 1, KO_D / 2, KO_D / 2, 64)          # entlang +z
    d = Manifold.cylinder(0.4, 1.5, 0.6, 24)                          # Zentrierkoernung (0,4 tief)
    m = c + d.translate((0, 0, depth + 1 - 0.01))
    z = Z0 + KO_Z
    if side == "R":
        return m.rotate((0, -90, 0)).translate((IN_W + WALL + 1, pos, z))
    if side == "T":
        return m.rotate((90, 0, 0)).translate((pos, IN_H + WALL + 1, z))
    return m.rotate((-90, 0, 0)).translate((pos, -WALL - 1, z))


for side, pos in KNOCKOUTS:
    shell -= knockout(side, pos)

# ---------------- Wandbefestigung: 2 Senkkopfloecher 4 x 30 ----------------
for (wx, wy) in ((97.5, (SD_POS["SD-15B-5 (5 V)"][1] + SD_W + 2 * CLR + SD_POS["SD-15B-12 (12 V)"][1]) / 2), (186.0, 72.0)):
    shell -= cyl(wx, wy, 2.25, -1, Z0 + 1)
    shell -= Manifold.cylinder(2.26, 2.25, 4.5, 48).translate((wx, wy, Z0 - 2.25))

# ---------------- Beschriftung im Boden (vertieft 0.4 mm) ----------------
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
FONT = str(BASE / "fonts" / "Inter-SemiBold.otf")


def text_cs(s, cap, center=True):
    tp = TextPath((0, 0), s, size=100, prop=FontProperties(fname=FONT))
    polys = [p for p in tp.to_polygons(closed_only=True) if len(p) > 2]
    cs = CrossSection(polys, fillrule=FillRule.EvenOdd)
    capref = TextPath((0, 0), "H", size=100, prop=FontProperties(fname=FONT)).get_extents().height
    cs = cs.scale((cap / capref, cap / capref))
    b = cs.bounds()
    return cs.translate((-(b[0] + b[2]) / 2 if center else -b[0], -(b[1] + b[3]) / 2))


LBL = 3.0                                   # Schrifthoehe Bodenbeschriftung (mm)
labels = [("12 V", SD_X + SD_L / 2, SD_POS["SD-15B-12 (12 V)"][1] + SD_W / 2, 6.0),
          ("5 V", SD_X + SD_L / 2, SD_POS["SD-15B-5 (5 V)"][1] + SD_W / 2, 6.0)]
for (n, y, lbl) in wago_slots:       # links neben dem Wago (Einfuehrungsseite)
    labels.append((lbl.replace("GND 2", "GND2"), WAGO_X - 5.6, y + (WAGO_W[n] + WCLR) / 2, LBL))
for (n, y, lbl) in wago_slots2:      # rechts hinter der Rueckwand
    labels.append((lbl, WAGO2_X - 1.6 - LABEL_GAP / 2, y + (WAGO_W[n] + WCLR) / 2, LBL))   # im Gang links
labels += [("ATOM", ATOM_X + aw / 2, ATOM_Y - 5.0, LBL), ("24 V IN", NOTCH_X, 24.0, LBL),
           ("CAT 7", BORE[0], BORE[1] + BORE_OPEN / 2 + 4.6, LBL)]
LABEL_DEPTH = 0.8
label_inlay = Manifold()                    # Schrift als eigenes Teil (zweite Farbe mit AMS)
for (s, x, y, cap) in labels:
    if 1.5 < y < IN_H - 1.5:
        cs = text_cs(s, cap).translate((x, y))
        shell -= cs.extrude(2).translate((0, 0, Z0 - LABEL_DEPTH))
        label_inlay += cs.extrude(LABEL_DEPTH).translate((0, 0, Z0 - LABEL_DEPTH))

# ---------------- Deckel ----------------
LIP, LIP_T = 2.0, 1.4
lid = rrect(IN_W + 2 * WALL, IN_H + 2 * WALL, R_OUT).extrude(LID)
ring = rrect(IN_W - 0.6, IN_H - 0.6, R_OUT - WALL - 0.3) - rrect(IN_W - 0.6 - 2 * LIP_T, IN_H - 0.6 - 2 * LIP_T,
                                                               R_OUT - WALL - 0.3 - LIP_T)
lid += ring.extrude(LIP).translate((0, 0, LID - 0.01))
lid = lid.translate((cx, cy, 0))


def hook(side, pos):
    """Rasthaken in Druck-Koordinaten des Deckels (Deckelplatte z 0..LID, Haken waechst nach oben).
    Profil in (aussen o, z): Haltekante steil (zur Platte hin), Auflaufschraege zur Spitze hin flach."""
    zA, zB = LID + BUMP_TOP, LID + BUMP_BOT
    prof = CrossSection([[(0.0, LID - 0.01), (HOOK_T, LID - 0.01), (HOOK_T, LID + HOOK_L), (0.0, LID + HOOK_L),
                          (0.0, zB), (-BUMP, zA + 1.2), (-BUMP, zA + 0.5), (0.0, zA)]])
    # Profil liegt in (o, z); in x/y-Ebene extrudieren und an die Seite drehen
    m = prof.extrude(HOOK_W).translate((0, 0, -HOOK_W / 2))      # (o, z, w)
    m = m.rotate((90, 0, 0))                                     # -> (o, w, z) mit z nach oben
    if side == "B":        # Aussenseite zeigt nach -y
        m = m.rotate((0, 0, 90)).translate((pos, LIP_IN, 0))
    elif side == "T":
        m = m.rotate((0, 0, -90)).translate((pos, IN_H - LIP_IN, 0))
    elif side == "L":
        m = m.translate((LIP_IN, pos, 0))
    else:
        m = m.rotate((0, 0, 180)).translate((IN_W - LIP_IN, pos, 0))
    return m


for side, pos in HOOKS:
    lid += hook(side, pos)
# Halter fuer Temperaturfuehler DS18B20 (Edelstahlhuelse Oe 6 mm) innen am Deckel, ueber dem Gang zwischen den
# Wago-Spalten (weit weg von den Wandlern). Zwei Klemmen, oben offen (5,0 mm Schlitz) -> Fuehler einklipsen.
# Nackter DS18B20 (TO-92): in Schrumpfschlauch stecken oder mit Kabelbinder durch den Schlitz unter den Klemmen.
TS_X, TS_Y0, TS_Y1 = 138.5, 52.0, 82.0      # Einbaulage: Mitte x, Klemmen bei y
TS_R, TS_SLOT, TS_H = 3.15, 5.0, 8.0
for _ty in (TS_Y0, TS_Y1):
    _px = IN_W - TS_X                         # Deckel liegt gespiegelt
    _c = box(_px - 5.0, _px + 5.0, _ty - 3.0, _ty + 3.0, LID - 0.01, LID + TS_H)
    _c -= Manifold.cylinder(8, TS_R, TS_R, 48).rotate((-90, 0, 0)).translate((_px, _ty - 4, LID + TS_H - TS_R - 0.8))
    _c -= box(_px - TS_SLOT / 2, _px + TS_SLOT / 2, _ty - 4, _ty + 4, LID + TS_H - TS_R - 0.8, LID + TS_H + 1)
    _c -= box(_px - 5.5, _px + 5.5, _ty - 1.6, _ty + 1.6, LID + 0.8, LID + 2.6)   # Kabelbinder-Schlitz (3,2 x 1,8)
    lid += _c
# Lueftungsschlitze ueber den Wandlern (dezent, 2 Reihen)
for row_y in (SD_POS["SD-15B-5 (5 V)"][1] + SD_W / 2, SD_POS["SD-15B-12 (12 V)"][1] + SD_W / 2):
    for i in range(7):
        sx = IN_W - (SD_X + 12 + i * 9.0) - 2.2       # Deckel liegt gespiegelt -> ueber den Wandlern
        lid -= box(sx, sx + 2.2, row_y - 12, row_y + 12, -1, LID + 1)
# ---------------- Logo + "AD.NET solutions / ACCESS" aussen auf dem Deckel (einfarbig, vertieft) ----------------
# Der Deckel liegt beim Druck mit der Aussenseite auf dem Druckbett -> Logo und Schrift 0,6 mm eingraviert
# (erhaben ginge nur mit Stuetzmaterial). Alles mittig untereinander.
DECO_X = 152.0                                       # Mitte in Einbaulage (von aussen gesehen, rechts der Lueftung)
LOGO_H, LOGO_Y = 46.0, 79.0
TXT1, TXT1_CAP = "AD.NET solutions", 6.5
TXT2, TXT2_CAP = "ACCESS", 9.0
ENGRAVE = 0.6


LOGO_RIB = 0.8                                       # Steg zwischen grauen und orangen Flaechen (druckbar)
LOGO_DEEP = 1.0                                      # orange Flaechen tiefer -> heben sich auch einfarbig ab


def logo_cs(height):
    """Logo-PNG in (orange, grau) zerlegen; grau bekommt einen Steg zum Orange, damit N und A getrennt bleiben."""
    import cv2
    from PIL import Image
    a = np.array(Image.open(BASE / "assets" / "adnet_logo.png").convert("RGBA")).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    vis = al > 128
    masks = (vis & (r > 180) & (g < 140) & (r - g > 80), vis & (abs(r - g) < 25) & (abs(g - b) < 25) & (r < 200))
    hpx, wpx = r.shape
    k = height / hpx
    out = []
    for m in masks:
        cs, _ = cv2.findContours(m.astype(np.uint8) * 255, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        polys = []
        for c in cs:
            c = cv2.approxPolyDP(c, 0.6, True)[:, 0, :].astype(float)
            if len(c) > 2:
                polys.append([((x - wpx / 2) * k, (hpx / 2 - y) * k) for x, y in c])
        out.append(CrossSection(polys, fillrule=FillRule.EvenOdd))
    orange, grau = out
    grau = grau - orange.offset(LOGO_RIB, JoinType.Miter)
    return orange, grau


_y1 = LOGO_Y - LOGO_H / 2 - 6.0 - TXT1_CAP / 2
_y2 = _y1 - TXT1_CAP / 2 - 5.0 - TXT2_CAP / 2
_lo, _lg = logo_cs(LOGO_H)
deco = (_lg.translate((DECO_X, LOGO_Y)) + text_cs(TXT1, TXT1_CAP).translate((DECO_X, _y1))
        + text_cs(TXT2, TXT2_CAP).translate((DECO_X, _y2)))
_pr = lambda cs: cs.mirror((1, 0)).translate((IN_W, 0))                                # Deckel liegt gespiegelt
lid -= _pr(deco).extrude(ENGRAVE + 0.01).translate((0, 0, -0.01))
lid -= _pr(_lo.translate((DECO_X, LOGO_Y))).extrude(LOGO_DEEP + 0.01).translate((0, 0, -0.01))

# ---------------- Niederhalter fuer die Wandler (2 x drucken) ----------------
span = (SD_W + 2 * CLR) + 2 * HOLD_OFF
bar = rrect(span + 9.0, 8.0, 3.0).extrude(4.0)
for dy in (-span / 2, span / 2):
    bar -= cyl(dy, 0, 1.7, -1, 5)
    bar -= cyl(dy, 0, 3.1, 4.0 - 2.0, 5)          # Senkung fuer Linsenkopf 2,9 (Kopf 5,6 x 2,4) -> steht nur 0,4 mm ueber
bar = bar.rotate((0, 0, 0))


def save(m, name):
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts)
    tm.export(OUT / name)
    b = tm.bounds
    print(f"{name:32s} {' x '.join(f'{v:.1f}' for v in (b[1] - b[0]))} mm  {'ok' if tm.is_watertight else 'NICHT WASSERDICHT'}")


save(shell, "innen_unterteil.stl")
save(label_inlay, "innen_unterteil_schrift.stl")
save(lid, "innen_deckel.stl")
save(bar, "innen_niederhalter.stl")

# Niederhalter-Platzhalter fuer die Vorschau
for name, (x, y) in SD_POS.items():
    parts_demo.append({"kind": "bar", "w": 8.0, "h": span + 9.0, "d": 4.0, "x": x + (SD_L + 2 * CLR) * SD_BAR_F[name],
                       "y": y + (SD_W + 2 * CLR) / 2, "z": Z0 + SD_H})
(OUT / "innen_layout.json").write_text(json.dumps({
    "in_w": IN_W, "in_h": IN_H, "sd": {k: [x, y, SD_L, SD_W] for k, (x, y) in SD_POS.items()}, "sd_term": SD_TERM,
    "wago1": [[WAGO_X, y, WAGO_D + CLR, WAGO_W[n] + WCLR, l, n] for n, y, l in wago_slots],
    "wago2": [[WAGO2_X, y, WAGO_D + CLR, WAGO_W[n] + WCLR, l, n] for n, y, l in wago_slots2],
    "atom": [ATOM_X, ATOM_Y, aw], "delock": [DL_X, DL_Y, dw, dl], "bore": [BORE[0], BORE[1], BORE_OPEN / 2],
    "jack": [NOTCH_X, JACK_D], "pry": cx}, indent=1), encoding="utf-8")
(OUT / "innen_bestueckung_demo.json").write_text(json.dumps(parts_demo, indent=1), encoding="utf-8")
print(f"Gehaeuse aussen: {IN_W + 2 * WALL:.0f} x {IN_H + 2 * WALL:.0f} x {H_OUT + LID:.0f} mm")
print(f"Wandbohrung: {BORE[0] + WALL:.0f} mm vom linken, {BORE[1] + WALL:.0f} mm vom unteren Aussenrand")

# ---------------- Passungstest: je eine Aufnahme 221-413 und 221-415 (Druck ca. 10 min) ----------------
_tw, _th = 2 * (WAGO_D + CLR) + 18, WAGO_W[5] + WCLR + 8
_test = rrect(_tw, _th, 5.0).extrude(Z0).translate((_tw / 2 - 4, _th / 2 - 4, 0))   # runde Ecken: hebt sich nicht ab
for i, n in enumerate((3, 5)):
    tx = 2 + i * (WAGO_D + CLR + 8)
    _test += frame(tx, 0, WAGO_D + CLR, WAGO_W[n] + WCLR, WALL_H_WAGO, sides="RBT")
    _test += snap_noses(tx, 0, WAGO_D + CLR, WAGO_W[n] + WCLR, Z0 + WALL_H_WAGO, along="x", depth=WNOSE, length=8.0)
save(_test, "test_wago_aufnahme.stl")
