"""Reine Regel-Logik (ohne I/O, getestet in tests/test_rules.py).

Zeitprofile: mehrere Regeln je Profil, jede Regel = Wochentage (Bitmaske Mo=1 ... So=64) + Start/Ende (HH:MM).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

DAY_NAMES = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MODES = {
    "card": "Nur Karte",
    "pin": "Nur PIN",
    "card_and_pin": "Karte + PIN",
    "card_or_pin": "Karte oder PIN",
}


def parse_hm(s: str) -> int:
    h, m = (s or "0:0").strip().split(":")
    v = int(h) * 60 + int(m)
    if not 0 <= v <= 1440:
        raise ValueError(f"Uhrzeit ungültig: {s}")
    return v


def parse_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    if len(s) == 10:                       # nur Datum
        return datetime.fromisoformat(s)
    return datetime.fromisoformat(s)


@dataclass
class Rule:
    days: int
    start: int   # Minuten seit 0:00
    end: int     # exklusiv, bis 1440

    def covers(self, weekday: int, minute: int) -> bool:
        return bool(self.days & (1 << weekday)) and self.start <= minute < self.end


@dataclass
class Profile:
    id: int
    name: str
    holidays_off: bool = True
    rules: list[Rule] = field(default_factory=list)

    def allows(self, dt: datetime, is_holiday: bool) -> bool:
        if is_holiday and self.holidays_off:
            return False
        minute = dt.hour * 60 + dt.minute
        return any(r.covers(dt.weekday(), minute) for r in self.rules)


@dataclass
class Person:
    id: int
    name: str
    mode: str = "card"
    valid_from: str = ""
    valid_to: str = ""
    blocked: bool = False
    blocked_until: str = ""
    ignore_vacation: bool = False
    always: bool = False
    profile_ids: list[int] = field(default_factory=list)


def _end_of_day_if_date(s: str) -> datetime | None:
    d = parse_dt(s)
    if d is not None and len(s.strip()) == 10:
        return d.replace(hour=23, minute=59, second=59)
    return d


def check_access(person: Person, profiles: dict[int, Profile], now: datetime, *, is_holiday: bool = False,
                 calendar_names: set[str] | None = None, vacation_lock: bool = False) -> tuple[bool, str]:
    """Prüft, ob eine (bereits identifizierte) Person jetzt rein darf. Gibt (erlaubt, Grund) zurück."""
    if person.blocked:
        return False, "gesperrt"
    bu = parse_dt(person.blocked_until)
    if bu and now < bu:
        return False, f"gesperrt bis {bu:%d.%m.%Y %H:%M}"
    vf = parse_dt(person.valid_from)
    if vf and now < vf:
        return False, f"erst gültig ab {vf:%d.%m.%Y}"
    vt = _end_of_day_if_date(person.valid_to)
    if vt and now > vt:
        return False, f"abgelaufen am {vt:%d.%m.%Y}"
    if vacation_lock and not person.ignore_vacation:
        return False, "Urlaubssperre aktiv"
    if person.always:
        return True, "immer erlaubt"
    if calendar_names and person.name.strip().lower() in calendar_names:
        return True, "Kalendertermin"
    if not person.profile_ids:
        return False, "kein Zeitprofil"
    for pid in person.profile_ids:
        p = profiles.get(pid)
        if p and p.allows(now, is_holiday):
            return True, f"Zeitprofil „{p.name}“"
    return False, "Feiertag" if is_holiday else "außerhalb der Zeitfenster"


# ---------------- Offline-Liste für den Atom ----------------
# Format: Einträge durch ';' getrennt, jeder Eintrag "T:WERT|MASKE|BIS"
#   T = K (Karte), P (PIN), C (Karte+PIN, WERT = "uid,pinhash")
#   MASKE = 42 Hex-Zeichen = 168 Bit, Bit i = Stunde i der Woche (Mo 0 Uhr = Bit 0), Bit i steht im
#           Hex-Zeichen i//4 an Position (3 - i%4)
#   BIS = Gültig-bis als Tage seit 1970-01-01 (hex), "ffff" = unbegrenzt
# Feiertage und Kalender werden offline nicht berücksichtigt; nur volle Stunden zählen.

def week_mask(person: Person, profiles: dict[int, Profile]) -> str:
    bits = [False] * 168
    if person.always:
        bits = [True] * 168
    else:
        for pid in person.profile_ids:
            p = profiles.get(pid)
            if not p:
                continue
            for r in p.rules:
                for wd in range(7):
                    if not r.days & (1 << wd):
                        continue
                    for h in range(24):
                        if r.start <= h * 60 and (h + 1) * 60 <= r.end:
                            bits[wd * 24 + h] = True
    out = []
    for i in range(0, 168, 4):
        nib = 0
        for j in range(4):
            if bits[i + j]:
                nib |= 1 << (3 - j)
        out.append(f"{nib:x}")
    return "".join(out)


def mask_allows(mask: str, now: datetime) -> bool:
    i = now.weekday() * 24 + now.hour
    return bool(int(mask[i // 4], 16) & (1 << (3 - i % 4)))


def valid_to_days(person: Person) -> str:
    vt = _end_of_day_if_date(person.valid_to)
    if not vt:
        return "ffff"
    return f"{(vt.date() - date(1970, 1, 1)).days:x}"


@dataclass
class Lockout:
    """Sperrt die Tastatur nach zu vielen Fehlversuchen (doppelte Dauer bei Wiederholung)."""
    attempts: int = 3
    seconds: int = 60
    failures: int = 0
    level: int = 0
    locked_until: float = 0.0

    def is_locked(self, t: float) -> bool:
        return t < self.locked_until

    def fail(self, t: float) -> bool:
        """Zählt einen Fehlversuch. True, wenn dadurch gesperrt wurde."""
        self.failures += 1
        if self.failures >= self.attempts:
            self.locked_until = t + self.seconds * (2 ** min(self.level, 6))
            self.level += 1
            self.failures = 0
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.level = 0
