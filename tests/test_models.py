from datetime import datetime, timezone

from signalgrid.models import Entity, Severity, Signal, SignalType


def test_entity_key_normalization():
    e = Entity(name="Hidden Labs Inc")
    assert e.key == "hidden-labs-inc"


def test_signal_fingerprint_is_stable():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s1 = Signal(entity_key="acme", source="github", type=SignalType.REPO_CREATED, observed_at=ts, summary="x")
    s2 = Signal(entity_key="acme", source="github", type=SignalType.REPO_CREATED, observed_at=ts, summary="x")
    assert s1.fingerprint == s2.fingerprint


def test_signal_fingerprint_differs_on_summary():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s1 = Signal(entity_key="acme", source="github", type=SignalType.REPO_CREATED, observed_at=ts, summary="a")
    s2 = Signal(entity_key="acme", source="github", type=SignalType.REPO_CREATED, observed_at=ts, summary="b")
    assert s1.fingerprint != s2.fingerprint


def test_to_dict_serializes_enum_values():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s = Signal(entity_key="acme", source="domain", type=SignalType.DOMAIN_REGISTERED, observed_at=ts, summary="x", severity=Severity.HIGH)
    d = s.to_dict()
    assert d["type"] == "domain_registered"
    assert d["severity"] == 3
