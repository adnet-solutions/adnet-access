"""Start: Datenbank, Leser-Verbindung, MQTT, Aufräumen, Kalender, Weboberfläche + Handy-Webhook."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn

from . import __version__, config, retention
from .db import DB
from .engine import Engine
from .esphome_link import EspLink
from .ha import HA
from .mqtt_bridge import MqttBridge
from .shelly import Shelly
from .web import create_phone_api, create_ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("adnet_access")


async def calendar_loop(engine: Engine) -> None:
    while True:
        if engine.opts.calendar_entity:
            try:
                names = await engine.ha.calendar_names_now(engine.opts.calendar_entity, engine.now())
                if names != engine.calendar_names:
                    engine.calendar_names = names
                    log.info("Kalender: aktuell freigegeben: %s", ", ".join(sorted(names)) or "niemand")
            except Exception as e:  # noqa: BLE001
                log.warning("Kalender nicht lesbar: %s", e)
        await asyncio.sleep(60)


def _bg(coro, name: str) -> asyncio.Task:
    async def guard():
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("Hintergrundaufgabe %s abgebrochen", name)
    return asyncio.create_task(guard(), name=name)


async def amain() -> None:
    opts = config.load()
    log.info("AD.NET Access %s startet", __version__)
    if not opts.pin_key:
        log.warning("pin_key ist leer – PINs sind dann nur schwach geschützt. Bitte setzen (gleich wie im ESPHome-Secret).")
    Path(opts.data_dir).mkdir(parents=True, exist_ok=True)
    db = DB(Path(opts.data_dir) / "adnet_access.db")
    engine = Engine(db, opts, HA(), Shelly(opts.shelly_host, opts.shelly_password, opts.shelly_switch_id))
    esp = EspLink(opts.esphome_host, opts.esphome_key, engine)
    mqtt = MqttBridge(engine, esp)
    engine.feedback = esp.feedback
    engine.on_event = mqtt.on_event

    async def rules_changed() -> None:
        await esp.push_list()
        await mqtt.publish_persons()
        await mqtt.publish_states()
    engine.on_rules_changed = rules_changed

    if opts.esphome_host:
        await esp.start()
    tasks = [_bg(mqtt.run(), "mqtt"),
             _bg(retention.loop(db, engine.snapshot_roots, opts.snapshot_days, opts.log_months), "aufraeumen"),
             _bg(calendar_loop(engine), "kalender")]

    ui = uvicorn.Server(uvicorn.Config(create_ui(engine, esp, mqtt), host="0.0.0.0", port=8099,
                                       log_level="warning", proxy_headers=False))
    phone = uvicorn.Server(uvicorn.Config(create_phone_api(engine), host="0.0.0.0", port=8098,
                                          log_level="warning", proxy_headers=False))
    ui.install_signal_handlers = phone.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    try:
        await asyncio.gather(ui.serve(), phone.serve())
    finally:
        for t in tasks:
            t.cancel()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
