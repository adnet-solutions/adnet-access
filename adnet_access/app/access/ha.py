"""Home-Assistant-API über den Supervisor: Kamera-Snapshot, Benachrichtigung, Kalender."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import httpx

from .config import supervisor_token

log = logging.getLogger(__name__)


class HA:
    def __init__(self) -> None:
        token = supervisor_token()
        self.enabled = bool(token)
        if not token:
            log.warning("Kein Supervisor-Token – Kamera, Benachrichtigung und Kalender sind aus")
        self.client = httpx.AsyncClient(base_url="http://supervisor/core/api",
                                        headers={"Authorization": f"Bearer {token}"}, timeout=10)

    async def camera_snapshot(self, entity: str) -> bytes | None:
        if not (self.enabled and entity):
            return None
        try:
            r = await self.client.get(f"/camera_proxy/{entity}")
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            log.warning("Snapshot von %s fehlgeschlagen: %s", entity, e)
            return None

    async def notify(self, service: str, title: str, message: str, image: str = "") -> None:
        """service z. B. 'notify.mobile_app_enrico'; image = '/media/local/...'"""
        if not (self.enabled and service):
            return
        domain, _, name = service.partition(".")
        data = {"title": title, "message": message}
        if image:
            data["data"] = {"image": image}
        try:
            r = await self.client.post(f"/services/{domain}/{name}", json=data)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("Benachrichtigung über %s fehlgeschlagen: %s", service, e)

    async def calendar_names_now(self, entity: str, now: datetime) -> set[str]:
        """Namen aus laufenden Terminen. Erkannt wird 'Zutritt: Name' oder 'Zutritt: Name1, Name2'."""
        if not (self.enabled and entity):
            return set()
        start = (now - timedelta(hours=12)).isoformat()
        end = (now + timedelta(hours=12)).isoformat()
        try:
            r = await self.client.get(f"/calendars/{entity}", params={"start": start, "end": end})
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("Kalender %s nicht lesbar: %s", entity, e)
            return set()
        names: set[str] = set()
        for ev in r.json():
            s, e_ = ev.get("start", {}), ev.get("end", {})
            st = s.get("dateTime") or s.get("date")
            en = e_.get("dateTime") or e_.get("date")
            try:
                st_dt = datetime.fromisoformat(st).replace(tzinfo=None)
                en_dt = datetime.fromisoformat(en).replace(tzinfo=None)
            except (TypeError, ValueError):
                continue
            if not (st_dt <= now.replace(tzinfo=None) < en_dt):
                continue
            summary = (ev.get("summary") or "").strip()
            if summary.lower().startswith("zutritt:"):
                for n in summary.split(":", 1)[1].split(","):
                    if n.strip():
                        names.add(n.strip().lower())
        return names
