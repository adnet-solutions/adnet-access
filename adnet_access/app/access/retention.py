"""Aufräumen: alte Snapshots und Logbuch-Einträge löschen."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def cleanup(db, roots, snapshot_days: int, log_months: int, now: datetime | None = None) -> tuple[int, int]:
    """roots: ein Ordner oder eine Liste (gewählter Speicherort + Ausweich-Ordner)."""
    now = now or datetime.now()
    files = 0
    limit = time.time() - snapshot_days * 86400
    for media in ([roots] if isinstance(roots, Path) else roots):
        if not media.exists():
            continue
        for f in media.rglob("*.jpg"):
            if f.stat().st_mtime < limit:
                f.unlink(missing_ok=True)
                files += 1
        for d in sorted(media.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    cut_snap = (now - timedelta(days=snapshot_days)).isoformat()
    db.x("UPDATE log SET snapshot='' WHERE ts < ? AND snapshot<>''", (cut_snap,))
    cut_log = (now - timedelta(days=log_months * 31)).isoformat()
    before = db.one("SELECT COUNT(*) AS n FROM log")["n"]
    db.x("DELETE FROM log WHERE ts < ?", (cut_log,))
    removed = before - db.one("SELECT COUNT(*) AS n FROM log")["n"]
    return files, removed


async def loop(db, roots, snapshot_days: int, log_months: int) -> None:
    while True:
        try:
            f, r = cleanup(db, roots() if callable(roots) else roots, snapshot_days, log_months)
            if f or r:
                log.info("Aufgeräumt: %d Snapshots, %d Logbuch-Einträge", f, r)
        except Exception as e:  # noqa: BLE001
            log.error("Aufräumen fehlgeschlagen: %s", e)
        await asyncio.sleep(6 * 3600)
