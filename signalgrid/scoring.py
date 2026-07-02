"""Momentum scoring.

Turns a pile of signals into a single number analysts can sort by. The
model is intentionally simple and fully transparent (no ML, no black box):

    score = sum( severity_weight(signal) * recency_weight(signal) )

- severity_weight: LOW=1, MEDIUM=3, HIGH=7, CRITICAL=15 (roughly exponential,
  so a handful of high-severity signals dominate a pile of low ones -- a
  domain registration matters more than one commit)
- recency_weight: 1.0 at observed_at == now, decaying linearly to 0 at
  `half_life_days`, so old signals fade out of the score automatically
  without ever needing to be deleted from storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

SEVERITY_WEIGHT = {1: 1.0, 2: 3.0, 3: 7.0, 4: 15.0}


@dataclass
class ScoredEntity:
    entity_key: str
    score: float
    signal_count: int
    top_sources: list[str]


def recency_weight(observed_at: datetime, half_life_days: float = 21.0) -> float:
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - observed_at).total_seconds() / 86400
    if age_days <= 0:
        return 1.0
    weight = 1.0 - (age_days / (half_life_days * 2))
    return max(weight, 0.0)


def score_signals(rows: list) -> list[ScoredEntity]:
    """rows: sqlite3.Row objects as returned by Storage.query_signals,
    already filtered to the entities of interest (or all entities)."""
    by_entity: dict[str, list] = {}
    for row in rows:
        by_entity.setdefault(row["entity_key"], []).append(row)

    results = []
    for entity_key, entity_rows in by_entity.items():
        total = 0.0
        sources: dict[str, int] = {}
        for row in entity_rows:
            observed_at = datetime.fromisoformat(row["observed_at"])
            sev_weight = SEVERITY_WEIGHT.get(row["severity"], 1.0)
            total += sev_weight * recency_weight(observed_at)
            sources[row["source"]] = sources.get(row["source"], 0) + 1

        top_sources = sorted(sources, key=sources.get, reverse=True)
        results.append(
            ScoredEntity(
                entity_key=entity_key,
                score=round(total, 2),
                signal_count=len(entity_rows),
                top_sources=top_sources,
            )
        )

    return sorted(results, key=lambda r: r.score, reverse=True)
