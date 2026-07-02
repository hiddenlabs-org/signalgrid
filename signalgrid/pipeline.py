"""The pipeline: runs every registered connector against every entity,
collects the resulting signals, and persists them.

This is deliberately a thin orchestration layer -- all the real logic lives
in connectors (data gathering) and storage/scoring (data at rest). Kept
synchronous and simple; parallelizing across connectors/entities via
concurrent.futures.ThreadPoolExecutor is a natural next step (network-bound
work), left as a clean extension point via `max_workers`.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Signal
from signalgrid.storage import Storage

logger = logging.getLogger("signalgrid.pipeline")


class SignalPipeline:
    def __init__(self, connectors: list[Connector], storage: Storage, max_workers: int = 4):
        self.connectors = connectors
        self.storage = storage
        self.max_workers = max_workers

    def run(self, entities: list[Entity]) -> dict[str, int]:
        """Run all connectors against all entities. Returns a summary dict
        of {entity_key: new_signal_count}."""
        summary: dict[str, int] = {}

        for entity in entities:
            self.storage.upsert_entity(entity)
            signals = self._collect_for_entity(entity)
            new_count = self.storage.save_signals(signals)
            summary[entity.key] = new_count
            logger.info("%s: %d signals fetched, %d new", entity.name, len(signals), new_count)

        return summary

    def _collect_for_entity(self, entity: Entity) -> list[Signal]:
        all_signals: list[Signal] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(c.safe_fetch, entity): c for c in self.connectors}
            for future in as_completed(futures):
                connector = futures[future]
                try:
                    all_signals.extend(future.result())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("%s: unexpected error: %s", connector.name, exc)
        return all_signals
