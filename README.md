# AD.NET Access

Zutrittskontrolle für die Haustür mit Home Assistant: **Karte, PIN oder Handy**, mit Personenverwaltung, Zeitfenstern, Logbuch mit Kamera-Snapshot und Push-Nachricht. Das **ekey bionyx** und der **Schlüssel** bleiben, wie sie sind. Der Shelly schaltet parallel zum ekey-Relais.

```
 Tastatur außen (Wiegand)  ──Cat 7──►  Inneneinheit: AtomS3 Lite (ESPHome)
                                              │  ESPHome-API, Noise-verschlüsselt
                                              ▼
                                   Home Assistant OS: Add-on „AD.NET Access“
                                   Personen · Zeitprofile · Logbuch · Snapshots
                                              │  HTTP (Digest-Login)
                                              ▼
                                   Shelly parallel zum ekey-Relais → Motorschloss
```

| Ordner | Inhalt |
|---|---|
| [`adnet_access/`](adnet_access/) | Home-Assistant-Add-on (Weboberfläche in der HA-Seitenleiste). Anleitung: [`adnet_access/DOCS.md`](adnet_access/DOCS.md) |
| [`esphome/`](esphome/) | Firmware für den AtomS3 Lite an der Tastatur |
| [`hardware/`](hardware/) | Teileliste, Verdrahtung, Inneneinheit zum Drucken (STL + Generator) |
| [`archiv/`](archiv/) | alter Entwurf mit RFID2-Sockel unter der Ring-Platte (nicht mehr verfolgt) |

## Funktionen

- **Personen** mit Gültigkeit von/bis, mehreren Karten, PIN, Handy-Link, Sperre (dauerhaft oder bis Zeitpunkt)
- **Pro Person einstellbar:** nur Karte, nur PIN, Karte + PIN, Karte oder PIN
- **Zeitprofile** (Wochentage + Uhrzeiten, mehrere Fenster), Feiertage nach Bundesland, einmalige Termine über einen HA-Kalender
- **Urlaubssperre** und **Tastatursperre** per Knopf oder Automation, Sperre nach Fehlversuchen
- **Logbuch** (wer, wann, womit, warum abgelehnt) mit **Snapshot der UniFi-Kamera** und Link in die Protect-Zeitleiste, CSV-Export, automatisches Aufräumen
- **Snapshots** wahlweise auf der HA-Platte (auch als USB-SSD-Datenlaufwerk) oder dem **NAS**, mit Ausweich-Ordner, falls der Speicher fehlt
- **Push** bei ausgewählten Personen und bei Warnungen
- **Offline-Modus:** Läuft HA nicht, entscheidet der Leser selbst nach der zuletzt übertragenen Liste und meldet das später nach

## Installation (Kurzfassung)

1. Hardware aufbauen: [`hardware/README.md`](hardware/README.md)
2. Firmware flashen: [`esphome/`](esphome/) (Secrets aus `secrets.example.yaml`)
3. Add-on installieren und einrichten: [`adnet_access/DOCS.md`](adnet_access/DOCS.md)

## Entwicklung

```bash
cd adnet_access
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests
# lokal starten (ohne HA): Optionen als JSON, "dev": true erlaubt Zugriff ohne Ingress
echo '{"pin_key":"test","dev":true,"esphome_host":"","data_dir":"/tmp/aa","media_dir":"/tmp/aa/media","snapshot_dir":"/tmp/aa/media"}' > /tmp/aa.json
cd app && ADNET_OPTIONS=/tmp/aa.json ../.venv/bin/python -m access.main   # http://localhost:8099
```
