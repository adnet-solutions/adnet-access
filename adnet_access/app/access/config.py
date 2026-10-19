"""Add-on-Optionen aus /data/options.json (lokal: Umgebungsvariable ADNET_OPTIONS)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class Options:
    esphome_host: str = "haustuer-zutritt.local"
    esphome_key: str = ""
    reader_type: str = "wiegand34"   # wiegand34 | wiegand26 | rfid2 – Format der Offline-Liste
    pin_key: str = ""
    shelly_host: str = ""
    shelly_password: str = ""
    shelly_switch_id: int = 0
    shelly_pulse_seconds: float = 1.0
    mqtt_host: str = ""          # leer = Mosquitto-Add-on automatisch
    mqtt_port: int = 0           # 0 = 1883 bzw. 8883 mit TLS
    mqtt_user: str = ""
    mqtt_password: str = ""
    mqtt_tls: bool = False
    mqtt_tls_insecure: bool = False
    camera_entity: str = ""
    notify_service: str = ""
    calendar_entity: str = ""
    protect_link_template: str = ""
    snapshot_crop: str = ""
    snapshot_dir: str = "/media/adnet_access"   # z. B. USB-Stick /media/usbstick/zutritt oder NAS
    snapshot_days: int = 30
    log_months: int = 12
    holidays_subdiv: str = "BY"
    holidays_entity: str = ""        # Grundlage aus HA, z. B. sensor.feiertag_de_by (sonst eingebaute Liste)
    holidays_calendar: str = ""      # zusätzliche freie Tage aus einem eigenen HA-Kalender
    timezone: str = "Europe/Berlin"
    card_pin_timeout: int = 15
    lockout_attempts: int = 3
    lockout_seconds: int = 60
    # nicht in config.yaml: nur für Entwicklung
    data_dir: str = "/data"
    media_dir: str = "/media/adnet_access"
    dev: bool = False


def supervisor_token() -> str:
    """Token für die Supervisor-/HA-API. Unter s6-overlay steht er nicht immer in der Umgebung des
    Hauptprozesses, dann liegt er in /run/s6/container_environment."""
    for name in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
        f = Path("/run/s6/container_environment") / name
        try:
            if f.is_file():
                return f.read_text().strip()
        except OSError:
            pass
    return ""


def load() -> Options:
    path = Path(os.environ.get("ADNET_OPTIONS", "/data/options.json"))
    raw = json.loads(path.read_text()) if path.exists() else {}
    known = {f.name for f in fields(Options)}
    return Options(**{k: v for k, v in raw.items() if k in known})
