"""SQLite-Datenbank: Personen, Karten, Zeitprofile, Logbuch, Einstellungen."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    note TEXT DEFAULT '',
    valid_from TEXT DEFAULT '',          -- ISO-Datum/Zeit, leer = sofort
    valid_to TEXT DEFAULT '',            -- ISO-Datum/Zeit, leer = unbegrenzt
    mode TEXT NOT NULL DEFAULT 'card',   -- card | pin | card_and_pin | card_or_pin
    pin_hash TEXT DEFAULT '',
    phone_allowed INTEGER DEFAULT 0,
    phone_token TEXT DEFAULT '',
    notify INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0,
    blocked_until TEXT DEFAULT '',
    block_reason TEXT DEFAULT '',
    ignore_vacation INTEGER DEFAULT 0,   -- darf auch bei Urlaubssperre rein (Familie)
    always INTEGER DEFAULT 0,            -- ohne Zeitprofil jederzeit (Familie)
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    uid TEXT NOT NULL UNIQUE,
    label TEXT DEFAULT '',
    blocked INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    holidays_off INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS profile_rules (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    days INTEGER NOT NULL,               -- Bitmaske Mo=1, Di=2, ... So=64
    start TEXT NOT NULL,                 -- HH:MM
    end TEXT NOT NULL                    -- HH:MM (exklusiv), 24:00 erlaubt
);
CREATE TABLE IF NOT EXISTS person_profiles (
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    PRIMARY KEY (person_id, profile_id)
);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    person_id INTEGER,
    person_name TEXT DEFAULT '',
    method TEXT DEFAULT '',              -- karte | pin | karte+pin | handy | manuell | offline
    credential TEXT DEFAULT '',          -- Karten-ID (PIN nie)
    result TEXT NOT NULL,                -- erlaubt | abgelehnt | info
    reason TEXT DEFAULT '',
    snapshot TEXT DEFAULT '',
    protect_link TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS log_ts ON log(ts);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class DB:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._seed()

    @contextmanager
    def tx(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def q(self, sql: str, args=()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, args))

    def one(self, sql: str, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    def x(self, sql: str, args=()) -> int:
        with self.tx() as c:
            cur = c.execute(sql, args)
            return cur.lastrowid

    # ---- Einstellungen ----
    def get(self, key: str, default: str = "") -> str:
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set(self, key: str, value: str) -> None:
        self.x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, value))

    def _seed(self) -> None:
        if self.one("SELECT id FROM profiles LIMIT 1"):
            return
        with self.tx() as c:
            pid = c.execute("INSERT INTO profiles(name, holidays_off) VALUES('Werktags 8-18 Uhr', 1)").lastrowid
            c.execute("INSERT INTO profile_rules(profile_id, days, start, end) VALUES(?, 31, '08:00', '18:00')", (pid,))
            pid = c.execute("INSERT INTO profiles(name, holidays_off) VALUES('Putzhilfe Di+Fr 7-13 Uhr', 1)").lastrowid
            c.execute("INSERT INTO profile_rules(profile_id, days, start, end) VALUES(?, 18, '07:00', '13:00')", (pid,))
