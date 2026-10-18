"""Shelly Gen2/Gen3/Gen4: Ausgang für 1 s einschalten (Impuls an den Öffnungseingang des Motorschlosses)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass
class Step:
    name: str
    ok: bool | None          # True = ok, False = Fehler, None = Hinweis/übersprungen
    detail: str = ""


class Shelly:
    def __init__(self, host: str, password: str = "", switch_id: int = 0, pulse_seconds: float = 1.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.host, self.switch_id = host, switch_id
        self.pulse_seconds = max(0.2, min(float(pulse_seconds), 10.0))
        auth = httpx.DigestAuth("admin", password) if password else None
        self._transport = transport          # nur für Tests
        self.client = httpx.AsyncClient(auth=auth, timeout=5, transport=transport)

    async def pulse(self, seconds: float | None = None) -> bool:
        """Schaltet ein und lässt den Shelly selbst nach `seconds` wieder ausschalten (toggle_after läuft
        auf dem Shelly, das Relais fällt also auch ab, wenn HA danach abstürzt oder das WLAN weg ist)."""
        seconds = self.pulse_seconds if seconds is None else seconds
        if not self.host:
            log.error("Kein Shelly konfiguriert")
            return False
        try:
            r = await self.client.post(f"http://{self.host}/rpc/Switch.Set",
                                       json={"id": self.switch_id, "on": True, "toggle_after": seconds})
            r.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001
            log.error("Shelly %s nicht erreichbar: %s", self.host, e)
            return False

    async def diagnose(self, switch: bool = False) -> list[Step]:
        """Prüft Schritt für Schritt: erreichbar, Gerät, Anmeldung, Kanal und optional echtes Schalten."""
        steps: list[Step] = []
        if not self.host:
            return [Step("Adresse", False, "shelly_host ist in der Add-on-Konfiguration leer")]
        base = f"http://{self.host}"
        plain = httpx.AsyncClient(timeout=4, transport=self._transport)
        # 1. erreichbar + Geräteinfo (/shelly braucht nie eine Anmeldung)
        try:
            r = await plain.get(f"{base}/shelly")
            r.raise_for_status()
            info = r.json()
        except httpx.ConnectError:
            return [Step("Erreichbar", False, f"keine Verbindung zu {self.host} – IP/Netz/VLAN-Regel prüfen")]
        except httpx.TimeoutException:
            return [Step("Erreichbar", False, f"{self.host} antwortet nicht (Zeitüberschreitung)")]
        except Exception as e:  # noqa: BLE001
            return [Step("Erreichbar", False, f"{self.host}: {e}")]
        finally:
            await plain.aclose()
        gen = int(info.get("gen") or 1)
        model = info.get("model") or info.get("type") or "?"
        steps.append(Step("Erreichbar", True, f"{info.get('name') or info.get('id') or model} – Modell {model}, "
                                              f"Firmware {info.get('ver') or info.get('fw') or '?'}"))
        if gen < 2:
            steps.append(Step("Gerätegeneration", False, "Gen1-Shelly wird nicht unterstützt (nötig: Gen2 oder neuer)"))
            return steps
        steps.append(Step("Gerätegeneration", True, f"Gen{gen}"))
        # 2. Anmeldung
        auth_en = bool(info.get("auth_en"))
        if not auth_en:
            steps.append(Step("Anmeldung", None, "Shelly hat KEIN Passwort – bitte in der Shelly-App setzen "
                                                 "(Einstellungen → Authentifizierung)"))
        try:
            r = await self.client.get(f"{base}/rpc/Switch.GetStatus", params={"id": self.switch_id})
        except Exception as e:  # noqa: BLE001
            steps.append(Step("Anmeldung", False, f"Abfrage fehlgeschlagen: {e}"))
            return steps
        if r.status_code == 401:
            steps.append(Step("Anmeldung", False, "Passwort fehlt in der Konfiguration (shelly_password)"
                              if not self.client.auth else "Passwort falsch (Benutzer ist immer „admin“)"))
            return steps
        if auth_en:
            steps.append(Step("Anmeldung", True, "Passwort korrekt"))
        # 3. Kanal
        if r.status_code != 200:
            msg = ""
            try:
                msg = r.json().get("message", "")
            except ValueError:
                pass
            steps.append(Step("Kanal", False, f"Kanal {self.switch_id} gibt es nicht ({msg or r.status_code}). "
                                              "Bei 1-Kanal-Geräten 0 nehmen."))
            return steps
        st = r.json()
        steps.append(Step("Kanal", True, f"Kanal {self.switch_id}: Relais ist {'AN' if st.get('output') else 'aus'}"))
        if st.get("output"):
            steps.append(Step("Ruhezustand", False, "Relais ist gerade eingeschaltet – im Normalfall muss es aus sein"))
        # 4. Schalten
        if not switch:
            steps.append(Step("Schalten", None, "nicht getestet (Knopf „… und schalten“ öffnet die Tür)"))
            return steps
        if not await self.pulse():
            steps.append(Step("Schalten", False, "Schaltbefehl abgelehnt (siehe Add-on-Protokoll)"))
            return steps
        await asyncio.sleep(0.15)
        on = (await self.client.get(f"{base}/rpc/Switch.GetStatus", params={"id": self.switch_id})).json()
        await asyncio.sleep(self.pulse_seconds + 0.6)
        off = (await self.client.get(f"{base}/rpc/Switch.GetStatus", params={"id": self.switch_id})).json()
        if on.get("output") and not off.get("output"):
            steps.append(Step("Schalten", True, f"Relais ging an und nach {self.pulse_seconds:g} s wieder aus"))
        elif not on.get("output"):
            steps.append(Step("Schalten", False, "Befehl angenommen, aber Relais ging nicht an"))
        else:
            steps.append(Step("Schalten", False, "Relais ist nach dem Impuls noch an – Shelly-Einstellungen prüfen"))
        return steps
