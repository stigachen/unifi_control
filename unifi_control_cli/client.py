"""UniFi Network controller HTTP client (legacy controller API, API-key auth).

Although UniFi OS 9.0.108+ ships an "integration v1" API, its endpoints expose
very few fields (no signal/SSID/uptime/AP info), so this client uses the
**legacy controller API** under /proxy/network/api/s/{site}/... — those
endpoints accept the same X-API-KEY header on UniFi OS, so no extra
credentials are needed.

Generate the key in the UniFi OS Console under:
    Settings -> Control Plane -> Integrations -> Create API Key

Zero runtime dependencies — uses only the Python standard library.
"""
from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


class UnifiError(RuntimeError):
    """Raised on non-2xx API responses or transport errors."""


@dataclass
class UnifiConfig:
    host: str
    api_key: str
    site: str = "default"
    verify_ssl: bool = False

    def __post_init__(self) -> None:
        self.host = self.host.rstrip("/")


def load_config(path: str | Path) -> UnifiConfig:
    p = Path(path).expanduser()
    if not p.exists():
        raise UnifiError(f"config not found: {p}")
    data = json.loads(p.read_text())
    missing = [k for k in ("host", "api_key") if not data.get(k)]
    if missing:
        raise UnifiError(f"config missing required fields: {', '.join(missing)}")
    return UnifiConfig(**data)


class UnifiClient:
    """Stateless UniFi Network legacy-API client."""

    BASE = "/proxy/network/api"

    def __init__(self, config: UnifiConfig, timeout: int = 20) -> None:
        self.cfg = config
        self.timeout = timeout
        self._opener = self._build_opener()

    def _build_opener(self) -> urlrequest.OpenerDirector:
        handlers: list = []
        if not self.cfg.verify_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            handlers.append(urlrequest.HTTPSHandler(context=ctx))
        return urlrequest.build_opener(*handlers)

    def _get(self, path: str) -> list[dict]:
        url = f"{self.cfg.host}{self.BASE}/s/{self.cfg.site}{path}"
        headers = {"Accept": "application/json", "X-API-KEY": self.cfg.api_key}
        req = urlrequest.Request(url, method="GET", headers=headers)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
        except HTTPError as e:
            msg = e.read().decode("utf-8", errors="replace")[:300]
            hint = " (check api_key in config)" if e.code == 401 else ""
            raise UnifiError(f"GET {url} -> HTTP {e.code}{hint}: {msg}") from e
        except URLError as e:
            raise UnifiError(f"GET {url} -> {e.reason}") from e
        return payload.get("data", [])

    def active_clients(self) -> list[dict]:
        """Currently connected clients (wireless + wired)."""
        return self._get("/stat/sta")

    def all_known_clients(self, within_hours: int = 24 * 30) -> list[dict]:
        """All known clients including disconnected ones, within the lookback
        window (default 30 days; the controller prunes older records anyway)."""
        return self._get(f"/stat/alluser?type=all&conn=all&within={within_hours}")

    def offline_clients(self, within_hours: int = 24 * 30) -> list[dict]:
        """Known clients that are not currently connected."""
        active_macs = {(c.get("mac") or "").lower() for c in self.active_clients()}
        return [c for c in self.all_known_clients(within_hours)
                if (c.get("mac") or "").lower() not in active_macs]
