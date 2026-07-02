"""Greenhouse connector.

Thousands of companies publish their open roles through Greenhouse's public,
unauthenticated job board API:
  https://boards-api.greenhouse.io/v1/boards/{token}/jobs
`{token}` is the company's Greenhouse board slug -- e.g. for a company that
lists jobs at boards.greenhouse.io/acmeinc, the token is "acmeinc".

Signals emitted:
  - job_posted        : a role opened within the lookback window
  - job_volume_surge  : total open roles crosses a threshold (hiring surge,
                         often correlated with funding events)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Severity, Signal, SignalType

API_ROOT = "https://boards-api.greenhouse.io/v1/boards"
DEFAULT_TIMEOUT = 15


class GreenhouseConnector(Connector):
    name = "greenhouse"

    def __init__(self, recent_days: int = 14, surge_threshold: int = 15):
        self.recent_days = recent_days
        self.surge_threshold = surge_threshold

    def is_applicable(self, entity: Entity) -> bool:
        return bool(entity.greenhouse_token)

    def fetch(self, entity: Entity) -> list[Signal]:
        token = entity.greenhouse_token
        resp = requests.get(f"{API_ROOT}/{token}/jobs", params={"content": "false"}, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            return []

        jobs = resp.json().get("jobs", [])
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.recent_days)
        signals: list[Signal] = []

        for job in jobs:
            updated_at = _parse_iso(job.get("updated_at"))
            if updated_at and updated_at >= cutoff:
                signals.append(
                    Signal(
                        entity_key=entity.key,
                        source=self.name,
                        type=SignalType.JOB_POSTED,
                        observed_at=updated_at,
                        summary=f"Job posted: {job.get('title')} ({_location(job)})",
                        severity=Severity.LOW,
                        url=job.get("absolute_url"),
                        raw=job,
                    )
                )

        if len(jobs) >= self.surge_threshold:
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.JOB_VOLUME_SURGE,
                    observed_at=datetime.now(timezone.utc),
                    summary=f"{len(jobs)} open roles listed for '{token}'",
                    severity=Severity.MEDIUM if len(jobs) < 40 else Severity.HIGH,
                    value=len(jobs),
                )
            )

        return signals


def _location(job: dict) -> str:
    loc = job.get("location") or {}
    return loc.get("name", "unspecified")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
