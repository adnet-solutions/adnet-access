# Hardware

Außen eine **Wiegand-Tastatur mit Kartenleser**, innen eine flache **Inneneinheit** mit Netzteil-Verteilung und dem **AtomS3 Lite**. Dazwischen **eine Bohrung, ein Cat-7-Kabel**, das auch die Ring-Klingeln versorgt. Der **Shelly** sitzt am Motorschloss parallel zum ekey-Relais; ekey und Schlüssel bleiben unverändert.

## Teileliste

| Teil | Anzahl | Hinweis | Bezug (Beispiele) |
|---|---|---|---|
| **UHPPOTE Wiegand-Tastatur 13,56 MHz**, 12 V, wetterfest (ASIN B01GJDNTP4) | 1 | Karte + PIN, Ausgang Wiegand 26/34 | Amazon |
| **M5Stack AtomS3 Lite** (ESP32-S3) | 1 | Leser-Elektronik innen | M5Stack, Berrybase, Eckstein |
| Grove-Kabel mit offenen Enden (oder Grove-auf-Dupont, Buchse) | 1 | Atom → Wagos | |
| **Mean Well GST60A24-P1J** (24 V / 2,5 A, Steckernetzteil) | 1 | **das eine Netzteil** für Ring + Tastatur + Atom | Reichelt, Conrad, Bürklin, TME (**nicht** Amazon/eBay: Fälschungen) |
| **Mean Well SD-15B-12** (DC/DC 18–36 V → 12 V) | 1 | Tastatur | Conrad (ca. 13 €), Bürklin 62C2001, TME |
| **Mean Well SD-15B-5** (DC/DC 18–36 V → 5 V) | 1 | Atom | wie oben |
| **Delock 65524** DC-Buchse 5,5 × 2,1 mit Klemmen | 1 | Netzteil rein | |
| **WAGO 221-415** | 3 | `24V+`, `24V−`, `GND` | |
| **WAGO 221-413** | 5 | `D0 a/b`, `D1 a/b`, `frei` | |
| Widerstand **10 kΩ**, ¼ W, bedrahtet | 4–8 | Spannungsteiler D0/D1 (nur falls nötig, siehe unten) | |
| **Cat 7 Verlegekabel** (S/FTP, 4 × 2 × AWG23) | Wand + 1 m | das einzige Kabel nach außen | |
| 13,56-MHz-Karten / Schlüsselanhänger (MIFARE) | nach Bedarf | | |
| Shelly Plus/Pro 1 (oder Mini Gen3) mit potentialfreiem Kontakt | 1 | parallel zum ekey-Relais (falls nicht schon vorhanden) | |

## Ein Kabel, eine Bohrung: Belegung Cat 7

| Ader | Signal | außen | innen |
|---|---|---|---|
| orange | Ring + | Ring-Klingeln | Wago `24V+` |
| weiß-orange | Ring − | Ring-Klingeln | Wago `24V−` |
| grün | +12 V | Tastatur rot | SD-15B-12 `+V` |
| weiß-grün | GND | Tastatur schwarz | Wago `GND` |
| blau | D0 | Tastatur D0 (grün) | Wago `D0 a` |
| braun | D1 | Tastatur D1 (weiß) | Wago `D1 a` |
| weiß-blau | LED | Tastatur **blau** (LED, Reserve) | Wago `frei` |
| weiß-braun | BEEP | Tastatur **gelb** (BEEP, Reserve) | Wago `frei` |

Aderfarben laut Anleitung (Modell **HBK-D02K**, so von Amazon für die UHPPOTE-Tastatur bereitgestellt): rot +12 V, schwarz GND, grün D0, weiß D1, blau LED, gelb BEEP, grau Wiegand-34-Auswahl. Liegt eine andere Anleitung bei: immer danach gehen.

**LED und Summer:** Laut Anleitung zeigt die Tastatur Grün bzw. Töne nur, wenn LED und BEEP vom Controller angesteuert werden (Ruhe: LED rot). Ohne Anschluss bleibt sie also stumm – ob auch der Tastenton entfällt, zeigt erst das Gerät. Eine eigene Einstellung für den Summer hat das Modell nicht.

**Wiegand 34 einstellen:** **graue und schwarze Ader verbinden** (Standard ab Werk ist Wiegand 26). Mit 26 Bit überträgt sie nur einen Teil der Karten-ID.

**Masse:** Minus von SD-15B-12, SD-15B-5, Atom und Tastatur liegen gemeinsam auf dem Wago `GND`. Der Ring-Kreis (24 V) bleibt davon getrennt, weil die SD-15B galvanisch trennen. Die Ring-Klingeln brauchen 24 V und hängen direkt am Netzteil.

## Spannungsteiler D0/D1 (ohne Löten)

Der Atom verträgt an G1/G2 **höchstens 3,3 V**. Vorher mit dem Multimeter messen: Tastatur an 12 V, **D0 gegen GND** im Ruhezustand.

| gemessen | Teiler (je Signal) | ergibt |
|---|---|---|
| ≤ 3,3 V | keiner, Ader direkt an den Atom | |
| **≈ 5 V** | 1 × 10 kΩ **oben** (Ader → Atom), 2 × 10 kΩ **unten** (Atom → GND, in Reihe) | 3,3 V |
| **≈ 12 V** | 3 × 10 kΩ **oben** (in Reihe), 1 × 10 kΩ **unten** | 3,0 V |

So geht das in den Wagos: Wago `D0 a` = Ader von außen + oberer Widerstand. Wago `D0 b` = anderes Ende des oberen Widerstands + unterer Widerstand + Grove-Ader zum Atom. Freies Ende des unteren Widerstands in den Wago `GND`. Reihenschaltungen: Widerstandsbeinchen zusammen in einen freien Steckplatz desselben Wago stecken bzw. verdrillen. Für D1 genauso.

## Inneneinheit

![Inneneinheit](inneneinheit/images/inneneinheit.png)

Gehäuse **229 × 137 × 39 mm**, flach, **PETG weiß**. Jedes Teil hat seine Aufnahme, nichts liegt lose:

| Aufnahme | Teil | Befestigung |
|---|---|---|
| links unten | **SD-15B-5** (24 → 5 V, Atom) | Eckwinkel + Niederhalter, 2 Schrauben 2,9 × 13 |
| links oben | **SD-15B-12** (24 → 12 V, Tastatur) | Eckwinkel + Niederhalter, 2 Schrauben 2,9 × 13 |
| Mitte, Spalte 1 | 3 × **WAGO 221-415**: `24V+`, `24V−`, `GND` | eindrücken, Rastnasen |
| Mitte, Spalte 2 | 5 × **WAGO 221-413**: `D0 a/b`, `D1 a/b`, `frei` | eindrücken, Rastnasen |
| rechts oben | **AtomS3 Lite** (USB-C frei zum Flashen) | eindrücken, Rastnasen |
| rechts unten | **Delock 65524** an der Kabelkerbe | eindrücken, Rastnasen |
| rechts | Öffnung **Ø 22 mm** über der Wandbohrung (Cat 7 von hinten) | Kabelbinder-Brücken |

Die Aufnahmen sind im Boden beschriftet.

![Aufnahmen](inneneinheit/images/inneneinheit_leer.png)

**Lage an der Wand:** Wandbohrung **204 mm vom linken** und **44 mm vom unteren Außenrand**. Gehäuse mit 2 Schrauben 4 × 30 + Dübel, Deckel mit 4 Blechschrauben 2,9 × 13.

**Druckteile** ([`inneneinheit/stl/`](inneneinheit/stl/)):

| Datei | Hinweis |
|---|---|
| `innen_unterteil.stl` | Boden aufs Bett, keine Stützen |
| `innen_deckel.stl` | Außenseite unten |
| `innen_niederhalter.stl` | **2 ×** drucken |

Neu erzeugen (Maße oben im Skript, Spiel 0,5 mm): `python3 hardware/inneneinheit/generate_innen.py` (braucht `trimesh`, `shapely`, `manifold3d`, `fonttools`). Vorschau-Bilder: `python3 hardware/inneneinheit/vorschau.py`.

**Vor dem Druck nachmessen:** Wagos (221-413 ca. 17,6 × 18,8 mm, 221-415 ca. 26,6 × 18,8 mm), Delock (27 × 18 × 15 mm), SD-15 (78 × 51 × 28 mm).

## Verdrahtung Schritt für Schritt

1. **24 V:** GST60A24 → Delock-Buchse → Wago `24V+` / `24V−`. Von dort: Ring-Paar (orange/weiß-orange), Eingang SD-15B-12, Eingang SD-15B-5.
2. **12 V:** SD-15B-12 `+V` → grüne Ader (Tastatur +12 V). `−V` → Wago `GND`.
3. **5 V:** SD-15B-5 `+V` → rote Grove-Ader (Atom 5 V). `−V` → Wago `GND`.
4. **GND-Wago:** Minus beider Wandler, schwarze Grove-Ader, weiß-grüne Ader (Tastatur GND), untere Widerstände.
5. **D0/D1:** blau → `D0`, braun → `D1`, ggf. über die Teiler, dann an **G1 (D0)** und **G2 (D1)** des Atom.
6. Netzteilkabel durch die Kerbe, mit Kabelbinder sichern.

**Vor dem Einschalten:** An den Wandler-Ausgängen 12 V bzw. 5 V messen, erst dann Tastatur und Atom anklemmen. **Beim Flashen per USB-C die 5-V-Ader vom Wandler abklemmen.**

## Shelly

Der Shelly-Kontakt (O/I bzw. potentialfrei) kommt **parallel zum Kontakt des ekey-Relais** am Motorschloss-Eingang. Er schaltet einen 1-s-Impuls (`Switch.Set` mit `toggle_after`). Shelly mit Passwort, Zugriff per Firewall nur von HA und dem Atom (siehe [`../adnet_access/DOCS.md`](../adnet_access/DOCS.md)).
