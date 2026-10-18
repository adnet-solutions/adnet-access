"""Verbindung zum Atom über die verschlüsselte ESPHome-API (Noise).

Atom -> Add-on: Text-Sensor "Ereignis" mit JSON {"n": Zähler, "t": "karte"|"pin", "v": Karten-ID bzw. PIN-HMAC}
                Text-Sensor "Offline-Protokoll": Zeilen "<unixzeit>|<weg>:<wert>[:<pinhash>]:<ergebnis>"
                (Entscheidungen, die der Atom ohne Add-on selbst getroffen hat)
Add-on -> Atom: Aktionen 'heartbeat', 'liste_setzen(daten)', 'rueckmeldung(ok)', 'offline_protokoll_loeschen'
"""
from __future__ import annotations

import asyncio
import json
import logging

from aioesphomeapi import APIClient, ReconnectLogic, TextSensorInfo, TextSensorState

log = logging.getLogger(__name__)
EVENT_ID = "ereignis"
OFFLINE_ID = "offline_protokoll"
MAX_LIST = 1800


class EspLink:
    def __init__(self, host: str, key: str, engine) -> None:
        self.host, self.engine = host, engine
        self.client = APIClient(host, 6053, None, client_info="adnet-access", noise_psk=key or None)
        self.connected = False
        self._event_key: int | None = None
        self._offline_key: int | None = None
        self._services: dict[str, object] = {}
        self._last_seq: int | None = None
        self._first_state = True
        self._last_list = None

    async def start(self) -> None:
        name = None if self.host.replace(".", "").isdigit() else self.host.removesuffix(".local")
        self._reconnect = ReconnectLogic(client=self.client, on_connect=self._on_connect,
                                         on_disconnect=self._on_disconnect, on_connect_error=self._on_error,
                                         name=name)
        await self._reconnect.start()
        asyncio.create_task(self._heartbeat_loop())

    async def _on_connect(self) -> None:
        entities, services = await self.client.list_entities_services()
        self._services = {s.name: s for s in services}
        def find(oid: str) -> int | None:
            for e in entities:
                if isinstance(e, TextSensorInfo) and oid in (e.object_id, e.name.lower().replace(" ", "_").replace("-", "_")):
                    return e.key
            return None
        self._event_key, self._offline_key = find(EVENT_ID), find(OFFLINE_ID)
        if self._event_key is None:
            log.error("Text-Sensor 'Ereignis' nicht gefunden – ESPHome-Konfiguration prüfen")
        self._first_state = True
        self.client.subscribe_states(self._on_state)
        self.connected = True
        self._last_list = None
        log.info("Verbunden mit %s (Aktionen: %s)", self.host, ", ".join(self._services))
        await self.push_list()

    async def _on_error(self, err: Exception) -> None:
        log.warning("Leser %s nicht erreichbar: %s", self.host, err)

    async def _on_disconnect(self, expected: bool) -> None:
        self.connected = False
        log.warning("Verbindung zu %s getrennt", self.host)

    def _on_state(self, state) -> None:
        if not isinstance(state, TextSensorState) or state.missing_state:
            return
        if state.key == self._offline_key and state.state.strip():
            asyncio.create_task(self._import_offline(state.state))
            return
        if state.key != self._event_key:
            return
        try:
            ev = json.loads(state.state)
        except (ValueError, TypeError):
            return
        seq = ev.get("n")
        first, self._first_state = self._first_state, False
        if first or seq == self._last_seq:      # Zustand beim Verbinden ist ein altes Ereignis
            self._last_seq = seq
            return
        self._last_seq = seq
        typ, val = ev.get("t"), str(ev.get("v", ""))
        if typ == "karte":
            asyncio.create_task(self.engine.handle_card(val))
        elif typ == "pin":
            asyncio.create_task(self.engine.handle_pin(val))

    async def _import_offline(self, text: str) -> None:
        """Offline-Entscheidungen des Atom ins Logbuch übernehmen, danach dort löschen."""
        n = 0
        for line in text.strip().splitlines():
            ts, _, rest = line.partition("|")
            parts = rest.split(":")
            if len(parts) < 3:
                continue
            method, result = parts[0], parts[-1]
            card = parts[1] if method.startswith("karte") else ""
            pin = parts[-2] if method in ("pin", "karte+pin") else ""
            try:
                when = int(ts)
            except ValueError:
                when = 0
            await self.engine.handle_offline(method, card, pin, result, when)
            n += 1
        log.info("%d Offline-Ereignisse vom Leser übernommen", n)
        await self._call("offline_protokoll_loeschen")

    async def _call(self, name: str, data: dict | None = None) -> None:
        svc = self._services.get(name)
        if not (self.connected and svc):
            return
        try:
            await self.client.execute_service(svc, data or {})
        except Exception as e:  # noqa: BLE001
            log.warning("Aktion %s fehlgeschlagen: %s", name, e)

    async def push_list(self) -> None:
        data = self.engine.offline_list()
        if data == self._last_list:
            return
        if len(data) > MAX_LIST:
            log.warning("Offline-Liste zu lang (%d Zeichen) – wird gekürzt", len(data))
            data = data[:MAX_LIST].rsplit(";", 1)[0]
        await self._call("liste_setzen", {"daten": data})
        self._last_list = data

    async def feedback(self, ok: bool) -> None:
        await self._call("rueckmeldung", {"ok": ok})

    async def _heartbeat_loop(self) -> None:
        n = 0
        while True:
            await asyncio.sleep(30)
            await self._call("heartbeat")
            n += 1
            if n % 10 == 0:          # alle 5 Minuten Liste abgleichen (Zeitfenster/Gültigkeit ändern sich)
                await self.push_list()
