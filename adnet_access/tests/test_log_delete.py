"""Logbuch von Hand loeschen (inkl. Snapshots)."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from access import retention  # noqa: E402
from access.db import DB  # noqa: E402


def test_loeschen(tmp_path):
    db = DB(tmp_path / "t.db")
    snap = tmp_path / "alt.jpg"
    snap.write_bytes(b"x")
    db.x("INSERT INTO log(ts,method,result,reason,snapshot) VALUES('2026-09-01T10:00:00','karte','erlaubt','',?)", (str(snap),))
    db.x("INSERT INTO log(ts,method,result,reason) VALUES('2026-10-20T10:00:00','karte','erlaubt','')")
    check = lambda s: Path(s) if s.startswith(str(tmp_path)) else None  # noqa: E731
    now = datetime(2026, 10, 21, 12, 0)
    assert retention.delete_entries(db, check, 30, now) == (1, 1)
    assert not snap.exists()
    assert db.one("SELECT COUNT(*) n FROM log")["n"] == 1
    assert retention.delete_entries(db, check, None, now) == (1, 0)
    assert db.one("SELECT COUNT(*) n FROM log")["n"] == 0
