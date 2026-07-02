"""SignalGrid CLI.

    signalgrid track "OpenAI" --github-org openai --domain openai.com
    signalgrid track --watchlist examples/watchlist.yaml
    signalgrid report "OpenAI"
    signalgrid leaderboard
    signalgrid watch --watchlist examples/watchlist.yaml --interval 3600
"""

from __future__ import annotations

import logging
import time

import click
from rich.console import Console
from rich.table import Table

from signalgrid.config import load_entities
from signalgrid.connectors import ALL_CONNECTORS
from signalgrid.models import Entity, Severity
from signalgrid.pipeline import SignalPipeline
from signalgrid.scoring import score_signals
from signalgrid.storage import DEFAULT_DB_PATH, Storage

console = Console()


def _build_pipeline(db_path: str, github_token: str | None) -> tuple[SignalPipeline, Storage]:
    storage = Storage(db_path)
    connectors = []
    for cls in ALL_CONNECTORS:
        if cls.name == "github":
            connectors.append(cls(token=github_token))
        else:
            connectors.append(cls())
    return SignalPipeline(connectors=connectors, storage=storage), storage


@click.group()
@click.option("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database.")
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, db: str, verbose: bool):
    """SignalGrid -- track real-world signals about companies and founders."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@cli.command()
@click.argument("name", required=False)
@click.option("--github-org", default=None, help="GitHub organization login.")
@click.option("--domain", default=None, help="Company domain, e.g. acme.com")
@click.option("--greenhouse-token", default=None, help="Greenhouse job board token/slug.")
@click.option("--hn-query", default=None, help="Custom Hacker News search query (defaults to NAME).")
@click.option("--watchlist", default=None, type=click.Path(exists=True), help="YAML/JSON file of entities to track.")
@click.option("--github-token", default=None, envvar="GITHUB_TOKEN", help="GitHub API token (or set GITHUB_TOKEN).")
@click.pass_context
def track(ctx, name, github_org, domain, greenhouse_token, hn_query, watchlist, github_token):
    """Run every connector once for one entity or a whole watchlist."""
    if watchlist:
        entities = load_entities(watchlist)
    elif name:
        entities = [
            Entity(
                name=name,
                github_org=github_org,
                domain=domain,
                greenhouse_token=greenhouse_token,
                hn_query=hn_query,
            )
        ]
    else:
        raise click.UsageError("Provide either NAME (with --github-org/--domain/...) or --watchlist FILE.")

    pipeline, storage = _build_pipeline(ctx.obj["db"], github_token)
    with console.status(f"[bold blue]Tracking {len(entities)} entit{'y' if len(entities)==1 else 'ies'}..."):
        summary = pipeline.run(entities)
    storage.close()

    table = Table(title="SignalGrid: track results")
    table.add_column("Entity")
    table.add_column("New signals", justify="right")
    for entity in entities:
        table.add_row(entity.name, str(summary.get(entity.key, 0)))
    console.print(table)


@cli.command()
@click.argument("name")
@click.option("--since-days", default=90, help="Only show signals from the last N days.")
@click.option("--min-severity", default=1, type=click.IntRange(1, 4), help="1=low .. 4=critical")
@click.pass_context
def report(ctx, name, since_days, min_severity):
    """Print the signal history and momentum score for one entity."""
    from datetime import datetime, timedelta, timezone

    storage = Storage(ctx.obj["db"])
    key = Entity(name=name).key
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = storage.query_signals(entity_key=key, since=since, min_severity=Severity(min_severity))
    storage.close()

    if not rows:
        console.print(f"[yellow]No signals found for '{name}'. Run `signalgrid track {name!r} ...` first.[/yellow]")
        return

    scored = score_signals(rows)
    score = scored[0].score if scored else 0.0
    console.print(f"[bold]{name}[/bold]  momentum score: [bold green]{score}[/bold green]  ({len(rows)} signals)")

    table = Table()
    table.add_column("Date")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Summary")
    table.add_column("Sev", justify="right")
    for row in rows:
        table.add_row(
            row["observed_at"][:10],
            row["source"],
            row["type"],
            row["summary"],
            str(row["severity"]),
        )
    console.print(table)


@cli.command()
@click.option("--since-days", default=30, help="Score signals from the last N days.")
@click.option("--top", default=20, help="Number of entities to show.")
@click.pass_context
def leaderboard(ctx, since_days, top):
    """Rank all tracked entities by momentum score."""
    from datetime import datetime, timedelta, timezone

    storage = Storage(ctx.obj["db"])
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    rows = storage.query_signals(since=since, limit=5000)
    storage.close()

    if not rows:
        console.print("[yellow]No signals stored yet. Run `signalgrid track ...` first.[/yellow]")
        return

    scored = score_signals(rows)[:top]
    table = Table(title=f"SignalGrid leaderboard (last {since_days}d)")
    table.add_column("#", justify="right")
    table.add_column("Entity")
    table.add_column("Score", justify="right")
    table.add_column("Signals", justify="right")
    table.add_column("Top sources")
    for i, s in enumerate(scored, start=1):
        table.add_row(str(i), s.entity_key, str(s.score), str(s.signal_count), ", ".join(s.top_sources))
    console.print(table)


@cli.command()
@click.option("--watchlist", required=True, type=click.Path(exists=True))
@click.option("--interval", default=3600, help="Seconds between runs.")
@click.option("--github-token", default=None, envvar="GITHUB_TOKEN")
@click.pass_context
def watch(ctx, watchlist, interval, github_token):
    """Run `track` on a watchlist repeatedly, forever, at INTERVAL seconds."""
    entities = load_entities(watchlist)
    pipeline, storage = _build_pipeline(ctx.obj["db"], github_token)
    console.print(f"[bold]Watching {len(entities)} entities every {interval}s. Ctrl+C to stop.[/bold]")
    try:
        while True:
            summary = pipeline.run(entities)
            total_new = sum(summary.values())
            console.print(f"[dim]{time.strftime('%Y-%m-%d %H:%M:%S')}[/dim] — {total_new} new signals across {len(entities)} entities")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    finally:
        storage.close()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
