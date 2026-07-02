import tempfile
from datetime import datetime, timezone
from pathlib import Path

from signalgrid.connectors.base import Connector
from signalgrid.models import Entity, Signal, SignalType
from signalgrid.pipeline import SignalPipeline
from signalgrid.storage import Storage


class StubConnector(Connector):
    name = "stub"

    def __init__(self, signals):
        self._signals = signals

    def fetch(self, entity: Entity):
        return self._signals


class FailingConnector(Connector):
    name = "failing"

    def fetch(self, entity: Entity):
        raise RuntimeError("simulated API outage")


def _entity():
    return Entity(name="Acme Corp", github_org="acme")


def test_pipeline_persists_signals():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        entity = _entity()
        signal = Signal(
            entity_key=entity.key,
            source="stub",
            type=SignalType.MENTION,
            observed_at=datetime.now(timezone.utc),
            summary="test mention",
        )
        storage = Storage(db_path)
        pipeline = SignalPipeline(connectors=[StubConnector([signal])], storage=storage)

        summary = pipeline.run([entity])

        assert summary[entity.key] == 1
        rows = storage.query_signals(entity_key=entity.key)
        assert len(rows) == 1
        storage.close()


def test_pipeline_dedupes_across_runs():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        entity = _entity()
        signal = Signal(
            entity_key=entity.key,
            source="stub",
            type=SignalType.MENTION,
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            summary="same signal",
        )
        storage = Storage(db_path)
        pipeline = SignalPipeline(connectors=[StubConnector([signal])], storage=storage)

        first = pipeline.run([entity])
        second = pipeline.run([entity])

        assert first[entity.key] == 1
        assert second[entity.key] == 0  # deduped by fingerprint
        storage.close()


def test_pipeline_survives_a_failing_connector():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        entity = _entity()
        good_signal = Signal(
            entity_key=entity.key,
            source="stub",
            type=SignalType.MENTION,
            observed_at=datetime.now(timezone.utc),
            summary="still works",
        )
        storage = Storage(db_path)
        pipeline = SignalPipeline(
            connectors=[FailingConnector(), StubConnector([good_signal])],
            storage=storage,
        )

        summary = pipeline.run([entity])

        assert summary[entity.key] == 1  # the good connector's signal still lands
        storage.close()
