"""Home-Assistant-API über den Supervisor: Kamera-Snapshot, Benachrichtigung, Kalender."""
from __future__ import annotations

import asyncio

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
        # UniFi Protect liefert ueber HA gelegentlich HTTP 500 oder antwortet langsam -> bis zu 3 Versuche
        last = ""
        for attempt in range(3):
            try:
                r = await self.client.get(f"/camera_proxy/{entity}", timeout=8)
                if r.status_code == 200 and r.content:
                    if attempt:
                        log.info("Snapshot von %s im %d. Versuch", entity, attempt + 1)
                    return r.content
                last = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__} {e}".strip()
            await asyncio.sleep(1.0 + attempt)
        log.warning("Snapshot von %s fehlgeschlagen (3 Versuche): %s", entity, last)
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

    async def get_state(self, entity: str, quiet: bool = False) -> dict | None:
        if not (self.enabled and entity):
            return None
        try:
            r = await self.client.get(f"/states/{entity}")
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if not quiet:
                log.warning("Entität %s nicht lesbar: %s", entity, e)
            return None

    async def calendar_dates(self, entity: str, start: datetime, end: datetime) -> tuple[set, dict] | None:
        """Alle Tage mit Termin im Kalender (z. B. Feiertagskalender). None = Kalender nicht lesbar."""
        if not (self.enabled and entity):
            return None
        try:
            r = await self.client.get(f"/calendars/{entity}",
                                      params={"start": start.isoformat(), "end": end.isoformat()})
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("Feiertagskalender %s nicht lesbar: %s", entity, e)
            return None
        days: set = set()
        names: dict = {}
        for ev in r.json():
            s, e_ = ev.get("start", {}), ev.get("end", {})
            try:
                if s.get("date"):                                   # ganztägig, Ende exklusiv
                    d0, d1 = datetime.fromisoformat(s["date"]).date(), datetime.fromisoformat(e_["date"]).date()
                else:
                    d0 = datetime.fromisoformat(s["dateTime"]).date()
                    d1 = datetime.fromisoformat(e_["dateTime"]).date() + timedelta(days=1)
            except (KeyError, TypeError, ValueError):
                continue
            d = d0
            while d < max(d1, d0 + timedelta(days=1)):
                days.add(d)
                names[d] = ev.get("summary") or ""
                d += timedelta(days=1)
        return days, names

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
