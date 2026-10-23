"""Belegungsschild als A4-PDF zum Ausdrucken, Ausschneiden, Laminieren und Einkleben (innen in den Deckel).

Freie Flaeche innen am Deckel: ca. 75 x 115 mm. Endmass nach dem Laminieren: 74 x 114 mm.
  Papier ausschneiden (durchgezogene Linie): 66 x 106 mm
  Laminierrand ringsum 4 mm -> Folie danach auf 74 x 114 mm zuschneiden (gestrichelte Linie = Schablone)
Druck mit 100 % (nicht "an Seite anpassen") - Kontrollstrich 50 mm auf der Seite.
"""
from pathlib import Path

from reportlab.lib.colors import black, grey
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent / "belegung_inneneinheit_A4.pdf"
PAPER_W, PAPER_H = 66 * mm, 106 * mm
LAM = 4 * mm                                   # Laminierrand je Seite
FINAL_W, FINAL_H = PAPER_W + 2 * LAM, PAPER_H + 2 * LAM

ADERN = [("gn-ge", "GND / alle Minus"), ("1", "24 V +"), ("2", "24 V −"), ("3", "12 V + Tastatur"),
         ("4", "5 V + Atom"), ("5", "D0"), ("6", "D1"), ("7", "LED"), ("8", "BEEP"), ("9", "Reserve")]
ATOM = [("G1", "D0 (Grove)"), ("G2", "D1 (Grove)"), ("5V + GND", "Grove"), ("G5", "LED (über BAT85)"),
        ("G6", "BEEP (über BAT85)"), ("G7", "Temperatur DS18B20")]


def label(c, x, y):
    """Schild mit linker unterer Ecke des Papiers bei (x, y)."""
    # Schablone Endmass (gestrichelt) und Schnittlinie Papier (durchgezogen)
    c.setStrokeColor(grey)
    c.setDash(2, 2)
    c.setLineWidth(0.4)
    c.roundRect(x - LAM, y - LAM, FINAL_W, FINAL_H, 3 * mm)
    c.setDash()
    c.setStrokeColor(black)
    c.setLineWidth(0.6)
    c.rect(x, y, PAPER_W, PAPER_H)
    # Inhalt
    left, col2 = x + 4 * mm, x + 24 * mm
    ty = y + PAPER_H - 7.5 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, ty, "Belegung Inneneinheit")
    c.setFont("Helvetica", 7)
    c.drawString(left, ty - 3.8 * mm, "AD.NET Access · Adern YSLY-JZ 10 × 0,75 mm²")
    ty -= 10 * mm
    for title, rows in (("Ader", ADERN), ("Atom", ATOM)):
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(grey)
        c.drawString(left, ty, title)
        c.drawString(col2, ty, "Funktion" if title == "Ader" else "Signal")
        c.setFillColor(black)
        c.setLineWidth(0.3)
        c.line(left, ty - 1.5 * mm, x + PAPER_W - 4 * mm, ty - 1.5 * mm)
        ty -= 4.8 * mm
        for a, f in rows:
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(left, ty, a)
            c.setFont("Helvetica", 9.5)
            c.drawString(col2, ty, f)
            ty -= 4.2 * mm
        ty -= 1.6 * mm
    assert ty + 1.6 * mm + 4.2 * mm - 1.5 * mm > y + 2 * mm, "Text passt nicht aufs Schild"


c = canvas.Canvas(str(OUT), pagesize=A4)
c.setTitle("Belegung Inneneinheit – AD.NET Access")
W, H = A4
c.setFont("Helvetica-Bold", 12)
c.drawString(20 * mm, H - 18 * mm, "Belegungsschild Inneneinheit – zum Ausschneiden und Laminieren")
c.setFont("Helvetica", 9)
for i, t in enumerate([
        "1. Mit 100 % drucken (nicht „an Seite anpassen“). Kontrolle: der Strich unten muss genau 50 mm lang sein.",
        "2. Papier an der durchgezogenen Linie ausschneiden (66 × 106 mm).",
        "3. Laminieren, dabei ringsum ca. 4 mm Folie überstehen lassen.",
        "4. Folie auf das Endmaß 74 × 114 mm zuschneiden (gestrichelte Linie als Schablone, Ecken leicht abrunden).",
        "5. Innen in den Deckel kleben: über Atom / rechter Wago-Spalte (von innen gesehen links neben den Fühlerklemmen).",
        "Zwei Exemplare – eins als Reserve."]):
    c.drawString(20 * mm, H - 26 * mm - i * 5 * mm, t)
top = H - 70 * mm
for x in (25 * mm, 25 * mm + FINAL_W + 15 * mm):
    label(c, x + LAM, top - PAPER_H)
# Kontrollstrich 50 mm
yb = 22 * mm
c.setLineWidth(1)
c.line(20 * mm, yb, 70 * mm, yb)
for xx in (20 * mm, 70 * mm):
    c.line(xx, yb - 2 * mm, xx, yb + 2 * mm)
c.setFont("Helvetica", 8)
c.drawString(20 * mm, yb - 6 * mm, "Kontrollstrich: genau 50 mm")
c.showPage()
c.save()
print("geschrieben:", OUT)
