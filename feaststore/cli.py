"""``feaststore`` command-line interface.

Loads a feature repo (a Python module that defines FeatureView objects), applies
it to the registry, and drives materialization -- the day-to-day operator verbs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from feaststore import __version__
from feaststore.definitions import FeatureView
from feaststore.store import FeatureStore

app = typer.Typer(add_completion=False, help="feaststore feature store CLI")
console = Console()


def _load_feature_views(repo_path: Path) -> list[FeatureView]:
    """Import a feature repo module and collect module-level FeatureView objects."""
    if not repo_path.exists():
        raise typer.BadParameter(f"feature repo not found: {repo_path}")

    spec = importlib.util.spec_from_file_location("feature_repo", repo_path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"cannot import feature repo: {repo_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["feature_repo"] = module
    spec.loader.exec_module(module)

    views = [obj for obj in vars(module).values() if isinstance(obj, FeatureView)]
    if not views:
        console.print("[yellow]warning:[/] no FeatureView objects found in repo")
    return views


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"feaststore {__version__}")


@app.command()
def apply(
    repo: Path = typer.Argument(..., help="Path to a feature repo .py file"),
) -> None:
    """Register the feature views defined in REPO."""
    views = _load_feature_views(repo)
    store = FeatureStore()
    store.apply(views)
    console.print(f"[green]applied[/] {len(views)} feature view(s)")


@app.command(name="list")
def list_views() -> None:
    """List registered feature views."""
    store = FeatureStore()
    views = store.list_feature_views()
    if not views:
        console.print("no feature views registered")
        return
    table = Table(title="feature views")
    table.add_column("name", style="cyan")
    table.add_column("entities")
    table.add_column("features")
    table.add_column("ttl")
    for v in views:
        ttl = f"{int(v.ttl.total_seconds())}s" if v.ttl else "-"
        table.add_row(v.name, ", ".join(v.join_keys), str(len(v.features)), ttl)
    console.print(table)


@app.command()
def materialize(
    view: list[str] = typer.Option(None, "--view", help="Restrict to these views"),
) -> None:
    """Materialize the latest offline rows into the online store."""
    store = FeatureStore()
    results = store.materialize(view_names=view or None)
    for r in results:
        console.print(
            f"[green]{r.feature_view}[/]: wrote {r.rows_written} rows in {r.duration_seconds:.2f}s"
        )


@app.command()
def export() -> None:
    """Dump the registry as JSON to stdout."""
    store = FeatureStore()
    console.print_json(store.registry.dump())


if __name__ == "__main__":
    app()
