"""Shelly Gen2/Gen3/Gen4: Ausgang für 1 s einschalten (Impuls an den Öffnungseingang des Motorschlosses)."""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class Shelly:
    def __init__(self, host: str, password: str = "", switch_id: int = 0, pulse_seconds: float = 1.0) -> None:
        self.host, self.switch_id = host, switch_id
        self.pulse_seconds = max(0.2, min(float(pulse_seconds), 10.0))
        auth = httpx.DigestAuth("admin", password) if password else None
        self.client = httpx.AsyncClient(auth=auth, timeout=5)

    async def pulse(self, seconds: float | None = None) -> bool:
        """Schaltet ein und lässt den Shelly selbst nach `seconds` wieder ausschalten (toggle_after läuft
        auf dem Shelly, das Relais fällt also auch ab, wenn HA danach abstürzt oder das WLAN weg ist)."""
        seconds = self.pulse_seconds if seconds is None else seconds
        if not self.host:
            log.error("Kein Shelly konfiguriert")
            return False
        try:
            r = await self.client.post(f"http://{self.host}/rpc/Switch.Set",
                                       json={"id": self.switch_id, "on": True, "toggle_after": seconds})
            r.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001
            log.error("Shelly %s nicht erreichbar: %s", self.host, e)
            return False
