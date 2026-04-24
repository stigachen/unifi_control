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

## Notes

- Read-only. The CLI never issues anything other than GET requests.
- `verify_ssl: false` is the default since UDM ships with a self-signed cert.
- Some clients show `ip: null` in `online` output — usually due to MAC
  randomization / private Wi-Fi address features hiding the device's real
  identity from the controller.
