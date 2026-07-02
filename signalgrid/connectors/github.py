"""GitHub connector.

Uses the real GitHub REST API (https://docs.github.com/en/rest). Works
unauthenticated at 60 requests/hour; set GITHUB_TOKEN in the environment
(or pass token=) to raise that to 5,000/hour and see private-adjacent org
data you have access to.

Signals emitted:
  - repo_created        : org published a new public repo recently
  - repo_starred_surge  : a repo crossed a star-count threshold quickly
  - commit_activity      : recent push activity across org repos
  - org_member_growth    : public member count (best-effort, GitHub does not
                            expose historical counts, so this is a snapshot
                            signal, useful when compared across pipeline runs
                            stored over time)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Severity, Signal, SignalType, now

API_ROOT = "https://api.github.com"
DEFAULT_TIMEOUT = 15


class GitHubConnector(Connector):
    name = "github"

    def __init__(self, token: str | None = None, recent_days: int = 30, star_threshold: int = 100):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.recent_days = recent_days
        self.star_threshold = star_threshold

    def is_applicable(self, entity: Entity) -> bool:
        return bool(entity.github_org)

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "signalgrid"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch(self, entity: Entity) -> list[Signal]:
        org = entity.github_org
        signals: list[Signal] = []
        repos = self._list_org_repos(org)
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.recent_days)

        for repo in repos:
            created_at = _parse_ts(repo.get("created_at"))
            pushed_at = _parse_ts(repo.get("pushed_at"))
            stars = repo.get("stargazers_count", 0) or 0
            full_name = repo.get("full_name", f"{org}/{repo.get('name')}")
            html_url = repo.get("html_url")

            if created_at and created_at >= cutoff:
                signals.append(
                    Signal(
                        entity_key=entity.key,
                        source=self.name,
                        type=SignalType.REPO_CREATED,
                        observed_at=created_at,
                        summary=f"New public repo '{full_name}' created",
                        severity=Severity.LOW,
                        value=1,
                        url=html_url,
                        raw=repo,
                    )
                )

            if stars >= self.star_threshold and pushed_at and pushed_at >= cutoff:
                signals.append(
                    Signal(
                        entity_key=entity.key,
                        source=self.name,
                        type=SignalType.REPO_STARRED_SURGE,
                        observed_at=pushed_at,
                        summary=f"'{full_name}' has {stars} stars and recent activity",
                        severity=Severity.MEDIUM if stars < 1000 else Severity.HIGH,
                        value=stars,
                        url=html_url,
                        raw=repo,
                    )
                )

            if pushed_at and pushed_at >= cutoff:
                signals.append(
                    Signal(
                        entity_key=entity.key,
                        source=self.name,
                        type=SignalType.COMMIT_ACTIVITY,
                        observed_at=pushed_at,
                        summary=f"Push activity on '{full_name}'",
                        severity=Severity.LOW,
                        value=None,
                        url=html_url,
                        raw={"full_name": full_name},
                    )
                )

        member_count = self._public_member_count(org)
        if member_count is not None:
            signals.append(
                Signal(
                    entity_key=entity.key,
                    source=self.name,
                    type=SignalType.ORG_MEMBER_GROWTH,
                    observed_at=now(),
                    summary=f"'{org}' has {member_count} public members",
                    severity=Severity.LOW,
                    value=member_count,
                    url=f"https://github.com/orgs/{org}/people",
                )
            )

        return signals

    def _list_org_repos(self, org: str) -> list[dict]:
        repos: list[dict] = []
        page = 1
        while True:
            resp = requests.get(
                f"{API_ROOT}/orgs/{org}/repos",
                headers=self._headers(),
                params={"per_page": 100, "page": page, "sort": "pushed", "direction": "desc"},
                timeout=DEFAULT_TIMEOUT,
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100 or page >= 3:  # cap at 300 repos per org per run
                break
            page += 1
        return repos

    def _public_member_count(self, org: str) -> int | None:
        resp = requests.get(f"{API_ROOT}/orgs/{org}/public_members", headers=self._headers(), timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            return None
        return len(resp.json())


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
