"""Karten-IDs unabhängig vom Leser vergleichen.

Dieselbe 13,56-MHz-Karte kommt je nach Leser unterschiedlich an:
  * RFID2 / RC522 (I2C):  UID als Hex-Bytes, z. B. "74-10-37-94" (bei 7-Byte-UIDs länger)
  * Wiegand 34:           32 Bit der UID als Dezimalzahl, z. B. "1947285396"
                          (Byte-Reihenfolge je nach Leser vorwärts oder rückwärts)
  * Wiegand 26:           nur 24 Bit davon als Dezimalzahl
Gespeichert wird immer, was der Leser beim Anlernen liefert. Verglichen wird über alle denkbaren
32-Bit-Werte; für die Offline-Liste rechnet das Add-on in das Format des eingestellten Lesers um.
"""
from __future__ import annotations

import re

READERS = {"wiegand34": "Wiegand 34 (Tastatur)", "wiegand26": "Wiegand 26", "rfid2": "RFID2 / RC522 (Hex)"}
_HEX_SEP = re.compile(r"[\s:\-]")


def normalize(uid: str) -> str:
    return (uid or "").strip().upper()


def _hex_bytes(s: str) -> bytes | None:
    if s.isdigit() and not _HEX_SEP.search(s):
        return None                                   # reine Dezimalzahl -> Wiegand
    h = _HEX_SEP.sub("", s)
    if not h or len(h) % 2 or not re.fullmatch(r"[0-9A-F]+", h):
        return None
    return bytes.fromhex(h)


def values32(uid: str) -> set[int]:
    """Alle 32-Bit-Werte, die diese Karte an einem Wiegand-34-Leser haben könnte."""
    s = normalize(uid)
    b = _hex_bytes(s)
    if b is None:
        return {int(s)} if s.isdigit() else set()
    if len(b) < 4:
        return {int.from_bytes(b, "big")}
    out = set()
    for part in {b[:4], b[-4:]}:                       # 7-Byte-UIDs: Leser nehmen Anfang oder Ende
        out.add(int.from_bytes(part, "big"))
        out.add(int.from_bytes(part, "little"))
    return out


def same_card(a: str, b: str) -> bool:
    if normalize(a) == normalize(b):
        return True
    va, vb = values32(a), values32(b)
    if va & vb:
        return True
    # Wiegand 26 überträgt nur die unteren 24 Bit
    short_a = {v for v in va if v < 1 << 24}
    short_b = {v for v in vb if v < 1 << 24}
    return any((x & 0xFFFFFF) in short_b for x in va) or any((y & 0xFFFFFF) in short_a for y in vb)


def for_reader(uid: str, reader: str) -> list[str]:
    """Darstellungen der Karte, wie sie der eingestellte Leser liefern würde (für die Offline-Liste)."""
    s = normalize(uid)
    b = _hex_bytes(s)
    if reader == "rfid2":
        if b is not None:
            return ["-".join(f"{x:02X}" for x in b)]
        n = int(s)
        be = n.to_bytes(4, "big")
        return sorted({"-".join(f"{x:02X}" for x in be), "-".join(f"{x:02X}" for x in be[::-1])})
    vals = values32(s)
    if reader == "wiegand26":
        vals = {v & 0xFFFFFF for v in vals}
    return sorted(str(v) for v in vals)
