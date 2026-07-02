# Contributing to SignalGrid

Thanks for considering a contribution. SignalGrid is intentionally small
and plugin-shaped — most contributions fall into one of two buckets.

## Adding a new connector

This is the easiest, highest-value contribution. A connector is one file:

1. Create `signalgrid/connectors/your_source.py`.
2. Subclass `Connector` (see `signalgrid/connectors/base.py`).
3. Implement `name` and `fetch(self, entity) -> list[Signal]`.
4. Override `is_applicable(entity)` if your connector needs specific
   `Entity` fields to run.
5. Register it in `signalgrid/connectors/__init__.py`'s `ALL_CONNECTORS`.
6. Add tests in `tests/` (mock the HTTP calls — see `tests/test_pipeline.py`
   for the `StubConnector` pattern; for real-HTTP connectors, use the
   `responses` library, already in `dev` extras).

Good connector candidates: Crunchbase, LinkedIn job counts, PyPI/npm
download stats, patent filings, SEC EDGAR filings, Product Hunt launches,
G2/Capterra review velocity, BuiltWith tech-stack changes.

## Fixing bugs / improving core

Core pieces are `models.py`, `pipeline.py`, `storage.py`, `scoring.py`,
`cli.py`. Keep changes backward compatible with the `Signal`/`Entity`
data model where possible — connectors depend on it.

## Development setup

```bash
git clone https://github.com/hidden-labs/signalgrid
cd signalgrid
pip install -e ".[dev,yaml]"
pytest
ruff check signalgrid tests
mypy signalgrid
```

## Pull requests

- Keep PRs focused (one connector or one fix per PR).
- Include tests — untested connectors won't be merged.
- Run `ruff check` and `pytest` locally before opening the PR.
