"""Config loading.

SignalGrid entities can be defined in a small YAML/JSON file so you don't
have to pass a dozen CLI flags per company. See examples/watchlist.yaml.
"""

from __future__ import annotations

import json
from pathlib import Path

from signalgrid.models import Entity


def load_entities(path: str | Path) -> list[Entity]:
    path = Path(path)
    text = path.read_text()

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Reading YAML watchlists requires: pip install pyyaml") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    entities = []
    for item in data.get("entities", []):
        entities.append(
            Entity(
                name=item["name"],
                github_org=item.get("github_org"),
                domain=item.get("domain"),
                greenhouse_token=item.get("greenhouse_token"),
                hn_query=item.get("hn_query"),
                tags=item.get("tags", []),
            )
        )
    return entities
