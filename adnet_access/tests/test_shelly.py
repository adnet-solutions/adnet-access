"""Shelly-Prüfung gegen einen simulierten Gen2-Shelly mit Digest-Anmeldung."""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from access.shelly import Shelly  # noqa: E402


class FakeShelly:
    def __init__(self, password="geheim", auth_en=True, gen=2):
        self.password, self.auth_en, self.gen = password, auth_en, gen
        self.off_at = 0.0

    def _authorized(self, req: httpx.Request) -> bool:
        if not self.auth_en:
            return True
        h = req.headers.get("authorization", "")
        if not h.startswith("Digest "):
            return False
        f = dict(p.strip().split("=", 1) for p in h[7:].split(","))
        f = {k: v.strip('"') for k, v in f.items()}
        ha1 = hashlib.sha256(f"admin:shellyplus1-x:{self.password}".encode()).hexdigest()
        ha2 = hashlib.sha256(f"{req.method}:{f['uri']}".encode()).hexdigest()
        exp = hashlib.sha256(f"{ha1}:{f['nonce']}:{f['nc']}:{f['cnonce']}:{f['qop']}:{ha2}".encode()).hexdigest()
        return f.get("response") == exp

    def handler(self, req: httpx.Request) -> httpx.Response:
        if req.url.path == "/shelly":
            return httpx.Response(200, json={"name": "Haustür", "model": "SNSW-001X16EU", "gen": self.gen,
                                             "ver": "1.4.4", "auth_en": self.auth_en})
        if not self._authorized(req):
            return httpx.Response(401, headers={"WWW-Authenticate": 'Digest qop="auth", realm="shellyplus1-x", '
                                                                    'nonce="123", algorithm=SHA-256'})
        if req.url.path == "/rpc/Switch.GetStatus":
            sid = int(req.url.params.get("id", 0))
            if sid != 0:
                return httpx.Response(500, json={"code": -105, "message": f"Argument 'id', value {sid} not found!"})
            return httpx.Response(200, json={"id": 0, "output": time.monotonic() < self.off_at})
        if req.url.path == "/rpc/Switch.Set":
            body = json.loads(req.content)
            self.off_at = time.monotonic() + body["toggle_after"]
            return httpx.Response(200, json={"was_on": False})
        return httpx.Response(404)


def diag(fake, switch=False, **kw):
    s = Shelly("shelly.test", transport=httpx.MockTransport(fake.handler), **kw)
    return {st.name: st for st in asyncio.run(s.diagnose(switch=switch))}


def test_alles_ok_mit_schalten():
    r = diag(FakeShelly(), switch=True, password="geheim", pulse_seconds=0.2)
    assert r["Erreichbar"].ok and r["Anmeldung"].ok and r["Kanal"].ok and r["Schalten"].ok


def test_falsches_passwort():
    r = diag(FakeShelly(), password="falsch")
    assert r["Anmeldung"].ok is False and "falsch" in r["Anmeldung"].detail


def test_passwort_fehlt():
    r = diag(FakeShelly())
    assert r["Anmeldung"].ok is False and "fehlt" in r["Anmeldung"].detail


def test_falscher_kanal():
    r = diag(FakeShelly(), password="geheim", switch_id=2)
    assert r["Kanal"].ok is False


def test_ohne_passwort_am_shelly_warnt():
    r = diag(FakeShelly(auth_en=False))
    assert r["Anmeldung"].ok is None and r["Kanal"].ok


def test_gen1_und_unerreichbar():
    assert diag(FakeShelly(gen=1))["Gerätegeneration"].ok is False

    def boom(req):
        raise httpx.ConnectError("refused")
    s = Shelly("10.9.9.9", transport=httpx.MockTransport(boom))
    assert asyncio.run(s.diagnose())[0].ok is False
