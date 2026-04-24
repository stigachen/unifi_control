# unifi-control

Lightweight Python client + CLI for querying a self-hosted UniFi Network controller
(UDM, UDM-Pro, Cloud Key Gen2+) for client devices, with fuzzy name matching.

Uses the legacy controller API under `/proxy/network/api/s/{site}/...` with
**API-key authentication** — no username/password, no cookie/CSRF dance, no
extra detail-endpoint round-trips. The integration v1 API exposes too few
fields (no signal/SSID/AP/uptime), so we don't use it.

Zero runtime dependencies — uses only the Python standard library.

## Install

```bash
pip install -e .
```

## Generate an API key

In the UniFi OS Console (your UDM web UI):

1. Open **Settings → Control Plane → Integrations**.
2. Click **Create API Key**, give it a name, copy the value once (it won't be shown again).

The key is local to that console.

## Configure

```bash
mkdir -p ~/.config/unifi-control
cp config.example.json ~/.config/unifi-control/config.json
chmod 600 ~/.config/unifi-control/config.json
$EDITOR ~/.config/unifi-control/config.json
```

Or set `UNIFI_CONTROL_CONFIG=/some/path/config.json` to point elsewhere.

```json
{
  "host": "https://192.168.1.1",
  "api_key": "your-unifi-api-key-here",
  "site": "default",
  "verify_ssl": false
}
```

`site` is the legacy site name (typically `default`); it's the segment that
appears in the controller URL `/manage/site/<name>/...`.

## Use as a CLI

```bash
# online clients matching "iphone" (case-insensitive substring on
# name / hostname / vendor / mac / ip)
unifi-control online iphone

# all online clients (no name filter)
unifi-control online

# offline / known-but-disconnected clients in the past 30 days
unifi-control offline laptop

# extend the offline lookback window to 90 days
unifi-control offline --within-hours 2160
```

Output is JSON on stdout. Timestamps are returned both as Unix epoch seconds
(`last_seen`, `disconnected_at`, ...) and as a human-readable local-time string
(`last_seen_local`, `disconnected_at_local`, ...).

## Use as a library

```python
from unifi_control_cli import UnifiClient, load_config, fuzzy_match

client = UnifiClient(load_config("~/.config/unifi-control/config.json"))
for c in client.active_clients():
    if fuzzy_match(c, "iphone"):
        print(c.get("hostname"), c.get("ip"), c.get("signal"))
```

## Run as a Docker service

The package also ships an HTTP server (`unifi-control-server`) that wraps the
same queries behind a small JSON REST API. Zero runtime deps — just stdlib
`http.server`.

### Quickstart with docker compose

Pre-built multi-arch images (amd64 + arm64) are published at
[`stigachen/unifi-control`](https://hub.docker.com/r/stigachen/unifi-control)
on Docker Hub.

```bash
cat > .env <<EOF
UNIFI_HOST=https://192.168.1.1
UNIFI_API_KEY=your-unifi-api-key-here
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
EOF

# Pull from Docker Hub (no local build needed):
docker run -d --name unifi-control --restart unless-stopped \
  -p 8787:8787 --env-file .env \
  stigachen/unifi-control:latest

# Or with the bundled compose file (also works without a local checkout —
# it builds from source by default; edit `image:` / remove `build:` to pull instead):
docker compose up -d --build
```

The compose file binds the container to `0.0.0.0:8787` — reachable from
other devices on the LAN at `http://<this-machine-lan-ip>:8787`. Change to
`127.0.0.1:8787:8787` in `docker-compose.yml` if you want loopback only.

> Note: the server has **no authentication**. Anyone on the same network
> can query your client list. Fine for a trusted home LAN; if you're on a
> shared/office network or want to expose this further, add a reverse
> proxy with auth in front of it.

### Endpoints

```bash
curl -s 'http://127.0.0.1:8787/healthz'
curl -s 'http://127.0.0.1:8787/clients/online?q=iphone'
curl -s 'http://127.0.0.1:8787/clients/offline?q=laptop&within_hours=2160'
```

Response shape matches the CLI: `{"mode", "query", "count", "results": [...]}`.

### Configuration

Resolved in this order:

1. Env vars `UNIFI_HOST` + `UNIFI_API_KEY` (and optional `UNIFI_SITE`,
   `UNIFI_VERIFY_SSL`) — wins if both required vars are set.
2. JSON file at `$UNIFI_CONTROL_CONFIG`, else
   `~/.config/unifi-control/config.json` (mount it into the container at
   that path or override the env var — see the commented `volumes` block in
   `docker-compose.yml`).

`HOST` / `PORT` env vars control the bind address inside the container
(defaults `0.0.0.0:8787`). The server is read-only — no write endpoints,
same invariant as the CLI.

## Notes

- Read-only. The CLI never issues anything other than GET requests.
- `verify_ssl: false` is the default since UDM ships with a self-signed cert.
- Some clients show `ip: null` in `online` output — usually due to MAC
  randomization / private Wi-Fi address features hiding the device's real
  identity from the controller.
