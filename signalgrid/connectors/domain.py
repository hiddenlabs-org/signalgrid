"""Domain connector.

Uses RDAP (Registration Data Access Protocol, RFC 9083), the modern
successor to WHOIS. `https://rdap.org/domain/{domain}` is a free, public,
unauthenticated bootstrap service maintained for exactly this use case: it
redirects to the correct registry RDAP server for any TLD and returns
structured JSON (no scraping/parsing whois text blobs).

Signals emitted:
  - domain_registered : domain creation date falls inside the lookback window
  - domain_expiring    : domain's expiration event is within 60 days
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Severity, Signal, SignalType

RDAP_ROOT = "https://rdap.org/domain"
DEFAULT_TIMEOUT = 15


class DomainConnector(Connector):
    name = "domain"

    def __init__(self, recent_days: int = 180, expiring_within_days: int = 60):
        self.recent_days = recent_days
        self.expiring_within_days = expiring_within_days

    def is_applicable(self, entity: Entity) -> bool:
        return bool(entity.domain)

    def fetch(self, entity: Entity) -> list[Signal]:
        domain = entity.domain
        resp = requests.get(f"{RDAP_ROOT}/{domain}", timeout=DEFAULT_TIMEOUT, headers={"Accept": "application/rdap+json"})
        if resp.status_code != 200:
            return []

        data = resp.json()
        events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", [])}
        signals: list[Signal] = []
        now_dt = datetime.now(timezone.utc)

        registered = _parse_iso(events.get("registration"))
        if registered and now_dt - registered <= timedelta(days=self.recent_days):
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.DOMAIN_REGISTERED,
                    observed_at=registered,
                    summary=f"Domain '{domain}' registered {registered.date()}",
                    severity=Severity.HIGH,
                    url=f"https://{domain}",
                    raw=data,
                )
            )

        expiration = _parse_iso(events.get("expiration"))
        if expiration and expiration - now_dt <= timedelta(days=self.expiring_within_days):
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.DOMAIN_EXPIRING,
                    observed_at=now_dt,
                    summary=f"Domain '{domain}' expires {expiration.date()}",
                    severity=Severity.MEDIUM,
                    url=f"https://{domain}",
                    raw=data,
                )
            )

        return signals


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
