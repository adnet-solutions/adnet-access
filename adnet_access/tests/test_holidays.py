"""Feiertage: eingebaute Liste und HA-Kalender."""
import asyncio
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from access.config import Options  # noqa: E402
from access.db import DB  # noqa: E402
from access.engine import Engine  # noqa: E402


class FakeHA:
    def __init__(self, result=None, state=None):
        self.result, self.state = result, state

    async def get_state(self, entity):
        return self.state

    async def calendar_dates(self, entity, start, end):
        return self.result


def engine(ha=None, **kw):
    d = tempfile.mkdtemp()
    o = Options(data_dir=d, media_dir=d + "/m", snapshot_dir=d + "/m", **kw)
    return Engine(DB(d + "/x.db"), o, ha, None)


def test_eingebaut_bayern():
    e = engine(holidays_subdiv="BY")
    assert e.is_holiday(datetime(2026, 11, 1, 9))          # Allerheiligen
    assert e.is_holiday(datetime(2026, 1, 6, 9))           # Heilige Drei Könige
    assert not e.is_holiday(datetime(2026, 10, 20, 9))
    assert not engine(holidays_subdiv="NW").is_holiday(datetime(2026, 1, 6, 9))


def test_kalender_ergaenzt_liste_und_fallback():
    e = engine(FakeHA(({date(2026, 10, 20)}, {date(2026, 10, 20): "Test"})), holidays_calendar="calendar.x")
    assert not e.is_holiday(datetime(2026, 10, 20, 9))      # noch nicht geladen
    asyncio.run(e.refresh_holidays())
    assert e.is_holiday(datetime(2026, 10, 20, 9)) and e.holiday_name(date(2026, 10, 20)) == "Test"
    assert e.is_holiday(datetime(2026, 11, 1, 9))            # gesetzliche Feiertage zählen weiter
    e.ha.result = None                                       # Kalender kurz nicht lesbar -> letzter Stand bleibt
    asyncio.run(e.refresh_holidays())
    assert e.is_holiday(datetime(2026, 10, 20, 9))


def test_entitaet_als_grundlage(monkeypatch):
    e = engine(FakeHA(state={"state": "kein_feiertag", "attributes": {"Name Feiertag": "All Saints' Day",
                                                                    "Datum": "01.11.2026"}}),
               holidays_entity="sensor.feiertag_de_by")
    monkeypatch.setattr(e, "now", lambda: datetime(2026, 1, 6, 9))      # Heilige Drei Könige
    asyncio.run(e.refresh_holiday_entity())
    assert not e.is_holiday(datetime(2026, 1, 6, 9))        # Entität sagt: kein Feiertag -> gilt
    assert e.holiday_name(date(2026, 11, 1)) == "All Saints' Day"
    e.ha.state = {"state": "Heilige Drei Könige", "attributes": {}}
    asyncio.run(e.refresh_holiday_entity())
    assert e.is_holiday(datetime(2026, 1, 6, 9))
    e.ha.state = {"state": "unavailable"}                   # nicht verfügbar -> eingebaute Liste
    asyncio.run(e.refresh_holiday_entity())
    assert e.is_holiday(datetime(2026, 1, 6, 9))
    b = engine(FakeHA(state={"state": "on"}), holidays_entity="binary_sensor.nur_feiertage_de_by")
    monkeypatch.setattr(b, "now", lambda: datetime(2026, 10, 20, 9))
    asyncio.run(b.refresh_holiday_entity())
    assert b.is_holiday(datetime(2026, 10, 20, 9))
