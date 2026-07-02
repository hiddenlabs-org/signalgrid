"""Example: use SignalGrid as a library instead of the CLI.

Run:
    python examples/track_via_api.py
"""

from signalgrid.connectors import DomainConnector, GitHubConnector, HackerNewsConnector
from signalgrid.models import Entity
from signalgrid.pipeline import SignalPipeline
from signalgrid.scoring import score_signals
from signalgrid.storage import Storage


def main():
    entity = Entity(name="Anthropic", github_org="anthropics", domain="anthropic.com", hn_query="Anthropic")

    storage = Storage("example.db")
    pipeline = SignalPipeline(
        connectors=[GitHubConnector(), DomainConnector(), HackerNewsConnector()],
        storage=storage,
    )

    summary = pipeline.run([entity])
    print(f"New signals stored: {summary}")

    rows = storage.query_signals(entity_key=entity.key)
    for scored in score_signals(rows):
        print(f"{scored.entity_key}: score={scored.score} ({scored.signal_count} signals)")

    storage.close()


if __name__ == "__main__":
    main()
