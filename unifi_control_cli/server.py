"""HTTP adapter exposing the same queries as the CLI over REST.

Zero runtime dependencies — uses only the Python standard library.
This is a thin adapter on top of UnifiClient + slim_{online,offline} +
fuzzy_match. No new query logic lives here.

Endpoints:
    GET /healthz                              -> {"ok": true}
    GET /clients/online?q=...                 -> {mode, query, count, results}
    GET /clients/offline?q=...&within_hours=N -> {mode, query, count, results}

Configuration (in resolution order):
  1. Env vars UNIFI_HOST + UNIFI_API_KEY (+ optional UNIFI_SITE,
     UNIFI_VERIFY_SSL) — wins if both required vars are set.
  2. JSON file at $UNIFI_CONTROL_CONFIG, else
     ~/.config/unifi-control/config.json.

Bind:
    HOST env (default 127.0.0.1)
    PORT env (default 8787)
"""
from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .cli import default_config_path, slim_offline, slim_online, _sort_key
from .client import UnifiClient, UnifiConfig, UnifiError, load_config
from .matcher import fuzzy_match


def _truthy(s: str | None) -> bool:
    return (s or "").strip().lower() in ("1", "true", "yes", "on")


def resolve_config() -> UnifiConfig:
    host = os.environ.get("UNIFI_HOST")
    api_key = os.environ.get("UNIFI_API_KEY")
    if host and api_key:
        return UnifiConfig(
            host=host,
            api_key=api_key,
            site=os.environ.get("UNIFI_SITE", "default"),
            verify_ssl=_truthy(os.environ.get("UNIFI_VERIFY_SSL")),
        )
    return load_config(default_config_path())


class _Handler(BaseHTTPRequestHandler):
    server_version = "unifi-control/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        params = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}

        if url.path == "/healthz":
            return self._send_json(HTTPStatus.OK, {"ok": True})

        if url.path == "/clients/online":
            return self._handle_query("online", params)

        if url.path == "/clients/offline":
            return self._handle_query("offline", params)

        self._send_json(HTTPStatus.NOT_FOUND, {"error": f"unknown path: {url.path}"})

    def _handle_query(self, mode: str, params: dict[str, str]) -> None:
        q = params.get("q", "")
        client: UnifiClient = self.server.unifi_client  # type: ignore[attr-defined]

        try:
            if mode == "online":
                results = [slim_online(c) for c in client.active_clients() if fuzzy_match(c, q)]
            else:
                within_raw = params.get("within_hours", str(24 * 30))
                try:
                    within = int(within_raw)
                except ValueError:
                    return self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": f"within_hours must be an integer, got: {within_raw!r}"},
                    )
                results = [slim_offline(c) for c in client.offline_clients(within)
                           if fuzzy_match(c, q)]
        except UnifiError as e:
            return self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(e)})

        results.sort(key=_sort_key, reverse=True)
        self._send_json(HTTPStatus.OK, {
            "mode": mode, "query": q, "count": len(results), "results": results,
        })


def main(argv: list[str] | None = None) -> int:
    try:
        cfg = resolve_config()
    except UnifiError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))

    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.unifi_client = UnifiClient(cfg)  # type: ignore[attr-defined]
    print(f"unifi-control server listening on http://{host}:{port} "
          f"(controller: {cfg.host}, site: {cfg.site})", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
