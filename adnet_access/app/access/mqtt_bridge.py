"""MQTT-Entitäten für Home Assistant (Discovery): letzter Zutritt, Tür öffnen, Sperren, Verbindungsstatus."""
from __future__ import annotations

import asyncio
import json
import logging
import os

import aiomqtt
import httpx

from .config import supervisor_token

log = logging.getLogger(__name__)
P = "adnet_access"
DEV = {"identifiers": ["adnet_access"], "name": "Haustür Zutritt", "manufacturer": "AD.NET Solutions",
       "model": "AD.NET Access"}


class MqttBridge:
    def __init__(self, engine, esp) -> None:
        self.engine, self.esp = engine, esp
        self.client: aiomqtt.Client | None = None

    async def _creds(self) -> dict | None:
        token = supervisor_token()
        if not token:
            log.warning("Kein Supervisor-Token – MQTT-Entitäten deaktiviert")
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
                r.raise_for_status()
                return r.json()["data"]
        except Exception as e:  # noqa: BLE001
            log.info("Kein MQTT-Broker verfügbar (%s) – HA-Entitäten deaktiviert", e)
            return None

    async def run(self) -> None:
        creds = await self._creds()
        if not creds:
            return
        while True:
            try:
                async with aiomqtt.Client(creds["host"], int(creds.get("port", 1883)), username=creds.get("username"),
                                          password=creds.get("password"),
                                          will=aiomqtt.Will(f"{P}/status", "offline", retain=True)) as client:
                    self.client = client
                    log.info("MQTT verbunden mit %s, Entitäten werden angelegt", creds["host"])
                    await client.publish(f"{P}/status", "online", retain=True)
                    await self.publish_discovery()
                    await client.subscribe(f"{P}/cmd/#")
                    asyncio.create_task(self._status_loop())
                    async for msg in client.messages:
                        await self._on_cmd(str(msg.topic), msg.payload.decode())
            except aiomqtt.MqttError as e:
                self.client = None
                log.warning("MQTT getrennt (%s), neuer Versuch in 10 s", e)
                await asyncio.sleep(10)

    async def _pub(self, topic: str, payload, retain: bool = True) -> None:
        if self.client:
            await self.client.publish(topic, payload if isinstance(payload, str) else json.dumps(payload), retain=retain)

    def _base(self, uid: str, name: str) -> dict:
        return {"unique_id": f"{P}_{uid}", "object_id": f"{P}_{uid}", "name": name, "device": DEV,
                "availability_topic": f"{P}/status"}

    async def publish_discovery(self) -> None:
        d = "homeassistant"
        await self._pub(f"{d}/sensor/{P}/letzter_zutritt/config", {
            **self._base("letzter_zutritt", "Letzter Zutritt"), "state_topic": f"{P}/letzter",
            "value_template": "{{ value_json.text }}", "json_attributes_topic": f"{P}/letzter", "icon": "mdi:door"})
        await self._pub(f"{d}/button/{P}/tuer_oeffnen/config", {
            **self._base("tuer_oeffnen", "Tür öffnen"), "command_topic": f"{P}/cmd/open", "icon": "mdi:door-open"})
        for key, name, icon in (("vacation_lock", "Urlaubssperre", "mdi:airplane"),
                                ("keypad_locked", "Tastatur gesperrt", "mdi:dialpad")):
            await self._pub(f"{d}/switch/{P}/{key}/config", {
                **self._base(key, name), "command_topic": f"{P}/cmd/{key}", "state_topic": f"{P}/state/{key}",
                "icon": icon})
        await self._pub(f"{d}/binary_sensor/{P}/leser/config", {
            **self._base("leser", "Leser verbunden"), "state_topic": f"{P}/state/leser",
            "device_class": "connectivity", "entity_category": "diagnostic"})
        await self.publish_persons()
        await self.publish_states()

    async def publish_persons(self) -> None:
        for p in self.engine.db.q("SELECT id, name FROM persons"):
            await self._pub(f"homeassistant/switch/{P}/person_{p['id']}/config", {
                **self._base(f"person_{p['id']}_gesperrt", f"{p['name']} gesperrt"),
                "command_topic": f"{P}/cmd/person/{p['id']}", "state_topic": f"{P}/state/person/{p['id']}",
                "icon": "mdi:account-lock"})

    async def remove_person(self, pid: int) -> None:
        await self._pub(f"homeassistant/switch/{P}/person_{pid}/config", "")

    async def publish_states(self) -> None:
        for key in ("vacation_lock", "keypad_locked"):
            await self._pub(f"{P}/state/{key}", "ON" if self.engine.flag(key) else "OFF")
        for p in self.engine.db.q("SELECT id, blocked FROM persons"):
            await self._pub(f"{P}/state/person/{p['id']}", "ON" if p["blocked"] else "OFF")

    async def _status_loop(self) -> None:
        last = None
        while self.client:
            state = "ON" if self.esp and self.esp.connected else "OFF"
            if state != last:
                await self._pub(f"{P}/state/leser", state)
                last = state
            await asyncio.sleep(5)

    async def on_event(self, ev: dict) -> None:
        text = ev["person"] or "Unbekannt"
        text += " ✓" if ev["granted"] else " ✗"
        await self._pub(f"{P}/letzter", {**ev, "text": text})

    async def _on_cmd(self, topic: str, payload: str) -> None:
        parts = topic.split("/")[2:]
        on = payload.upper() in ("ON", "1", "TRUE", "PRESS")
        if parts == ["open"]:
            await self.engine.open_manual("Home Assistant")
        elif parts and parts[0] in ("vacation_lock", "keypad_locked"):
            self.engine.db.set(parts[0], "1" if on else "0")
            await self.engine.rules_changed()
        elif len(parts) == 2 and parts[0] == "person":
            self.engine.db.x("UPDATE persons SET blocked=? WHERE id=?", (1 if on else 0, int(parts[1])))
            await self.engine.rules_changed()
        await self.publish_states()
