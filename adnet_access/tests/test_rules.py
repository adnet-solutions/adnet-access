"""Tests der Regel-Logik und der Offline-Liste.  Aufruf:  cd adnet_access && python -m pytest tests"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from access.rules import (Lockout, Person, Profile, Rule, check_access, mask_allows, parse_hm,  # noqa: E402
                          valid_to_days, week_mask)
from access.security import pin_hash  # noqa: E402

PUTZ = Profile(1, "Putzhilfe", True, [Rule(2 | 16, parse_hm("07:00"), parse_hm("13:00"))])   # Di + Fr
PROFILES = {1: PUTZ}
DI_9 = datetime(2026, 10, 20, 9, 0)      # Dienstag
MI_9 = datetime(2026, 10, 21, 9, 0)


def person(**kw):
    return Person(1, "Maria", profile_ids=[1], **kw)


def test_zeitfenster():
    assert check_access(person(), PROFILES, DI_9)[0]
    assert not check_access(person(), PROFILES, MI_9)[0]
    assert not check_access(person(), PROFILES, DI_9.replace(hour=13))[0]      # Ende exklusiv
    assert check_access(person(), PROFILES, DI_9.replace(hour=12, minute=59))[0]


def test_feiertag():
    ok, reason = check_access(person(), PROFILES, DI_9, is_holiday=True)
    assert not ok and reason == "Feiertag"


def test_gueltigkeit_und_sperre():
    assert not check_access(person(valid_to="2026-10-19"), PROFILES, DI_9)[0]
    assert check_access(person(valid_to="2026-10-20"), PROFILES, DI_9)[0]       # Datum = ganzer Tag
    assert not check_access(person(valid_from="2026-11-01"), PROFILES, DI_9)[0]
    assert not check_access(person(blocked=True), PROFILES, DI_9)[0]
    assert not check_access(person(blocked_until="2026-10-20T10:00"), PROFILES, DI_9)[0]
    assert check_access(person(blocked_until="2026-10-20T08:00"), PROFILES, DI_9)[0]


def test_urlaub_immer_kalender():
    assert not check_access(person(), PROFILES, DI_9, vacation_lock=True)[0]
    assert check_access(person(ignore_vacation=True), PROFILES, DI_9, vacation_lock=True)[0]
    assert check_access(person(always=True), PROFILES, MI_9)[0]
    assert check_access(person(), PROFILES, MI_9, calendar_names={"maria"})[0]
    assert not check_access(Person(2, "Ohne"), PROFILES, DI_9)[0]


def test_wochenmaske():
    m = week_mask(person(), PROFILES)
    assert len(m) == 42
    assert mask_allows(m, DI_9) and mask_allows(m, DI_9.replace(hour=7))
    assert not mask_allows(m, DI_9.replace(hour=13)) and not mask_allows(m, MI_9)
    assert mask_allows(m, datetime(2026, 10, 23, 12, 30))                         # Freitag
    assert week_mask(person(always=True), PROFILES) == "f" * 42
    # halbe Stunden zählen offline nicht
    half = {1: Profile(1, "x", True, [Rule(1, parse_hm("07:30"), parse_hm("09:00"))])}
    hm = week_mask(person(), half)
    assert not mask_allows(hm, datetime(2026, 10, 19, 7, 45)) and mask_allows(hm, datetime(2026, 10, 19, 8, 10))


def test_valid_to_days():
    assert valid_to_days(person()) == "ffff"
    assert int(valid_to_days(person(valid_to="2026-10-20")), 16) == 20746


def test_lockout():
    lo = Lockout(3, 60)
    assert not lo.fail(0) and not lo.fail(1) and lo.fail(2)
    assert lo.is_locked(30) and not lo.is_locked(63)
    lo.fail(100), lo.fail(100), lo.fail(100)
    assert lo.is_locked(100 + 119)                                                 # doppelte Dauer
    lo.success()
    assert lo.level == 0


def test_pin_hash_stabil():
    h = pin_hash("geheim", "1234")
    assert h == pin_hash("geheim", "1234") and h != pin_hash("anders", "1234") and len(h) == 32


def test_tagesfenster():
    import tempfile
    from datetime import date
    from access.config import Options
    from access.db import DB
    from access.engine import Engine
    d = tempfile.mkdtemp()
    e = Engine(DB(d + "/x.db"), Options(data_dir=d, media_dir=d + "/m", snapshot_dir=d + "/m"), None, None)
    putz = e.profiles()[2]                                   # Seed: Putzhilfe Di+Fr 7-13
    p = Person(9, "P", profile_ids=[putz.id])
    assert e.day_windows(p, date(2026, 10, 20)) == ([("07:00", "13:00")], "")      # Dienstag
    w, why = e.day_windows(p, date(2026, 10, 21))
    assert w == [] and why == "außerhalb der Zeitfenster"
    assert e.day_windows(p, date(2027, 1, 6))[1] in ("Feiertag", "außerhalb der Zeitfenster")
    assert e.day_windows(Person(8, "F", always=True), date(2026, 10, 21)) == ([("00:00", "24:00")], "")
    w, why = e.day_windows(Person(7, "G", always=True, blocked=True), date(2026, 10, 21))
    assert w == [] and why == "gesperrt"
