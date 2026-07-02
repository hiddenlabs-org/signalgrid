"""Hacker News connector.

Uses the Algolia-powered HN Search API (https://hn.algolia.com/api), which
is free, public, unauthenticated, and the standard way to query HN
programmatically (it's what news.ycombinator.com's own search box uses).

Signals emitted:
  - mention        : a story or comment matching the query, within window
  - mention_surge  : mention volume in the window exceeds a threshold
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Severity, Signal, SignalType

API_ROOT = "https://hn.algolia.com/api/v1/search_by_date"
DEFAULT_TIMEOUT = 15


class HackerNewsConnector(Connector):
    name = "hackernews"

    def __init__(self, lookback_days: int = 14, surge_threshold: int = 5):
        self.lookback_days = lookback_days
        self.surge_threshold = surge_threshold

    def is_applicable(self, entity: Entity) -> bool:
        return bool(entity.hn_query or entity.name)

    def fetch(self, entity: Entity) -> list[Signal]:
        query = entity.hn_query or entity.name
        since = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        resp = requests.get(
            API_ROOT,
            params={
                "query": query,
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
                "hitsPerPage": 100,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        hits = resp.json().get("hits", [])
        signals: list[Signal] = []

        for hit in hits[:20]:  # cap individual mention signals; the rest roll into the surge count
            title = hit.get("title") or (hit.get("comment_text") or "")[:80]
            created = _parse_iso(hit.get("created_at"))
            if not created:
                continue
            object_id = hit.get("objectID")
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.MENTION,
                    observed_at=created,
                    summary=f"HN mention: {title}".strip(),
                    severity=Severity.LOW,
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else None,
                    raw=hit,
                )
            )

        if len(hits) >= self.surge_threshold:
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.MENTION_SURGE,
                    observed_at=datetime.now(timezone.utc),
                    summary=f"{len(hits)} HN mentions of '{query}' in the last {self.lookback_days} days",
                    severity=Severity.MEDIUM if len(hits) < 20 else Severity.HIGH,
                    value=len(hits),
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
