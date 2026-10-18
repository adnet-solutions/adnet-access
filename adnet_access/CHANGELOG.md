# Änderungen

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
