# SignalGrid

**Track real-world signals about companies and founders — from GitHub, domain registries, Hacker News, and job boards — in one normalized, queryable stream.**

Built by [Hidden Labs](https://github.com/hidden-labs). SignalGrid is the open-source core of the "Signals" stage in our research pipeline: `Signals → Research → Engineering → Verification → Intelligence`.

```
signalgrid track "Anthropic" --github-org anthropics --domain anthropic.com
signalgrid report "Anthropic"
signalgrid leaderboard
```

## Why

Most "startup discovery" tooling is either a manually-updated spreadsheet or an expensive black-box SaaS. SignalGrid is neither: it's a small, transparent, pluggable Python library and CLI that pulls from real public APIs, normalizes everything into one `Signal` shape, stores it locally (SQLite, zero setup), and scores momentum with a fully auditable formula — no ML, no hidden weighting.

It answers questions like:
- Which companies in my watchlist just had a hiring surge?
- Who registered a new domain in the last 6 months?
- Whose GitHub org just shipped a bunch of new repos?
- Who's suddenly getting talked about on Hacker News?

## Data sources (all real, all free / no-auth-required for basic use)

| Source | API | What it detects |
|---|---|---|
| GitHub | [REST API](https://docs.github.com/en/rest) | New repos, star surges, commit activity, org member growth |
| Domain registries | [RDAP](https://rdap.org) (RFC 9083) | New domain registrations, upcoming expirations |
| Hacker News | [Algolia HN Search](https://hn.algolia.com/api) | Mentions and mention-volume surges |
| Greenhouse job boards | [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html) | New job postings, hiring-volume surges |

GitHub works unauthenticated at 60 req/hour; set `GITHUB_TOKEN` to raise that to 5,000/hour.

## Install

```bash
git clone https://github.com/hidden-labs/signalgrid
cd signalgrid
pip install -e ".[yaml]"
```

Or from PyPI once published: `pip install signalgrid[yaml]`

## Quickstart

Track a single company:

```bash
signalgrid track "Vercel" --github-org vercel --domain vercel.com --greenhouse-token vercel
```

Or track a whole watchlist at once (see `examples/watchlist.yaml`):

```bash
signalgrid track --watchlist examples/watchlist.yaml
```

See what SignalGrid found:

```bash
signalgrid report "Vercel"
signalgrid leaderboard --since-days 30
```

Run continuously (e.g. in a background process / systemd unit / container):

```bash
signalgrid watch --watchlist examples/watchlist.yaml --interval 3600
```

## Use it as a library

```python
from signalgrid.connectors import GitHubConnector, DomainConnector, HackerNewsConnector
from signalgrid.models import Entity
from signalgrid.pipeline import SignalPipeline
from signalgrid.storage import Storage
from signalgrid.scoring import score_signals

entity = Entity(name="Anthropic", github_org="anthropics", domain="anthropic.com")
storage = Storage("signals.db")
pipeline = SignalPipeline(connectors=[GitHubConnector(), DomainConnector(), HackerNewsConnector()], storage=storage)

pipeline.run([entity])
rows = storage.query_signals(entity_key=entity.key)
for scored in score_signals(rows):
    print(scored.entity_key, scored.score)
```

See `examples/track_via_api.py` for a runnable version.

## Architecture

```
Entity  ──▶  Connector.fetch()  ──▶  Signal[]  ──▶  Storage (SQLite, dedup by fingerprint)
                  │                                          │
      github / domain / hackernews / greenhouse       query_signals()
                  │                                          │
            (pluggable, one file each)               scoring.score_signals()
                                                               │
                                                     ranked leaderboard / report
```

- **`signalgrid/models.py`** — `Entity` (thing being tracked) and `Signal` (one observed fact). This is the only contract connectors need to honor.
- **`signalgrid/connectors/`** — one file per data source, each implementing `Connector.fetch(entity) -> list[Signal]`. Failures are isolated: one connector erroring never kills a pipeline run (`Connector.safe_fetch`).
- **`signalgrid/pipeline.py`** — runs all applicable connectors for all entities in parallel (thread pool, since this is network-bound work), persists results.
- **`signalgrid/storage.py`** — SQLite, one `signals` table, deduplicated via a content-based fingerprint so re-running `track` never double-counts.
- **`signalgrid/scoring.py`** — transparent momentum score: `severity_weight × recency_weight`, summed per entity. No ML — every number is explainable.
- **`signalgrid/cli.py`** — `track`, `report`, `leaderboard`, `watch` commands (Click + Rich).

## Adding a new connector

Connectors are the main extension point — see [CONTRIBUTING.md](CONTRIBUTING.md). In short: subclass `Connector`, implement `fetch()`, register it in `signalgrid/connectors/__init__.py`. Good candidates: Crunchbase, PyPI/npm download stats, SEC EDGAR filings, Product Hunt launches, patent filings.

## Roadmap

- [ ] Webhook/Slack/email output for `watch` mode
- [ ] Postgres storage backend for multi-user deployments
- [ ] Additional connectors: PyPI/npm, SEC EDGAR, Product Hunt, LinkedIn job counts
- [ ] `signalgrid export` (CSV/JSON) for feeding into other tools
- [ ] Web dashboard (companion repo)

## License

MIT — see [LICENSE](LICENSE).

---

*SignalGrid is maintained by [Hidden Labs](https://github.com/hidden-labs), a research and engineering company. hello.hiddenlabs@outlook.com*
