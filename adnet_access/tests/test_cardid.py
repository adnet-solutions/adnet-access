"""Karten-IDs: RFID2-Hex, Wiegand 34 und Wiegand 26 müssen dieselbe Karte erkennen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from access.cardid import for_reader, same_card, values32  # noqa: E402

HEX = "74-10-37-94"
BE, LE = 0x74103794, 0x94371074


def test_werte():
    assert values32(HEX) == {BE, LE}
    assert values32(str(BE)) == {BE}
    assert values32("741037 94".replace(" ", ":")) == {BE, LE}


def test_gleiche_karte():
    assert same_card(HEX, str(BE)) and same_card(HEX, str(LE))     # Wiegand 34, beide Byte-Reihenfolgen
    assert same_card(str(LE), HEX.lower())
    assert same_card(HEX, str(BE & 0xFFFFFF))                       # Wiegand 26
    assert not same_card(HEX, "12345678") and not same_card(HEX, "74-10-37-95")
    assert same_card("04-A2-3B-11-22-33-80", str(0x112233 << 8 | 0x80))  # 7-Byte-UID, letzte 4 Byte


def test_offline_format():
    assert set(for_reader(HEX, "wiegand34")) == {str(BE), str(LE)}
    assert for_reader(HEX, "rfid2") == [HEX]
    assert set(for_reader(str(BE), "rfid2")) == {HEX, "94-37-10-74"}
    assert set(for_reader(HEX, "wiegand26")) == {str(BE & 0xFFFFFF), str(LE & 0xFFFFFF)}


def test_engine_findet_karte_anderer_leser():
    import tempfile
    from access.config import Options
    from access.db import DB
    from access.engine import Engine
    d = tempfile.mkdtemp()
    e = Engine(DB(d + "/x.db"), Options(data_dir=d, media_dir=d + "/m", snapshot_dir=d + "/m",
                                        reader_type="wiegand34"), None, None)
    pid = e.db.x("INSERT INTO persons(name, always) VALUES('A', 1)")
    e.db.x("INSERT INTO cards(person_id, uid) VALUES(?, ?)", (pid, HEX))      # mit RFID2 angelernt
    assert e.find_card(str(BE))["person_id"] == pid                            # an Wiegand vorgehalten
    assert f"K:{BE}|" in e.offline_list() and f"K:{LE}|" in e.offline_list()
