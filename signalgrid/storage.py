"""SQLite-backed storage for signals.

Deliberately boring: one table, fingerprint-based dedup via `INSERT OR
IGNORE`, no ORM. SignalGrid is meant to be embeddable, and SQLite means
`signalgrid track acme` works with zero setup while still giving you a real
queryable history across runs.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from signalgrid.models import Entity, Severity, Signal, SignalType

DEFAULT_DB_PATH = Path.home() / ".signalgrid" / "signalgrid.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    fingerprint TEXT PRIMARY KEY,
    entity_key  TEXT NOT NULL,
    source      TEXT NOT NULL,
    type        TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    summary     TEXT NOT NULL,
    severity    INTEGER NOT NULL,
    value       REAL,
    url         TEXT,
    inserted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_signals_entity ON signals(entity_key);
CREATE INDEX IF NOT EXISTS idx_signals_observed ON signals(observed_at);

CREATE TABLE IF NOT EXISTS entities (
    key             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    github_org      TEXT,
    domain          TEXT,
    greenhouse_token TEXT,
    hn_query        TEXT,
    tags            TEXT
);
"""


class Storage:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- entities -----------------------------------------------------

    def upsert_entity(self, entity: Entity) -> None:
        self._conn.execute(
            """
            INSERT INTO entities (key, name, github_org, domain, greenhouse_token, hn_query, tags)
            VALUES (:key, :name, :github_org, :domain, :greenhouse_token, :hn_query, :tags)
            ON CONFLICT(key) DO UPDATE SET
                name=excluded.name, github_org=excluded.github_org, domain=excluded.domain,
                greenhouse_token=excluded.greenhouse_token, hn_query=excluded.hn_query, tags=excluded.tags
            """,
            {
                "key": entity.key,
                "name": entity.name,
                "github_org": entity.github_org,
                "domain": entity.domain,
                "greenhouse_token": entity.greenhouse_token,
                "hn_query": entity.hn_query,
                "tags": ",".join(entity.tags),
            },
        )
        self._conn.commit()

    def list_entities(self) -> list[Entity]:
        rows = self._conn.execute("SELECT * FROM entities ORDER BY name").fetchall()
        return [
            Entity(
                name=r["name"],
                github_org=r["github_org"],
                domain=r["domain"],
                greenhouse_token=r["greenhouse_token"],
                hn_query=r["hn_query"],
                tags=(r["tags"] or "").split(",") if r["tags"] else [],
            )
            for r in rows
        ]

    # -- signals --------------------------------------------------------

    def save_signals(self, signals: list[Signal]) -> int:
        """Insert signals, ignoring duplicates by fingerprint. Returns the
        number of genuinely new rows inserted."""
        inserted = 0
        for s in signals:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO signals
                    (fingerprint, entity_key, source, type, observed_at, summary, severity, value, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.fingerprint,
                    s.entity_key,
                    s.source,
                    s.type.value if isinstance(s.type, SignalType) else s.type,
                    s.observed_at.isoformat(),
                    s.summary,
                    int(s.severity),
                    s.value,
                    s.url,
                ),
            )
            inserted += cur.rowcount
        self._conn.commit()
        return inserted

    def query_signals(
        self,
        entity_key: str | None = None,
        since: datetime | None = None,
        source: str | None = None,
        min_severity: Severity | int = Severity.LOW,
        limit: int = 200,
    ) -> list[sqlite3.Row]:
        clauses = ["severity >= ?"]
        params: list = [int(min_severity)]
        if entity_key:
            clauses.append("entity_key = ?")
            params.append(entity_key)
        if since:
            clauses.append("observed_at >= ?")
            params.append(since.isoformat())
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = " AND ".join(clauses)
        params.append(limit)
        return self._conn.execute(
            f"SELECT * FROM signals WHERE {where} ORDER BY observed_at DESC LIMIT ?", params
        ).fetchall()

    def entity_keys_with_signals(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT entity_key FROM signals").fetchall()
        return [r["entity_key"] for r in rows]
