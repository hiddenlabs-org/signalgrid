"""Base class every SignalGrid connector implements.

A connector's only job is: given an Entity, return a list of Signals.
Everything else (storage, dedup, scoring, CLI) is connector-agnostic, so
adding a new data source never touches the rest of the codebase.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from signalgrid.models import Entity, Signal

logger = logging.getLogger("signalgrid.connectors")


class Connector(ABC):
    """Subclass this and implement `name` and `fetch`."""

    #: short, stable identifier used as Signal.source and in CLI flags
    name: str = "base"

    @abstractmethod
    def fetch(self, entity: Entity) -> list[Signal]:
        """Return signals observed for this entity. Must not raise on
        expected failure modes (missing field, 404, rate limit) -- log a
        warning and return [] instead, so one flaky source never kills a
        pipeline run across many entities.
        """
        raise NotImplementedError

    def is_applicable(self, entity: Entity) -> bool:
        """Whether this connector has enough info to run for this entity.
        Default: always applicable; override to check required fields."""
        return True

    def safe_fetch(self, entity: Entity) -> list[Signal]:
        if not self.is_applicable(entity):
            logger.debug("%s: skipping %s (missing required field)", self.name, entity.name)
            return []
        try:
            return self.fetch(entity)
        except Exception as exc:  # noqa: BLE001 - connectors must not crash the pipeline
            logger.warning("%s: fetch failed for %s: %s", self.name, entity.name, exc)
            return []
