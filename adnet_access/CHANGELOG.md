# Änderungen

## 0.1.19
- Logbuch: Einträge älter als X Tage oder alles löschen (samt Bildern, mit Rückfrage); ein Nachweis-Eintrag bleibt stehen

## 0.1.18
- Nachgemeldete Offline-Öffnungen: Push-Nachricht nennt die echte Uhrzeit („um 12:30 (nachgemeldet)“)

## 0.1.17
- Ersatz-Kamerabild in der Benachrichtigung wieder entfernt (verhinderte bei gestörter Kamera die Zustellung)
- Log zeigt, ob eine Benachrichtigung mit oder ohne Bild gesendet wurde

## 0.1.16
- Snapshot in Full HD statt 4K anfordern (schneller, v. a. bei WLAN-Kameras), 15 s Zeit pro Versuch

## 0.1.15
- Kamera-Snapshot: bis zu 3 Versuche (UniFi Protect antwortet über HA gelegentlich mit HTTP 500), genauere Fehlermeldung im Log

## 0.1.14
- Logbuch und Übersicht aktualisieren sich live (alle 3 s, neue Einträge werden kurz hervorgehoben)

## 0.1.13
- Karten werden unabhängig vom Leser erkannt (RFID2-Hex, Wiegand 34, Wiegand 26 werden umgerechnet) – kein Neuanlernen beim Umstieg
- Neue Option `reader_type` für das Format der Offline-Liste

## 0.1.12
- Karten-ID von Hand auch im Hex-Format mit Bindestrich (RFID2-Testleser)

## 0.1.11
- Personenliste: Spalten „Heute“ und „Morgen“ mit den Zeitfenstern, in denen die Person reinkommt (inkl. Feiertag, Sperre, Gültigkeit, Urlaubssperre)

## 0.1.10
- Feiertage aus einer HA-Entität (`holidays_entity`, z. B. `sensor.feiertag_de_by`); `holidays_calendar` gilt jetzt zusätzlich (eigene freie Tage)

## 0.1.9
- Feiertage wahlweise aus einem HA-Kalender (`holidays_calendar`, z. B. Integration „Feiertage“); Anzeige des nächsten Feiertags unter *Einstellungen*

## 0.1.8
- MQTT-Prüfung unter *Einstellungen*: Broker, Erreichbarkeit, TLS, Anmeldung, Senden/Empfangen, Dauerverbindung

## 0.1.7
- Richtige Versionsnummer im Protokoll

## 0.1.6
- Eigener MQTT-Broker einstellbar (`mqtt_host`, `mqtt_user`, `mqtt_password`, optional TLS), wenn kein Mosquitto-Add-on läuft

## 0.1.5
- Behoben: Kamera-Snapshot, Push, Kalender und MQTT-Entitäten gingen nicht (Supervisor-Token wurde unter s6 nicht gefunden)
- Protokoll in Ortszeit, weniger HTTP-Rauschen

## 0.1.4
- Zugriff auf den MQTT-Dienst des Supervisors freigeschaltet (hassio_api)

## 0.1.3
- Shelly-Prüfung unter *Einstellungen*: erreichbar, Gerät/Generation, Anmeldung, Kanal, Ruhezustand und optional echtes Schalten mit Kontrolle, dass das Relais wieder abfällt

## 0.1.2
- Dauer des Shelly-Schaltimpulses einstellbar (`shelly_pulse_seconds`, Standard 1 s)

## 0.1.1
- Shelly und Leser dürfen leer bleiben (Einrichten, bevor die Hardware da ist)

## 0.1.0
- Erste Version: Personen, Karten, PIN, Handy-Webhook, Zeitprofile, Feiertage, Kalender
- Logbuch mit UniFi-Snapshot, Protect-Link, CSV, Aufräumen
- Speicherort für Snapshots wählbar (intern, USB-Stick/SSD, NAS) mit Ausweich-Ordner
- MQTT-Entitäten für Home Assistant, Offline-Liste und Offline-Protokoll für den Leser
