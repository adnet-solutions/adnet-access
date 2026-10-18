# AD.NET Access – Anleitung

Das Add-on ist die Zentrale: Es kennt Personen, Karten, PINs und Zeitfenster, entscheidet bei jedem Vorhalten bzw. jeder PIN, schaltet den Shelly, schreibt das Logbuch und holt den Snapshot von der UniFi-Kamera. Bedient wird es über **„Zutritt“** in der HA-Seitenleiste (nur Administratoren).

## 1. Installieren

Das Repository ist privat, deshalb kann der Add-on-Store es nicht selbst abholen. Zwei Wege:

**a) Lokales Add-on (empfohlen, solange das Repo privat ist)**
1. In HA das Add-on **Samba share** oder **Studio Code Server** installieren.
2. Den Ordner `adnet_access/` aus diesem Repository nach **`/addons/adnet_access/`** kopieren.
3. *Einstellungen → Add-ons → Add-on-Store* → oben rechts ⋮ → **Nach Updates suchen**. Unter *Lokale Add-ons* erscheint „AD.NET Access“ → Installieren. Der erste Bau dauert einige Minuten.
4. Update: Ordner neu kopieren, Version in `config.yaml` erhöhen, *Nach Updates suchen* → Aktualisieren.

**b) Als Add-on-Repository (wenn das Repo öffentlich ist)**
*Add-on-Store* → ⋮ → *Repositories* → `https://github.com/adnet-solutions/adnet-access` hinzufügen.

Voraussetzungen: **MQTT** für die HA-Entitäten, optional. Mit dem Mosquitto-Add-on geht das automatisch. Läuft der Broker woanders (NAS, eigener Server), `mqtt_host`, `mqtt_user` und `mqtt_password` eintragen – am besten einen eigenen Benutzer für das Add-on anlegen. Ohne MQTT läuft alles, nur ohne Schalter in HA.

## 2. Einrichten (Reiter *Konfiguration*)

| Option | Bedeutung |
|---|---|
| `esphome_host` | Name/IP des Lesers, z. B. `haustuer-zutritt.local` |
| `esphome_key` | `adnet_api_key` aus den ESPHome-Secrets. Damit ist die Verbindung **verschlüsselt** (Noise). |
| `pin_key` | `adnet_pin_key` aus den ESPHome-Secrets. Muss gleich sein, sonst passt keine PIN. |
| `shelly_host`, `shelly_password`, `shelly_switch_id` | Shelly am Motorschloss (Gen2/Gen3/Gen4, Benutzer `admin`) |
| `shelly_pulse_seconds` | Wie lange das Relais schließt. Motorschloss mit Impuls-Eingang: **1 s**, elektrischer Türöffner (Summer): **3–5 s**. Das Abschalten macht der Shelly selbst. Für den Offline-Modus denselben Wert als `impuls_s` in `esphome/haustuer-zutritt.yaml` setzen. |
| `camera_entity` | z. B. `camera.eingang_high` aus der UniFi-Protect-Integration |
| `snapshot_crop` | optional Ausschnitt `x,y,breite,höhe` in Prozent, z. B. `30,10,40,80` |
| `snapshot_dir` | **Speicherort der Bilder**, siehe Abschnitt 5 |
| `snapshot_days`, `log_months` | Aufbewahrung, danach automatisch gelöscht |
| `notify_service` | z. B. `notify.mobile_app_enricos_iphone` |
| `calendar_entity` | optional, z. B. `calendar.zutritt` |
| `protect_link_template` | optional Link in die Protect-Zeitleiste, `{ts_ms}` wird durch die Zeit ersetzt |
| `holidays_subdiv` | Bundesland für Feiertage (BY, BW, …) |
| `card_pin_timeout` | Sekunden für die PIN nach der Karte (Modus Karte + PIN) |
| `lockout_attempts`, `lockout_seconds` | Sperre nach Fehlversuchen, die Dauer verdoppelt sich bei Wiederholung |

**Shelly prüfen:** In der Seitenleiste unter *Zutritt → Einstellungen → Shelly prüfen*. Getestet werden Erreichbarkeit, Gerät (Gen2 oder neuer), Anmeldung, Kanal und Ruhezustand. „Prüfen und schalten“ schaltet zusätzlich wirklich (Tür geht auf) und kontrolliert, dass das Relais nach der Impulsdauer wieder abfällt.

**Shelly absichern:** Im Offline-Fall schaltet der Leser den Shelly direkt per HTTP **ohne Passwort** (ESPHome kann keine Digest-Anmeldung). Deshalb: Shelly-Passwort setzen, aber im Router/Firewall dafür sorgen, dass nur **HA und der Leser** den Shelly erreichen (eigenes IoT-VLAN, Regel nur von diesen zwei IPs). Wer den Offline-Modus nicht will: im ESPHome-Secret `adnet_shelly_host` auf `0.0.0.0` setzen.

## 3. Bedienung

**Personen:** Name, gültig von/bis (einschließlich), Modus, PIN, Zeitprofile, Sperre, Benachrichtigung, Handy.
- *Nur PIN* verlangt mindestens 6 Ziffern, sonst 4–8. Jede PIN darf nur einmal vergeben sein.
- **Karte anlernen:** Knopf drücken, innerhalb von 60 s Karte an die Tastatur halten. Mehrere Karten pro Person, jede einzeln sperrbar.
- **Gesperrt bis:** z. B. bis Montag 8 Uhr, danach automatisch wieder frei.
- **Jederzeit / auch bei Urlaubssperre:** für die Familie.

**Zeitprofile:** Wochentage + von/bis, mehrere Zeilen pro Profil. „An Feiertagen kein Zutritt“ nimmt die Feiertage des Bundeslands aus.

**Termine über den Kalender:** Ein Termin im HA-Kalender mit dem Titel **`Zutritt: Name`** oder **`Zutritt: Name1, Name2`** erlaubt diesen Personen für die Dauer des Termins Zutritt, auch außerhalb ihrer Zeitprofile (z. B. Handwerker am Donnerstag 13–16 Uhr). Der Name muss genau so geschrieben sein wie in der Personenliste. Gültigkeit und Sperren gelten trotzdem.

**Handy:** Bei der Person „Darf per Handy öffnen“ einschalten. Es entsteht ein geheimer Link `http://<HA>:8098/handy/<token>`. Den als Kurzbefehl (iPhone: *Kurzbefehle → URL abrufen*) oder mit *HTTP Shortcuts* (Android) auf den Homescreen legen. Nur im WLAN oder über VPN, **Port 8098 nicht ins Internet freigeben**. Link verloren → *Neuen Link erzeugen*.

**Logbuch:** jeder Versuch mit Ergebnis und Grund (z. B. „außerhalb der Zeitfenster“, „Karte gesperrt“). PINs werden nie gespeichert, nur die Karten-ID. Filter nach Person, Ergebnis, Zeitraum; CSV-Export.

## 4. In Home Assistant (über MQTT)

Gerät **„Haustür Zutritt“** mit: *Letzter Zutritt* (Sensor mit Person, Weg, Bildpfad als Attribute), *Tür öffnen* (Knopf), *Urlaubssperre*, *Tastatur gesperrt*, *Leser verbunden* und je Person *„<Name> gesperrt“*.

Beispiel: Urlaubssperre automatisch mit der Alarmanlage:
```yaml
automation:
  - alias: Urlaubssperre mit Alarm
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.haus
    actions:
      - action: "switch.turn_{{ 'on' if trigger.to_state.state == 'armed_away' else 'off' }}"
        target:
          entity_id: switch.adnet_access_vacation_lock
```
Hinweis: Wer Zugriff auf den MQTT-Broker hat, kann über *Tür öffnen* die Tür öffnen. Den Broker also nur mit Benutzer/Passwort betreiben (Standard beim Mosquitto-Add-on).

## 5. Wo die Bilder liegen (intern, USB-Stick, NAS)

Die Snapshots holt das Add-on über HA von der UniFi-Kamera; der Leser an der Tür hat damit nichts zu tun. Gespeichert wird unter **`/media`** von Home Assistant:

| Ort | Einrichtung | `snapshot_dir` |
|---|---|---|
| intern (Standard) | nichts | `/media/adnet_access` |
| **NAS** (offiziell unterstützt) | *Einstellungen → System → Speicher → Netzwerkspeicher hinzufügen*, Verwendung **Medien**, Name z. B. `nas_zutritt` (SMB oder NFS) | `/media/nas_zutritt` |
| **USB-SSD als Datenlaufwerk** (offiziell unterstützt) | *Einstellungen → System → Speicher → Datenlaufwerk verschieben*. Dann liegt **ganz HA** samt `/media` auf der SSD, nicht nur die Bilder. Schont die SD-Karte. | `/media/adnet_access` (bleibt) |
| **USB-Stick nur für die Bilder** | Von HA OS **nicht offiziell unterstützt**. Geht nur per udev-Regel (Import über einen `CONFIG`-Stick) oder mit dem Community-Add-on *Samba NAS* mit Automount (dafür muss der Schutzmodus aus). Der Stick erscheint dann unter `/media/<Name>`. | z. B. `/media/usbstick/zutritt` |

Ist der gewählte Ort nicht erreichbar (Stick abgezogen, NAS aus), speichert das Add-on **vorübergehend in `/media/adnet_access`**, schreibt eine Warnung ins Protokoll und zeigt das unter *Einstellungen* an. Es legt den Stick-Ordner nie selbst an, damit nicht unbemerkt auf die interne Platte geschrieben wird. Das Aufräumen nach `snapshot_days` läuft an beiden Orten.

Empfehlung: NAS, oder – falls HA noch von einer SD-Karte läuft – gleich die USB-SSD als Datenlaufwerk. Mengen: ein Bild ca. 100–300 kB, bei 10 Öffnungen am Tag und 30 Tagen Aufbewahrung also unter 100 MB.

Unabhängig davon zeichnet die UniFi-Kamera selbst weiter in Protect auf; der Protect-Link im Logbuch springt an die passende Stelle.

## 6. Wenn HA ausfällt

Der Leser bekommt bei jeder Änderung (und alle 5 Minuten) eine **Offline-Liste**: Karten/PIN-Hashes mit Wochen-Zeitfenstern in vollen Stunden und Gültig-bis. Hört er 90 s nichts vom Add-on, entscheidet er selbst und schaltet den Shelly. Offline nicht berücksichtigt: Feiertage, Kalender, halbe Stunden. Gesperrte Personen und die Urlaubssperre sind gar nicht erst in der Liste. Die Offline-Entscheidungen übernimmt das Add-on beim nächsten Verbinden ins Logbuch (ohne Snapshot). Platz ist für ca. 30 Einträge.

Fingerprint (ekey) und Schlüssel gehen immer, unabhängig von allem hier.

## 7. Sicherheit

- Leser ↔ Add-on: ESPHome-API mit **Noise-Verschlüsselung**; PINs verlassen die Tastatur nur als HMAC.
- Weboberfläche nur über HA-Ingress (HA-Login, nur Admins). Direkte Zugriffe auf Port 8099 werden abgewiesen.
- Karten-IDs (13,56 MHz, UID) lassen sich kopieren. Für Bereiche mit hohem Schutzbedarf **Karte + PIN** verwenden.
- Nach Fehlversuchen sperrt die Tastatur kurz und schickt eine Warnung.
