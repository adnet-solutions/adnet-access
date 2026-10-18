# Firmware für den Leser (AtomS3 Lite)

| Datei | Inhalt |
|---|---|
| `haustuer-zutritt.yaml` | ESPHome-Konfiguration: Wiegand (Karte + Tasten), PIN-Sammler, verschlüsselte API, Offline-Modus |
| `adnet_access.h` | PIN-HMAC und Prüfung der Offline-Liste |
| `secrets.example.yaml` | Vorlage für die Secrets |

Geprüft mit ESPHome 2026.9 (`esphome config`).

1. Beide Dateien `haustuer-zutritt.yaml` und `adnet_access.h` in den ESPHome-Ordner von HA kopieren (`/config/esphome/`).
2. Werte aus `secrets.example.yaml` in die ESPHome-`secrets.yaml` übernehmen. Schlüssel erzeugen:
   `openssl rand -base64 32` (API) und `openssl rand -hex 24` (PIN). Beide auch in die Add-on-Optionen eintragen.
3. Erster Flash per USB-C (dabei die 5-V-Ader vom Wandler abklemmen), danach per WLAN.
4. Das Gerät **nicht** zwingend in die ESPHome-Integration von HA aufnehmen; das Add-on verbindet sich selbst. Wird es aufgenommen, sind die Ereignis-Sensoren dort standardmäßig ausgeblendet.

**Bedienung an der Tastatur:** Karte vorhalten. PIN: Ziffern, dann `#`. `*` löscht. Bei *Karte + PIN* erst Karte, dann innerhalb von 15 s PIN + `#`.

**Tastatur auf Wiegand 34 stellen** (bei der UHPPOTE: schwarze und graue Ader verbinden, siehe Hardware-Anleitung). Bei 26 Bit überträgt sie nur einen Teil der Karten-ID.

**D0/D1 vertauscht?** Dann kommen falsche Karten-IDs und keine Tasten an. In der YAML einfach `GPIO1` und `GPIO2` tauschen.
