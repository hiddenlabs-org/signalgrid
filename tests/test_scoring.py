from datetime import datetime, timedelta, timezone

from signalgrid.scoring import recency_weight, score_signals


class FakeRow(dict):
    """Mimics sqlite3.Row's __getitem__ access pattern for tests."""

    def __getitem__(self, key):
        return dict.get(self, key)


def _row(entity_key, source, severity, observed_at):
    return FakeRow(entity_key=entity_key, source=source, severity=severity, observed_at=observed_at.isoformat())


def test_recency_weight_is_1_for_now():
    # observed_at is constructed a few microseconds before recency_weight()
    # calls datetime.now() internally, so allow a tiny tolerance rather than
    # asserting exact float equality.
    assert recency_weight(datetime.now(timezone.utc)) > 0.9999


def test_recency_weight_decays_over_time():
    old = datetime.now(timezone.utc) - timedelta(days=100)
    assert recency_weight(old, half_life_days=21) == 0.0


def test_score_signals_ranks_by_severity_and_recency():
    now = datetime.now(timezone.utc)
    rows = [
        _row("acme", "domain", 3, now),  # high severity, fresh
        _row("beta", "github", 1, now),  # low severity, fresh
    ]
    ranked = score_signals(rows)
    assert ranked[0].entity_key == "acme"
    assert ranked[0].score > ranked[1].score


def test_score_signals_groups_by_entity():
    now = datetime.now(timezone.utc)
    rows = [
        _row("acme", "domain", 2, now),
        _row("acme", "github", 1, now),
        _row("beta", "github", 1, now),
    ]
    ranked = score_signals(rows)
    acme = next(r for r in ranked if r.entity_key == "acme")
    assert acme.signal_count == 2
