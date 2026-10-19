"""Weboberfläche (über HA-Ingress) und Handy-Webhook (eigener Port)."""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import cardid
from .rules import DAY_NAMES, MODES, parse_hm
from .security import new_token, pin_hash

HERE = Path(__file__).parent
INGRESS_IP = "172.30.32.2"


def create_ui(engine, esp=None, mqtt=None) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    tpl = Jinja2Templates(directory=HERE / "templates")
    tpl.env.filters["hasday"] = lambda days, d: bool(int(days) & (1 << int(d)))
    tpl.env.globals["card_alt"] = lambda u: [(cardid.READERS[r], ", ".join(cardid.for_reader(u, r)))
                                             for r in cardid.READERS]
    db, opts = engine.db, engine.opts

    @app.middleware("http")
    async def only_ingress(request: Request, call_next):
        if not opts.dev and request.client and request.client.host != INGRESS_IP:
            return Response("Nur über Home Assistant erreichbar", status_code=403)
        return await call_next(request)

    def holiday_ctx() -> dict:
        import holidays as _h
        today = engine.now().date()
        cal = _h.Germany(subdiv=opts.holidays_subdiv or None, years=[today.year, today.year + 1])
        days = {d: (cal.get(d) or "") for d in cal.keys() if d >= today}
        if engine.entity_next and engine.entity_next[0] >= today:
            days[engine.entity_next[0]] = engine.entity_next[1]
        for d in engine.holiday_days or ():
            if d >= today:
                days[d] = engine.holiday_name(d)
        nxt = sorted(days.items())[:3]
        return {"next_holidays": nxt,
                "holidays_fallback": bool(opts.holidays_entity) and engine.entity_holiday is None,
                "extra_fallback": bool(opts.holidays_calendar) and engine.holiday_days is None}

    def render(request: Request, name: str, **ctx):
        if name == "settings.html":
            ctx = {**holiday_ctx(), **ctx}
        base = request.headers.get("X-Ingress-Path", "")
        return tpl.TemplateResponse(request, name, {"base": base, "MODES": MODES, "DAYS": DAY_NAMES,
                                                    "esp": esp, "mqtt": mqtt, "flag": engine.flag, **ctx})

    def back(request: Request, path: str):
        return RedirectResponse(request.headers.get("X-Ingress-Path", "") + path, status_code=303)

    async def changed(person_list: bool = False):
        await engine.rules_changed()
        if mqtt:
            if person_list:
                await mqtt.publish_persons()
            await mqtt.publish_states()

    # ---------------- Übersicht ----------------
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        rows = db.q("SELECT * FROM log ORDER BY id DESC LIMIT 15")
        stats = db.one("SELECT COUNT(*) n, SUM(result='erlaubt') ok, SUM(result='abgelehnt') nok FROM log "
                       "WHERE ts >= date('now','-1 day')")
        return render(request, "index.html", rows=rows, stats=stats)

    @app.post("/oeffnen")
    async def oeffnen(request: Request):
        await engine.open_manual()
        return back(request, "/")

    @app.post("/schalter/{key}")
    async def schalter(request: Request, key: str):
        if key in ("vacation_lock", "keypad_locked"):
            db.set(key, "0" if engine.flag(key) else "1")
            await changed()
        return back(request, "/")

    # ---------------- Personen ----------------
    @app.get("/personen", response_class=HTMLResponse)
    async def personen(request: Request):
        rows = db.q("SELECT p.*, (SELECT COUNT(*) FROM cards c WHERE c.person_id=p.id) AS n_cards, "
                    "(SELECT MAX(ts) FROM log l WHERE l.person_id=p.id AND l.result='erlaubt') AS last "
                    "FROM persons p ORDER BY p.name")
        now = engine.now()
        from datetime import timedelta
        profiles = engine.profiles()
        status, today, tomorrow = {}, {}, {}
        for r in rows:
            person = engine.person(r["id"])[0]
            status[r["id"]] = engine.evaluate(person, now)
            today[r["id"]] = engine.day_windows(person, now.date(), profiles)
            tomorrow[r["id"]] = engine.day_windows(person, now.date() + timedelta(days=1), profiles)
        return render(request, "persons.html", rows=rows, status=status, today=today, tomorrow=tomorrow,
                      tomorrow_label=(now + timedelta(days=1)).strftime("%a %d.%m.").replace(
                          "Mon", "Mo").replace("Tue", "Di").replace("Wed", "Mi").replace("Thu", "Do")
                      .replace("Fri", "Fr").replace("Sat", "Sa").replace("Sun", "So"))

    @app.get("/personen/{pid}", response_class=HTMLResponse)
    async def person_edit(request: Request, pid: int):
        row = db.one("SELECT * FROM persons WHERE id=?", (pid,)) if pid else None
        cards = db.q("SELECT * FROM cards WHERE person_id=? ORDER BY id", (pid,)) if pid else []
        sel = {r["profile_id"] for r in db.q("SELECT profile_id FROM person_profiles WHERE person_id=?", (pid,))}
        logs = db.q("SELECT * FROM log WHERE person_id=? ORDER BY id DESC LIMIT 20", (pid,)) if pid else []
        learning = engine.learn and engine.learn[0] == pid and time.monotonic() < engine.learn[1]
        return render(request, "person_edit.html", p=row, cards=cards, profiles=db.q("SELECT * FROM profiles"),
                      sel=sel, logs=logs, learning=learning, msg=request.query_params.get("msg", ""))

    @app.post("/personen/{pid}")
    async def person_save(request: Request, pid: int):
        f = await request.form()
        g = lambda k: (f.get(k) or "").strip()  # noqa: E731
        vals = dict(name=g("name"), note=g("note"), valid_from=g("valid_from"), valid_to=g("valid_to"),
                    mode=g("mode") if g("mode") in MODES else "card", phone_allowed=int(bool(f.get("phone_allowed"))),
                    notify=int(bool(f.get("notify"))), blocked=int(bool(f.get("blocked"))),
                    blocked_until=g("blocked_until"), block_reason=g("block_reason"),
                    ignore_vacation=int(bool(f.get("ignore_vacation"))), always=int(bool(f.get("always"))))
        if not vals["name"]:
            return back(request, f"/personen/{pid}?msg=Name+fehlt")
        if pid:
            db.x("UPDATE persons SET " + ", ".join(f"{k}=?" for k in vals) + " WHERE id=?", (*vals.values(), pid))
        else:
            pid = db.x("INSERT INTO persons(" + ",".join(vals) + ") VALUES(" + ",".join("?" * len(vals)) + ")",
                       tuple(vals.values()))
        db.x("DELETE FROM person_profiles WHERE person_id=?", (pid,))
        for prof in f.getlist("profiles"):
            db.x("INSERT OR IGNORE INTO person_profiles(person_id, profile_id) VALUES(?,?)", (pid, int(prof)))
        msg = "Gespeichert"
        pin = g("pin")
        if pin:
            min_len = 6 if vals["mode"] == "pin" else 4
            if not pin.isdigit() or not min_len <= len(pin) <= 8:
                msg = f"PIN nicht gespeichert: {min_len}–8 Ziffern nötig"
            else:
                h = pin_hash(opts.pin_key, pin)
                if db.one("SELECT id FROM persons WHERE pin_hash=? AND id<>?", (h, pid)):
                    msg = "PIN nicht gespeichert: diese PIN hat schon jemand anderes"
                else:
                    db.x("UPDATE persons SET pin_hash=? WHERE id=?", (h, pid))
        if f.get("pin_clear"):
            db.x("UPDATE persons SET pin_hash='' WHERE id=?", (pid,))
        row = db.one("SELECT phone_token, phone_allowed FROM persons WHERE id=?", (pid,))
        if row["phone_allowed"] and not row["phone_token"]:
            db.x("UPDATE persons SET phone_token=? WHERE id=?", (new_token(), pid))
        await changed(person_list=True)
        return back(request, f"/personen/{pid}?msg={msg.replace(' ', '+')}")

    @app.post("/personen/{pid}/loeschen")
    async def person_delete(request: Request, pid: int):
        db.x("DELETE FROM persons WHERE id=?", (pid,))
        if mqtt:
            await mqtt.remove_person(pid)
        await changed()
        return back(request, "/personen")

    @app.post("/personen/{pid}/token")
    async def person_token(request: Request, pid: int):
        db.x("UPDATE persons SET phone_token=? WHERE id=?", (new_token(), pid))
        return back(request, f"/personen/{pid}?msg=Neuer+Handy-Link+erzeugt")

    @app.post("/personen/{pid}/anlernen")
    async def person_learn(request: Request, pid: int):
        engine.learn = (pid, time.monotonic() + 60)
        engine.learned.pop(pid, None)
        return back(request, f"/personen/{pid}")

    @app.get("/personen/{pid}/anlernen/status")
    async def learn_status(pid: int):
        active = bool(engine.learn and engine.learn[0] == pid and time.monotonic() < engine.learn[1])
        return JSONResponse({"active": active, "learned": engine.learned.get(pid, "")})

    @app.post("/karten/{cid}/{action}")
    async def card_action(request: Request, cid: int, action: str):
        card = db.one("SELECT * FROM cards WHERE id=?", (cid,))
        if not card:
            return back(request, "/personen")
        if action == "sperren":
            db.x("UPDATE cards SET blocked=1-blocked WHERE id=?", (cid,))
        elif action == "loeschen":
            db.x("DELETE FROM cards WHERE id=?", (cid,))
        elif action == "name":
            f = await request.form()
            db.x("UPDATE cards SET label=? WHERE id=?", ((f.get("label") or "").strip(), cid))
        await changed()
        return back(request, f"/personen/{card['person_id']}")

    @app.post("/karten/zuordnen")
    async def card_assign(request: Request, uid: str = Form(...), person_id: int = Form(...)):
        if not engine.find_card(uid):
            db.x("INSERT INTO cards(person_id, uid) VALUES(?,?)", (person_id, cardid.normalize(uid)))
            await changed()
        return back(request, f"/personen/{person_id}")

    # ---------------- Zeitprofile ----------------
    @app.get("/zeitprofile", response_class=HTMLResponse)
    async def profiles(request: Request):
        profs = db.q("SELECT * FROM profiles ORDER BY name")
        rules = {p["id"]: db.q("SELECT * FROM profile_rules WHERE profile_id=? ORDER BY id", (p["id"],)) for p in profs}
        usage = {p["id"]: db.one("SELECT COUNT(*) n FROM person_profiles WHERE profile_id=?", (p["id"],))["n"]
                 for p in profs}
        return render(request, "profiles.html", profs=profs, rules=rules, usage=usage)

    @app.get("/zeitprofile/{pid}", response_class=HTMLResponse)
    async def profile_edit(request: Request, pid: int):
        prof = db.one("SELECT * FROM profiles WHERE id=?", (pid,)) if pid else None
        rules = db.q("SELECT * FROM profile_rules WHERE profile_id=? ORDER BY id", (pid,)) if pid else []
        return render(request, "profile_edit.html", prof=prof, rules=rules, msg=request.query_params.get("msg", ""))

    @app.post("/zeitprofile/{pid}")
    async def profile_save(request: Request, pid: int):
        f = await request.form()
        name = (f.get("name") or "").strip() or "Ohne Namen"
        hol = int(bool(f.get("holidays_off")))
        if pid:
            db.x("UPDATE profiles SET name=?, holidays_off=? WHERE id=?", (name, hol, pid))
        else:
            pid = db.x("INSERT INTO profiles(name, holidays_off) VALUES(?,?)", (name, hol))
        new_rules, err = [], ""
        for i in range(int(f.get("rows", 0))):
            days = sum(1 << d for d in range(7) if f.get(f"r{i}_d{d}"))
            st, en = (f.get(f"r{i}_start") or "").strip(), (f.get(f"r{i}_end") or "").strip()
            if not days or not st or not en:
                continue
            try:
                if parse_hm(st) >= parse_hm(en):
                    err = "Ende muss nach Beginn liegen"
                    continue
            except ValueError:
                err = "Uhrzeit im Format HH:MM"
                continue
            new_rules.append((pid, days, st, en))
        db.x("DELETE FROM profile_rules WHERE profile_id=?", (pid,))
        for r in new_rules:
            db.x("INSERT INTO profile_rules(profile_id, days, start, end) VALUES(?,?,?,?)", r)
        await changed()
        return back(request, f"/zeitprofile/{pid}?msg=" + (err or "Gespeichert").replace(" ", "+"))

    @app.post("/zeitprofile/{pid}/loeschen")
    async def profile_delete(request: Request, pid: int):
        db.x("DELETE FROM profiles WHERE id=?", (pid,))
        await changed()
        return back(request, "/zeitprofile")

    # ---------------- Logbuch ----------------
    def log_query(params) -> tuple[str, list]:
        where, args = [], []
        if params.get("person"):
            where.append("person_id=?")
            args.append(int(params["person"]))
        if params.get("result"):
            where.append("result=?")
            args.append(params["result"])
        if params.get("von"):
            where.append("ts>=?")
            args.append(params["von"])
        if params.get("bis"):
            where.append("ts<=?")
            args.append(params["bis"] + "T23:59:59")
        return (" WHERE " + " AND ".join(where)) if where else "", args

    @app.get("/logbuch", response_class=HTMLResponse)
    async def logbuch(request: Request):
        params = dict(request.query_params)
        page = max(int(params.get("seite", 1) or 1), 1)
        w, a = log_query(params)
        rows = db.q(f"SELECT * FROM log{w} ORDER BY id DESC LIMIT 50 OFFSET ?", (*a, (page - 1) * 50))
        total = db.one(f"SELECT COUNT(*) n FROM log{w}", a)["n"]
        persons = db.q("SELECT id, name FROM persons ORDER BY name")
        qs = "&".join(f"{k}={v}" for k, v in params.items() if k != "seite" and v)
        return render(request, "log.html", rows=rows, total=total, page=page, persons=persons, params=params, qs=qs)

    @app.get("/logbuch.csv")
    async def logbuch_csv(request: Request):
        w, a = log_query(dict(request.query_params))
        out = io.StringIO()
        wr = csv.writer(out, delimiter=";")
        wr.writerow(["Zeit", "Person", "Weg", "Karte", "Ergebnis", "Grund", "Snapshot", "Protect"])
        for r in db.q(f"SELECT * FROM log{w} ORDER BY id DESC", a):
            wr.writerow([r["ts"], r["person_name"], r["method"], r["credential"], r["result"], r["reason"],
                         r["snapshot"], r["protect_link"]])
        return Response(out.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=zutritt-{datetime.now():%Y%m%d}.csv"})

    @app.get("/snap/{lid}")
    async def snap(lid: int):
        row = db.one("SELECT snapshot FROM log WHERE id=?", (lid,))
        p = engine.snapshot_file(row["snapshot"]) if row else None
        if not p:
            return Response(status_code=404)
        return FileResponse(p, media_type="image/jpeg")

    # ---------------- Einstellungen ----------------
    @app.get("/einstellungen", response_class=HTMLResponse)
    async def settings(request: Request):
        store = engine.snapshot_store()
        return render(request, "settings.html", opts=opts, offline=engine.offline_list(), store=store,
                      store_ok=str(store) == str(Path(opts.snapshot_dir or opts.media_dir)),
                      msg=request.query_params.get("msg", ""))

    @app.post("/test/{what}")
    async def test(request: Request, what: str):
        msg = ""
        if what == "mqtt" and mqtt:
            steps = await mqtt.diagnose()
            store = engine.snapshot_store()
            return render(request, "settings.html", opts=opts, offline=engine.offline_list(), store=store,
                          store_ok=str(store) == str(Path(opts.snapshot_dir or opts.media_dir)), mqtt_steps=steps)
        if what in ("shelly", "shelly_schalten"):
            steps = await engine.shelly.diagnose(switch=what == "shelly_schalten")
            if what == "shelly_schalten" and any(st.name == "Schalten" and st.ok for st in steps):
                await engine.record(None, "test", "", True, "Shelly-Test: Tür geöffnet", info=True)
            store = engine.snapshot_store()
            return render(request, "settings.html", opts=opts, offline=engine.offline_list(), store=store,
                          store_ok=str(store) == str(Path(opts.snapshot_dir or opts.media_dir)), shelly_steps=steps)
        elif what == "snapshot":
            lid = await engine.record(None, "test", "", True, "Test-Snapshot", info=True)
            await engine.snapshot(lid)
            stored = db.one("SELECT snapshot FROM log WHERE id=?", (lid,))["snapshot"]
            msg = f"Snapshot gespeichert in {Path(stored).parent.parent.parent}" if stored \
                else "Kein Snapshot (Kamera-Entität prüfen)"
        elif what == "push":
            await engine.ha.notify(opts.notify_service, "Haustür", "Test-Benachrichtigung von AD.NET Access")
            msg = "Benachrichtigung gesendet"
        elif what == "liste" and esp:
            esp._last_list = None
            await esp.push_list()
            msg = "Offline-Liste an den Leser übertragen"
        return back(request, "/einstellungen?msg=" + msg.replace(" ", "+"))

    return app


def create_phone_api(engine) -> FastAPI:
    """Kleiner Server nur für den Handy-Webhook (Kurzbefehl/MacroDroid): GET oder POST /handy/<token>."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/handy/{token}", methods=["GET", "POST"])
    async def phone(token: str):
        if len(token) < 20:
            return JSONResponse({"ok": False}, status_code=404)
        ok = await engine.handle_phone(token)
        return JSONResponse({"ok": ok}, status_code=200 if ok else 403)

    return app
