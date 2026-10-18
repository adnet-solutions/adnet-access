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
        self.last_error = ""
        self.source = ""            # "Konfiguration" oder "Mosquitto-Add-on"

    async def _creds(self) -> dict | None:
        o = self.engine.opts
        if o.mqtt_host:                       # eigener Broker (nicht das Mosquitto-Add-on)
            self.source = "Konfiguration"
            return {"host": o.mqtt_host, "port": o.mqtt_port or (8883 if o.mqtt_tls else 1883),
                    "username": o.mqtt_user or None, "password": o.mqtt_password or None, "ssl": o.mqtt_tls}
        token = supervisor_token()
        if not token:
            log.warning("Kein Supervisor-Token – MQTT-Entitäten deaktiviert")
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"})
                r.raise_for_status()
                self.source = "Mosquitto-Add-on"
                return r.json()["data"]
        except Exception as e:  # noqa: BLE001
            log.warning("Kein Mosquitto-Add-on gefunden (%s). Für einen eigenen Broker mqtt_host/mqtt_user/"
                        "mqtt_password in der Konfiguration setzen – bis dahin keine HA-Entitäten", e)
            return None

    async def run(self) -> None:
        creds = await self._creds()
        if not creds:
            return
        tls = self._tls(creds)
        while True:
            try:
                async with aiomqtt.Client(creds["host"], int(creds.get("port", 1883)), username=creds.get("username"),
                                          password=creds.get("password"), tls_context=tls,
                                          will=aiomqtt.Will(f"{P}/status", "offline", retain=True)) as client:
                    self.client = client
                    self.last_error = ""
                    log.info("MQTT verbunden mit %s, Entitäten werden angelegt", creds["host"])
                    await client.publish(f"{P}/status", "online", retain=True)
                    await self.publish_discovery()
                    await client.subscribe(f"{P}/cmd/#")
                    asyncio.create_task(self._status_loop())
                    async for msg in client.messages:
                        await self._on_cmd(str(msg.topic), msg.payload.decode())
            except (aiomqtt.MqttError, OSError) as e:
                self.client = None
                self.last_error = str(e)
                log.warning("MQTT getrennt (%s), neuer Versuch in 10 s", e)
                await asyncio.sleep(10)

    def _tls(self, creds: dict):
        if not creds.get("ssl"):
            return None
        import ssl
        tls = ssl.create_default_context()
        if self.engine.opts.mqtt_tls_insecure:      # selbstsigniertes Zertifikat am Broker
            tls.check_hostname = False
            tls.verify_mode = ssl.CERT_NONE
        return tls

    async def diagnose(self) -> list:
        """Prüft Schritt für Schritt: Zugangsdaten, Netz, TLS, Anmeldung, Senden/Empfangen, Status der Brücke."""
        from .shelly import Step
        steps: list[Step] = []
        creds = await self._creds()
        if not creds:
            return [Step("Broker", False, "Kein Broker: weder mqtt_host gesetzt noch Mosquitto-Add-on vorhanden")]
        host, port = creds["host"], int(creds.get("port") or 1883)
        steps.append(Step("Broker", True, f"{host}:{port} (aus {self.source}"
                                          f"{', TLS' if creds.get('ssl') else ', unverschlüsselt'})"))
        # 1. Netz
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection(host, port), 4)
            w.close()
            steps.append(Step("Erreichbar", True, f"Port {port} ist offen"))
        except asyncio.TimeoutError:
            steps.append(Step("Erreichbar", False, f"{host}:{port} antwortet nicht – IP, Port oder Firewall prüfen"))
            return steps
        except OSError as e:
            steps.append(Step("Erreichbar", False, f"{host}:{port}: {e.strerror or e} – läuft der Broker, stimmt der Port?"))
            return steps
        if not creds.get("ssl"):
            steps.append(Step("Verschlüsselung", None, "ohne TLS – im Heimnetz üblich; Broker mit TLS: mqtt_tls einschalten"))
        if not creds.get("username"):
            steps.append(Step("Benutzer", None, "kein Benutzer gesetzt – nur ok, wenn der Broker anonyme Zugriffe erlaubt"))
        # 2. Anmeldung + Senden/Empfangen
        topic = f"{P}/test/{os.getpid()}-{int(asyncio.get_running_loop().time() * 1000)}"
        try:
            async with aiomqtt.Client(host, port, username=creds.get("username"), password=creds.get("password"),
                                      tls_context=self._tls(creds), timeout=6,
                                      identifier=f"adnet-access-test-{os.getpid()}") as c:
                if creds.get("ssl"):
                    steps.append(Step("Verschlüsselung", True, "TLS-Verbindung steht"))
                steps.append(Step("Anmeldung", True, f"angemeldet{' als ' + creds['username'] if creds.get('username') else ''}"))
                await c.subscribe(topic)
                await c.publish(topic, "ping")
                try:
                    async with asyncio.timeout(4):
                        async for msg in c.messages:
                            if str(msg.topic) == topic:
                                break
                    steps.append(Step("Senden/Empfangen", True, "Testnachricht kam zurück"))
                except TimeoutError:
                    steps.append(Step("Senden/Empfangen", False, "Testnachricht kam nicht zurück – fehlen dem Benutzer "
                                                                 f"Rechte auf {P}/# (ACL)?"))
                await c.publish(topic, b"", retain=False)
        except aiomqtt.MqttCodeError as e:
            rc = getattr(e.rc, "value", e.rc)
            if rc in (4, 134):
                msg = "Benutzer oder Passwort falsch"
            elif rc in (5, 135):
                msg = ("Anmeldung abgelehnt – Benutzer/Passwort falsch oder Benutzer nicht freigeschaltet "
                       "(Mosquitto meldet beides gleich)")
            else:
                msg = str(e)
            steps.append(Step("Anmeldung", False, msg))
            return steps
        except aiomqtt.MqttError as e:
            text = str(e)
            if "SSL" in text or "certificate" in text.lower():
                steps.append(Step("Verschlüsselung", False, f"TLS fehlgeschlagen: {text}. Selbstsigniert? "
                                                            "mqtt_tls_insecure einschalten"))
            else:
                steps.append(Step("Anmeldung", False, f"Verbindung abgebrochen: {text}"))
            return steps
        # 3. laufende Verbindung des Add-ons
        if self.client:
            n = 5 + len(self.engine.db.q("SELECT id FROM persons"))
            steps.append(Step("Add-on verbunden", True, f"läuft; {n} Entitäten an HA gemeldet (Gerät „Haustür Zutritt“)"))
        else:
            steps.append(Step("Add-on verbunden", False, "Testverbindung geht, die Dauerverbindung aber nicht"
                              + (f" ({self.last_error})" if self.last_error else "") + " – Add-on neu starten"))
        return steps

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
