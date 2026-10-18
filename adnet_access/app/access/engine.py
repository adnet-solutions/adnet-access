"""Entscheidungs-Kern: Karte/PIN/Handy -> Regeln prüfen -> Tür öffnen, Logbuch, Snapshot, Benachrichtigung."""
from __future__ import annotations

import asyncio
import io
import os
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

import holidays

from .config import Options
from .db import DB
from .ha import HA
from .rules import Lockout, Person, Profile, Rule, check_access, parse_hm, valid_to_days, week_mask
from .shelly import Shelly

log = logging.getLogger(__name__)


@dataclass
class Pending:
    person_id: int
    uid: str
    expires: float


class Engine:
    def __init__(self, db: DB, opts: Options, ha: HA, shelly: Shelly) -> None:
        self.db, self.opts, self.ha, self.shelly = db, opts, ha, shelly
        self.tz = ZoneInfo(opts.timezone)
        self.holidays = holidays.Germany(subdiv=opts.holidays_subdiv or None)
        self.holiday_days: set | None = None       # gesetzt, wenn holidays_calendar genutzt wird
        self.holiday_names: dict = {}
        self.lockout = Lockout(opts.lockout_attempts, opts.lockout_seconds)
        self.pending: Pending | None = None
        self.learn: tuple[int, float] | None = None      # (person_id, bis)
        self.learned: dict[int, str] = {}                # person_id -> zuletzt angelernte Karte
        self.calendar_names: set[str] = set()
        self.media = Path(opts.media_dir)          # Ausweich-Ordner, immer vorhanden
        self.media.mkdir(parents=True, exist_ok=True)
        self._store_warned = False
        # Rückkanäle, werden von main.py gesetzt
        self.feedback: Callable[[bool], Awaitable[None]] | None = None
        self.on_event: Callable[[dict], Awaitable[None]] | None = None
        self.on_rules_changed: Callable[[], Awaitable[None]] | None = None

    # ---------------- Hilfen ----------------
    def now(self) -> datetime:
        return datetime.now(self.tz).replace(tzinfo=None)

    def is_holiday(self, dt: datetime) -> bool:
        if self.holiday_days is not None:            # Feiertagskalender aus HA (holidays_calendar)
            return dt.date() in self.holiday_days
        return dt.date() in self.holidays

    def holiday_name(self, d) -> str:
        if self.holiday_days is not None:
            return self.holiday_names.get(d, "") if d in self.holiday_days else ""
        return self.holidays.get(d) or ""

    async def refresh_holidays(self) -> None:
        """Feiertage aus dem HA-Kalender holen (ein Jahr im Voraus). Schlägt das fehl, bleibt der letzte
        Stand; gab es noch keinen, gilt die eingebaute Liste (holidays_subdiv)."""
        if not self.opts.holidays_calendar:
            self.holiday_days = None
            return
        now = self.now().replace(hour=0, minute=0, second=0, microsecond=0)
        res = await self.ha.calendar_dates(self.opts.holidays_calendar, now - timedelta(days=1),
                                           now + timedelta(days=370))
        if res is not None:
            self.holiday_days, self.holiday_names = res

    def flag(self, key: str) -> bool:
        return self.db.get(key) == "1"

    def keypad_locked_until(self) -> float:
        try:
            return float(self.db.get("keypad_locked_until", "0"))
        except ValueError:
            return 0.0

    def profiles(self) -> dict[int, Profile]:
        out: dict[int, Profile] = {}
        for p in self.db.q("SELECT * FROM profiles"):
            out[p["id"]] = Profile(p["id"], p["name"], bool(p["holidays_off"]), [])
        for r in self.db.q("SELECT * FROM profile_rules"):
            if r["profile_id"] in out:
                out[r["profile_id"]].rules.append(Rule(r["days"], parse_hm(r["start"]), parse_hm(r["end"])))
        return out

    def person(self, pid: int) -> tuple[Person, dict] | None:
        row = self.db.one("SELECT * FROM persons WHERE id=?", (pid,))
        if not row:
            return None
        prof = [r["profile_id"] for r in self.db.q("SELECT profile_id FROM person_profiles WHERE person_id=?", (pid,))]
        p = Person(row["id"], row["name"], row["mode"], row["valid_from"] or "", row["valid_to"] or "",
                   bool(row["blocked"]), row["blocked_until"] or "", bool(row["ignore_vacation"]), bool(row["always"]),
                   prof)
        return p, dict(row)

    def evaluate(self, person: Person, now: datetime) -> tuple[bool, str]:
        return check_access(person, self.profiles(), now, is_holiday=self.is_holiday(now),
                            calendar_names=self.calendar_names, vacation_lock=self.flag("vacation_lock"))

    # ---------------- Eingänge ----------------
    async def handle_card(self, uid: str) -> None:
        uid = uid.strip().upper()
        t = time.monotonic()
        if self.learn and t < self.learn[1]:
            await self._learn_card(self.learn[0], uid)
            return
        if blocked := self._blocked_reason(t):
            await self.record(None, "karte", uid, False, blocked)
            return
        card = self.db.one("SELECT * FROM cards WHERE uid=?", (uid,))
        if not card:
            await self._fail(None, "karte", uid, "unbekannte Karte")
            return
        res = self.person(card["person_id"])
        if not res:
            await self._fail(None, "karte", uid, "Karte ohne Person")
            return
        person, row = res
        if card["blocked"]:
            await self._fail(person, "karte", uid, "Karte gesperrt", row)
            return
        if person.mode == "pin":
            await self._fail(person, "karte", uid, "Person darf nur per PIN", row)
            return
        ok, reason = self.evaluate(person, self.now())
        if not ok:
            await self.record(person, "karte", uid, False, reason, row)
            return
        if person.mode == "card_and_pin":
            self.pending = Pending(person.id, uid, t + self.opts.card_pin_timeout)
            log.info("Karte von %s erkannt, warte auf PIN", person.name)
            return
        await self._grant(person, "karte", uid, reason, row)

    async def handle_pin(self, pin_hash: str) -> None:
        t = time.monotonic()
        if blocked := self._blocked_reason(t):
            await self.record(None, "pin", "", False, blocked)
            return
        pend, self.pending = self.pending, None
        if pend and t < pend.expires:
            res = self.person(pend.person_id)
            if res:
                person, row = res
                if row["pin_hash"] and row["pin_hash"] == pin_hash:
                    ok, reason = self.evaluate(person, self.now())
                    if ok:
                        await self._grant(person, "karte+pin", pend.uid, reason, row)
                    else:
                        await self.record(person, "karte+pin", pend.uid, False, reason, row)
                else:
                    await self._fail(person, "karte+pin", pend.uid, "falscher PIN", row)
                return
        for row in self.db.q("SELECT id FROM persons WHERE mode IN ('pin','card_or_pin') AND pin_hash=?", (pin_hash,)):
            res = self.person(row["id"])
            if not res:
                continue
            person, prow = res
            ok, reason = self.evaluate(person, self.now())
            if ok:
                await self._grant(person, "pin", "", reason, prow)
            else:
                await self.record(person, "pin", "", False, reason, prow)
            return
        await self._fail(None, "pin", "", "PIN unbekannt")

    async def handle_phone(self, token: str) -> bool:
        row = self.db.one("SELECT id FROM persons WHERE phone_allowed=1 AND phone_token=? AND phone_token<>''", (token,))
        if not row:
            await self.record(None, "handy", "", False, "unbekanntes Handy")
            return False
        person, prow = self.person(row["id"])
        ok, reason = self.evaluate(person, self.now())
        if ok:
            await self._grant(person, "handy", "", reason, prow)
        else:
            await self.record(person, "handy", "", False, reason, prow)
        return ok

    async def handle_offline(self, method: str, card: str, pin: str, result: str, unix_ts: int) -> None:
        """Ereignis, das der Atom ohne Add-on selbst entschieden hat (nur ins Logbuch, Tür ist schon offen)."""
        person = None
        if card:
            row = self.db.one("SELECT person_id FROM cards WHERE uid=?", (card.upper(),))
            person = self.person(row["person_id"]) if row else None
        elif pin:
            row = self.db.one("SELECT id FROM persons WHERE pin_hash=?", (pin,))
            person = self.person(row["id"]) if row else None
        texts = {"offen": "offline geöffnet", "abgelehnt": "offline abgelehnt", "warte_pin": "offline: Karte, warte auf PIN",
                 "keine_zeit": "offline: Leser kannte die Uhrzeit nicht"}
        when = datetime.fromtimestamp(unix_ts, self.tz).replace(tzinfo=None) if unix_ts > 1_600_000_000 else None
        await self.record(person[0] if person else None, f"{method} (offline)", card.upper(), result == "offen",
                          texts.get(result, result), person[1] if person else None, info=result == "warte_pin",
                          ts=when, snapshot=False)

    async def open_manual(self, who: str = "Weboberfläche") -> None:
        await self.shelly.pulse()
        await self.record(None, "manuell", "", True, f"geöffnet über {who}")

    # ---------------- intern ----------------
    def _blocked_reason(self, t: float) -> str:
        if self.lockout.is_locked(t):
            return "Tastatur nach Fehlversuchen kurz gesperrt"
        if time.time() < self.keypad_locked_until() or self.flag("keypad_locked"):
            return "Tastatur gesperrt"
        return ""

    async def _learn_card(self, person_id: int, uid: str) -> None:
        self.learn = None
        existing = self.db.one("SELECT person_id FROM cards WHERE uid=?", (uid,))
        if existing:
            self.learned[person_id] = f"bereits vergeben:{uid}"
            await self.record(None, "karte", uid, False, "Anlernen: Karte ist bereits vergeben", info=True)
            return
        self.db.x("INSERT INTO cards(person_id, uid, label) VALUES(?,?,?)", (person_id, uid, ""))
        self.learned[person_id] = uid
        res = self.person(person_id)
        await self.record(res[0] if res else None, "karte", uid, True, "Karte angelernt", info=True)
        await self.rules_changed()

    async def _fail(self, person: Person | None, method: str, cred: str, reason: str, row: dict | None = None) -> None:
        locked = self.lockout.fail(time.monotonic())
        await self.record(person, method, cred, False, reason, row)
        if locked:
            await self.alert(f"Tastatur gesperrt nach {self.opts.lockout_attempts} Fehlversuchen (zuletzt: {reason})")

    async def _grant(self, person: Person, method: str, cred: str, reason: str, row: dict) -> None:
        self.lockout.success()
        ok = await self.shelly.pulse()
        if self.feedback:
            asyncio.create_task(self.feedback(ok))
        await self.record(person, method, cred, ok, reason if ok else "Shelly nicht erreichbar", row)

    async def rules_changed(self) -> None:
        if self.on_rules_changed:
            await self.on_rules_changed()

    async def alert(self, message: str) -> None:
        await self.ha.notify(self.opts.notify_service, "Haustür: Warnung", message)

    async def record(self, person: Person | None, method: str, cred: str, granted: bool, reason: str,
                     row: dict | None = None, info: bool = False, ts: datetime | None = None,
                     snapshot: bool = True) -> int:
        now = ts or self.now()
        result = "info" if info else ("erlaubt" if granted else "abgelehnt")
        protect = ""
        if self.opts.protect_link_template:
            ts_ms = int(now.replace(tzinfo=self.tz).timestamp() * 1000)
            protect = self.opts.protect_link_template.replace("{ts_ms}", str(ts_ms)).replace("{ts}", str(ts_ms // 1000))
        lid = self.db.x("INSERT INTO log(ts, person_id, person_name, method, credential, result, reason, protect_link)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (now.isoformat(timespec="seconds"), person.id if person else None,
                         person.name if person else "", method, cred, result, reason, protect))
        log.info("%s: %s %s (%s)", result, person.name if person else "?", method, reason)
        asyncio.create_task(self._after(lid, person, method, granted, reason, row or {}, info or not snapshot))
        return lid

    async def _after(self, lid: int, person: Person | None, method: str, granted: bool, reason: str, row: dict,
                     info: bool) -> None:
        image = ""
        if not info:
            image = await self.snapshot(lid)
        if self.on_event:
            await self.on_event({"id": lid, "person": person.name if person else "", "method": method,
                                 "granted": granted, "reason": reason, "image": image})
        if granted and row.get("notify") and self.opts.notify_service:
            await self.ha.notify(self.opts.notify_service, "Haustür geöffnet",
                                 f"{person.name} ({method}) um {self.now():%H:%M}", image)

    def snapshot_roots(self) -> list[Path]:
        """Alle Ordner, in denen Snapshots liegen dürfen (gewählter Speicherort + Ausweich-Ordner)."""
        roots = [self.media]
        if self.opts.snapshot_dir:
            roots.insert(0, Path(self.opts.snapshot_dir))
        return list(dict.fromkeys(roots))

    def snapshot_store(self) -> Path:
        """Gewählter Speicherort, falls erreichbar (USB-Stick/NAS eingehängt), sonst Ausweich-Ordner.

        Der oberste Ordner unter /media (z. B. /media/usbstick) wird nie selbst angelegt: fehlt er, ist der
        Stick nicht eingehängt und wir würden sonst unbemerkt auf die interne Platte schreiben.
        """
        want = Path(self.opts.snapshot_dir or self.opts.media_dir)
        if want == self.media:
            return self.media
        parts = want.parts
        under_media = len(parts) >= 3 and parts[1] == "media"
        top = Path(*parts[:3]) if under_media else want.parent
        try:
            # NAS/USB: /media/<name> muss ein eingehängtes Laufwerk sein. Ein leerer Ordner (NAS aus,
            # Stick abgezogen) zählt nicht, sonst würde unbemerkt auf die interne Platte geschrieben.
            mounted = os.path.ismount(top) if under_media else top.is_dir()
            if mounted:
                want.mkdir(parents=True, exist_ok=True)
                probe = want / ".schreibtest"
                probe.write_bytes(b"")
                probe.unlink()
                if self._store_warned:
                    log.info("Speicherort %s wieder erreichbar", want)
                self._store_warned = False
                return want
        except OSError as e:
            log.debug("Speicherort %s nicht beschreibbar: %s", want, e)
        if not self._store_warned:
            log.warning("Speicherort %s nicht erreichbar (USB-Stick/NAS eingehängt?) – speichere vorübergehend in %s",
                        want, self.media)
            self._store_warned = True
        return self.media

    async def snapshot(self, lid: int) -> str:
        data = await self.ha.camera_snapshot(self.opts.camera_entity)
        if not data:
            return ""
        now = self.now()
        path = self.snapshot_store() / f"{now:%Y/%m}" / f"{now:%Y%m%d-%H%M%S}-{lid}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = self._crop(data)
        except Exception as e:  # noqa: BLE001
            log.warning("Zuschneiden fehlgeschlagen: %s", e)
        path.write_bytes(data)
        self.db.x("UPDATE log SET snapshot=? WHERE id=?", (str(path), lid))
        # HA-Medienpfad für Benachrichtigungen: /media/<x> ist in HA /media/local/<x>
        return "/media/local/" + str(path.relative_to("/media")) if path.is_relative_to("/media") else ""

    def snapshot_file(self, stored: str) -> Path | None:
        """Pfad aus dem Logbuch prüfen: nur Dateien innerhalb der erlaubten Ordner."""
        if not stored:
            return None
        p = Path(stored)
        if not p.is_absolute():                  # alte Einträge (relativ zum Standardordner)
            p = self.media / p
        p = p.resolve()
        for root in self.snapshot_roots():
            if p.is_relative_to(root.resolve()) and p.is_file():
                return p
        return None

    def _crop(self, data: bytes) -> bytes:
        """snapshot_crop = 'x,y,b,h' in Prozent des Bildes, z. B. '30,20,40,60'."""
        if not self.opts.snapshot_crop:
            return data
        from PIL import Image
        x, y, w, h = (float(v) / 100 for v in self.opts.snapshot_crop.split(","))
        im = Image.open(io.BytesIO(data))
        W, H = im.size
        im = im.crop((int(x * W), int(y * H), int((x + w) * W), int((y + h) * H)))
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=85)
        return out.getvalue()

    # ---------------- Offline-Liste ----------------
    def offline_list(self) -> str:
        """Kompakte Berechtigungsliste für den Atom (Format siehe rules.py)."""
        if self.flag("keypad_locked") or time.time() < self.keypad_locked_until():
            return ""
        profiles = self.profiles()
        now = self.now()
        vacation = self.flag("vacation_lock")
        entries: list[str] = []
        for row in self.db.q("SELECT id FROM persons"):
            person, prow = self.person(row["id"])
            if person.blocked or (vacation and not person.ignore_vacation):
                continue
            ok, reason = check_access(person, profiles, now, calendar_names=set())
            if not ok and reason.startswith(("gesperrt", "abgelaufen", "erst gültig")):
                continue
            mask, until = week_mask(person, profiles), valid_to_days(person)
            if mask == "0" * 42:
                continue
            cards = [c["uid"] for c in self.db.q("SELECT uid FROM cards WHERE person_id=? AND blocked=0", (person.id,))]
            pin = prow["pin_hash"]
            if person.mode in ("card", "card_or_pin"):
                entries += [f"K:{u}|{mask}|{until}" for u in cards]
            if person.mode in ("pin", "card_or_pin") and pin:
                entries.append(f"P:{pin}|{mask}|{until}")
            if person.mode == "card_and_pin" and pin:
                entries += [f"C:{u},{pin}|{mask}|{until}" for u in cards]
        return ";".join(entries)
