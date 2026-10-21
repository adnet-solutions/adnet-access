"""Seiten rendern mit echten Daten (Regression: Personenseite war leer, weil base.html 'p' ueberschrieb)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient  # noqa: E402

from access import config  # noqa: E402
from access.db import DB  # noqa: E402
from access.engine import Engine  # noqa: E402
from access.ha import HA  # noqa: E402
from access.shelly import Shelly  # noqa: E402
from access.web import create_ui  # noqa: E402


def test_personenseite(tmp_path):
    o = config.Options(data_dir=str(tmp_path), snapshot_dir=str(tmp_path / "snap"), dev=True)
    db = DB(tmp_path / "t.db")
    c = TestClient(create_ui(Engine(db, o, HA(), Shelly("", "", 0, 1))))
    c.post("/personen/0", data={"name": "Enrico Roga", "mode": "card", "always": "on"})
    r = c.get("/personen/1")
    assert re.search(r"<h2>Enrico Roga</h2>", r.text)
    assert 'action="/personen/1"' in r.text
    assert 'class="active">Personen' in r.text
    r = c.post("/personen/1/loeschen", follow_redirects=False)
    assert r.status_code == 303
    assert db.one("SELECT COUNT(*) n FROM persons")["n"] == 0
    for page in ("/", "/personen", "/zeitprofile", "/logbuch", "/einstellungen"):
        assert c.get(page).status_code == 200, page
