"""Command-line interface: `unifi-control online|offline [name]`."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .client import UnifiClient, UnifiError, load_config
from .matcher import display_name, fuzzy_match


def _g(c: dict, *keys):
    for k in keys:
        v = c.get(k)
        if v not in (None, ""):
            return v
    return None


def _local_time(ts) -> str | None:
    """Convert a Unix epoch (int/float/str) or ISO-8601 string to a local-time
    'YYYY-MM-DD HH:MM:SS+ZZZZ' string. Returns None for falsy/unparseable input."""
    if ts in (None, "", 0):
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
        except (OSError, ValueError):
            return None
    if isinstance(ts, str):
        try:
            return (datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    .astimezone().strftime("%Y-%m-%d %H:%M:%S%z"))
        except ValueError:
            return None
    return None


def slim_online(c: dict) -> dict:
    last_seen = _g(c, "last_seen")
    first_seen = _g(c, "first_seen")
    assoc_time = _g(c, "assoc_time")  # WiFi association time (epoch sec)
    return {
        "name": display_name(c),
        "hostname": _g(c, "hostname"),
        "ip": _g(c, "ip", "fixed_ip"),
        "mac": _g(c, "mac"),
        "vendor": _g(c, "oui"),
        "is_wired": _g(c, "is_wired"),
        "is_guest": _g(c, "is_guest"),
        "ssid": _g(c, "essid"),
        "ap_mac": _g(c, "ap_mac"),
        "ap_name": _g(c, "last_uplink_name"),
        "radio": _g(c, "radio"),
        "channel": _g(c, "channel"),
        "signal_dbm": _g(c, "signal"),
        "rx_rate_kbps": _g(c, "rx_rate"),
        "tx_rate_kbps": _g(c, "tx_rate"),
        "rx_bytes": _g(c, "rx_bytes"),
        "tx_bytes": _g(c, "tx_bytes"),
        "uptime_sec": _g(c, "uptime"),
        "network": _g(c, "network"),
        "first_seen": first_seen,
        "first_seen_local": _local_time(first_seen),
        "assoc_time": assoc_time,
        "assoc_time_local": _local_time(assoc_time),
        "last_seen": last_seen,
        "last_seen_local": _local_time(last_seen),
    }


def slim_offline(c: dict) -> dict:
    last_seen = _g(c, "lastSeenAt", "last_seen")
    disconnected_at = _g(c, "disconnect_timestamp")
    first_seen = _g(c, "firstSeenAt", "first_seen")
    return {
        "name": display_name(c),
        "hostname": _g(c, "hostname"),
        "mac": _g(c, "macAddress", "mac"),
        "vendor": _g(c, "manufacturer", "oui"),
        "last_ip": _g(c, "lastIpAddress", "last_ip", "ipAddress", "ip"),
        "last_seen": last_seen,
        "last_seen_local": _local_time(last_seen),
        "disconnected_at": disconnected_at,
        "disconnected_at_local": _local_time(disconnected_at),
        "first_seen": first_seen,
        "first_seen_local": _local_time(first_seen),
        "is_wired": _g(c, "isWired", "is_wired"),
        "last_network": _g(c, "last_connection_network_name"),
        "last_uplink": _g(c, "last_uplink_name"),
        "is_guest": _g(c, "isGuest", "is_guest"),
    }


def default_config_path() -> Path:
    env = os.environ.get("UNIFI_CONTROL_CONFIG")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "unifi-control" / "config.json"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="unifi-control", description="Query UniFi clients by fuzzy name")
    p.add_argument("mode", choices=["online", "offline"],
                   help="online = active clients; offline = known but disconnected")
    p.add_argument("name", nargs="?", default="", help="fuzzy substring match (optional)")
    p.add_argument("--config", type=Path, default=None,
                   help=f"path to config.json (default: $UNIFI_CONTROL_CONFIG or {default_config_path()})")
    p.add_argument("--within-hours", type=int, default=24 * 30,
                   help="offline mode: lookback window in hours (default: 720 = 30 days)")
    return p


def _sort_key(record: dict):
    v = record.get("last_seen") or record.get("connected_at") or 0
    if isinstance(v, str):
        return v
    return v or 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = args.config or default_config_path()

    try:
        cfg = load_config(config_path)
        client = UnifiClient(cfg)
        if args.mode == "online":
            results = [slim_online(c) for c in client.active_clients() if fuzzy_match(c, args.name)]
        else:
            results = [slim_offline(c) for c in client.offline_clients(args.within_hours)
                       if fuzzy_match(c, args.name)]
    except UnifiError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    results.sort(key=_sort_key, reverse=True)
    print(json.dumps(
        {"mode": args.mode, "query": args.name, "count": len(results), "results": results},
        indent=2, ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
