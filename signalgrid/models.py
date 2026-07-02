"""Core data models for SignalGrid.

A `Signal` is the atomic unit SignalGrid deals with: one observed fact about
an entity (a company, a domain, a person) coming from one source, at one
point in time. Connectors produce signals; the pipeline collects, dedupes,
stores and scores them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SignalType(str, Enum):
    """The kinds of signals SignalGrid understands out of the box.

    Connectors are free to emit new values here (SignalType is just a str),
    but keeping to a shared vocabulary makes cross-source scoring possible.
    """

    REPO_CREATED = "repo_created"
    REPO_STARRED_SURGE = "repo_starred_surge"
    COMMIT_ACTIVITY = "commit_activity"
    NEW_CONTRIBUTOR = "new_contributor"
    ORG_MEMBER_GROWTH = "org_member_growth"

    DOMAIN_REGISTERED = "domain_registered"
    DOMAIN_RENEWED = "domain_renewed"
    DOMAIN_EXPIRING = "domain_expiring"

    JOB_POSTED = "job_posted"
    JOB_VOLUME_SURGE = "job_volume_surge"

    MENTION = "mention"
    MENTION_SURGE = "mention_surge"


class Severity(int, Enum):
    """Rough signal strength, used by the scoring engine."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Entity:
    """The thing being tracked -- typically a company, identified by
    whichever handles are known about it. Any field may be blank; connectors
    only use the fields they need.
    """

    name: str
    github_org: Optional[str] = None
    domain: Optional[str] = None
    greenhouse_token: Optional[str] = None
    hn_query: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.name.strip().lower().replace(" ", "-")


@dataclass
class Signal:
    """One observed, timestamped fact about an entity from one source."""

    entity_key: str
    source: str  # connector name, e.g. "github", "domain", "hackernews"
    type: SignalType
    observed_at: datetime
    summary: str
    severity: Severity = Severity.LOW
    value: Optional[float] = None  # numeric payload, e.g. star count delta
    url: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Stable id used for deduplication in storage.

        Built from everything that makes a signal *this* signal, so the same
        underlying event fetched twice (e.g. two pipeline runs on the same
        day) collapses to one stored row instead of duplicating.
        """
        basis = f"{self.entity_key}|{self.source}|{self.type}|{self.summary}|{self.observed_at.date()}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "entity_key": self.entity_key,
            "source": self.source,
            "type": self.type.value if isinstance(self.type, SignalType) else self.type,
            "observed_at": self.observed_at.isoformat(),
            "summary": self.summary,
            "severity": int(self.severity),
            "value": self.value,
            "url": self.url,
        }


def now() -> datetime:
    return datetime.now(timezone.utc)
