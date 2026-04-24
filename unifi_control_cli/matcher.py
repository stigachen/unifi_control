"""Fuzzy matching helpers for UniFi client records.

The legacy controller API uses snake_case fields (mac, ip, oui, hostname).
We also accept camelCase variants (macAddress, ipAddress, manufacturer) so
callers who feed us records from the integration v1 API still work.
"""
from __future__ import annotations

from typing import Iterable

# Order matters only for display_name fallback; for fuzzy_match all fields are equal.
MATCH_FIELDS = (
    "name", "hostname", "displayName",
    "manufacturer", "oui",
    "macAddress", "mac",
    "ipAddress", "ip",
)


def _get(client: dict, *keys: str):
    for k in keys:
        v = client.get(k)
        if v:
            return v
    return None


def display_name(client: dict) -> str:
    return (_get(client, "name", "displayName", "hostname", "macAddress", "mac")
            or "<unknown>")


def fuzzy_match(client: dict, query: str, fields: Iterable[str] = MATCH_FIELDS) -> bool:
    """Case-insensitive substring match across the given fields."""
    if not query:
        return True
    q = query.lower()
    return any((v := client.get(f)) and q in str(v).lower() for f in fields)
