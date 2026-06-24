"""Typer CLI for VBU-Projects-Agent."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .orchestrator import Orchestrator

app = typer.Typer(
    name="vbu-agent",
    help="VBU Delivery Manager agentic solution for project context and executive reporting.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
project_app = typer.Typer(help="Per-project commands.", no_args_is_help=True)
dashboard_app = typer.Typer(help="Portfolio dashboard commands.", no_args_is_help=True)
history_app = typer.Typer(help="History and export commands.", no_args_is_help=True)
portfolio_app = typer.Typer(help="Cross-portfolio commands.", no_args_is_help=True)

app.add_typer(project_app, name="project")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(history_app, name="history")
app.add_typer(portfolio_app, name="portfolio")

console = Console()

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_BASE_DIR: Optional[Path] = None
_CONFIG_PATH: Optional[Path] = None
_VERBOSE: bool = False


def _orchestrator() -> Orchestrator:
    base = _BASE_DIR or Path.cwd()
    return Orchestrator(base_dir=base, config_path=_CONFIG_PATH)


@app.callback()
def main_callback(
    config: Annotated[Optional[Path], typer.Option("--config", help="Path to vbu-agent.yaml")] = None,
    base_dir: Annotated[Optional[Path], typer.Option("--base-dir", help="Workspace root")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q")] = False,
) -> None:
    global _BASE_DIR, _CONFIG_PATH, _VERBOSE
    _BASE_DIR = base_dir
    _CONFIG_PATH = config
    _VERBOSE = verbose

    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Root commands
# ---------------------------------------------------------------------------

@app.command("init")
def cmd_init(force: bool = typer.Option(False, "--force", help="Overwrite existing files")) -> None:
    """Scaffold the workspace directory structure."""
    orch = _orchestrator()
    orch.init(force=force)
    console.print("[green]✓[/green] Workspace initialized.")


@app.command("doctor")
def cmd_doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    """Diagnose environment, providers, ADO reachability, paths."""
    orch = _orchestrator()
    results = orch.doctor()
    if json_output:
        typer.echo(json.dumps(results, indent=2))
        return
    table = Table(title="VBU Agent Diagnostics", show_header=True)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status")
    for k, v in results.items():
        color = "green" if v.startswith("OK") else ("yellow" if v.startswith("WARN") else "red")
        table.add_row(k, f"[{color}]{v}[/{color}]")
    console.print(table)


# ---------------------------------------------------------------------------
# Config commands
# ---------------------------------------------------------------------------
config_app = typer.Typer(help="Configuration commands.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("validate")
def cmd_config_validate() -> None:
    """Validate the global config file. Exits non-zero on error."""
    from .config.loader import load_global_config, validate_global_config
    base = _BASE_DIR or Path.cwd()
    cfg_path = _CONFIG_PATH or base / "config" / "vbu-agent.yaml"
    try:
        cfg = load_global_config(cfg_path, base_dir=base)
        issues = validate_global_config(cfg, base)
        if issues:
            for issue in issues:
                console.print(f"[yellow]{issue}[/yellow]")
        else:
            console.print("[green]✓[/green] Config is valid.")
    except Exception as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

@project_app.command("create")
def cmd_project_create(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (folder name)"),
    name: str = typer.Option(..., "--name", "-n", help="Human-readable project name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Scaffold a new project folder with project.yaml and empty context files."""
    from .projects.scaffolder import ProjectScaffolder
    orch = _orchestrator()
    scaffolder = ProjectScaffolder(orch.base_dir / orch.cfg.projects.root_path)
    try:
        project_dir = scaffolder.create(project, name, force=force)
        console.print(f"[green]✓[/green] Project created at {project_dir}")
        console.print(f"  Next: fill in [bold]{project_dir}/project.yaml[/bold] then run:")
        console.print(f"    vbu-agent project validate --project {project}")
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@project_app.command("list")
def cmd_project_list(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all projects with current health and last-update."""
    orch = _orchestrator()
    projects = orch.project_list()
    if json_output:
        typer.echo(json.dumps(projects, indent=2, default=str))
        return
    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Health")
    table.add_column("Last Updated")
    for p in projects:
        health = p.get("current_health") or "unknown"
        color = {"green": "green", "yellow": "yellow", "red": "red"}.get(health, "white")
        table.add_row(
            p.get("id", ""),
            p.get("name", ""),
            f"[{color}]{health}[/{color}]",
            (p.get("last_updated_at") or "—")[:10],
        )
    console.print(table)


@project_app.command("validate")
def cmd_project_validate(
    project: str = typer.Option(..., "--project", "-p"),
) -> None:
    """Validate a project's project.yaml and context integrity."""
    orch = _orchestrator()
    try:
        project_dir, pcfg = orch._load_project(project)
        from .projects.context_manager import ContextManager
        ctx_mgr = ContextManager(project_dir / "context")
        issues = ctx_mgr.verify_integrity()
        if issues:
            for issue in issues:
                console.print(f"[yellow]WARN:[/yellow] {issue}")
        else:
            console.print(f"[green]✓[/green] Project '{project}' config and context are valid.")
    except Exception as e:
        console.print(f"[red]Validation error:[/red] {e}")
        raise typer.Exit(1)


@project_app.command("update")
def cmd_project_update(
    project: str = typer.Option(..., "--project", "-p"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
    review_required: bool = typer.Option(False, "--review-required", help="Require approval before applying"),
) -> None:
    """Ingest input files and update context (the core daily workflow)."""
    orch = _orchestrator()
    try:
        result = orch.project_update(project, dry_run=dry_run, review_required=review_required)
        mode = "[yellow][DRY RUN][/yellow] " if dry_run else ""
        if result.get("skipped"):
            console.print(f"{mode}[dim]Skipped:[/dim] {result.get('skipped_reason', 'no input')}")
        else:
            console.print(f"{mode}[green]✓[/green] Update complete (run_id: {result['run_id']})")
            console.print(f"  Changes applied: {len(result.get('changes', []))}")
            console.print(f"  Conflicts detected: {result.get('conflicts', 0)}")
        if _VERBOSE:
            console.print(result.get("change_summary", ""))
    except Exception as e:
        console.print(f"[red]Update failed:[/red] {e}")
        raise typer.Exit(1)


@project_app.command("sync-ado")
def cmd_project_sync_ado(
    project: str = typer.Option(..., "--project", "-p"),
    no_cache: bool = typer.Option(False, "--no-cache"),
) -> None:
    """Pull latest metrics from Azure DevOps."""
    orch = _orchestrator()
    try:
        result = orch.project_sync_ado(project, no_cache=no_cache)
        console.print(f"[green]✓[/green] ADO sync complete.")
        console.print(f"  Health: {result.get('health', '?')}")
        console.print(f"  Progress: {float(result.get('overall_percent', 0) or 0) * 100:.1f}%")
    except Exception as e:
        console.print(f"[red]ADO sync failed:[/red] {e}")
        raise typer.Exit(1)


@project_app.command("status")
def cmd_project_status(
    project: str = typer.Option(..., "--project", "-p"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Print current computed status (no generation)."""
    orch = _orchestrator()
    result = orch.project_status(project)
    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
        return
    if "error" in result:
        console.print(f"[yellow]{result['error']}[/yellow]")
        return
    health = result.get("health", "unknown")
    color = {"green": "green", "yellow": "yellow", "red": "red"}.get(health, "white")
    console.print(f"Project: [bold]{project}[/bold]")
    console.print(f"Health: [{color}]{health.upper()}[/{color}]")
    console.print(f"Progress: {float(result.get('overall_percent', 0) or 0) * 100:.1f}%")
    console.print(f"Measured: {(result.get('measured_at') or '')[:19]}")


@project_app.command("slack-status")
def cmd_project_slack_status(
    project: str = typer.Option(..., "--project", "-p"),
    style: Optional[str] = typer.Option(None, "--style"),
) -> None:
    """Generate a copy-ready executive Slack status message."""
    orch = _orchestrator()
    try:
        msg = orch.project_slack_status(project, style=style)
        console.print("\n[bold]--- Slack Status (copy ready) ---[/bold]")
        console.print(msg)
        console.print("[bold]--------------------------------[/bold]\n")
    except Exception as e:
        console.print(f"[red]Slack status failed:[/red] {e}")
        raise typer.Exit(1)


@project_app.command("report")
def cmd_project_report(
    project: str = typer.Option(..., "--project", "-p"),
    open_browser: bool = typer.Option(False, "--open"),
) -> None:
    """Generate an interactive HTML status report."""
    orch = _orchestrator()
    try:
        path = orch.project_report(project, open_browser=open_browser)
        console.print(f"[green]✓[/green] Report written to: {path}")
    except Exception as e:
        console.print(f"[red]Report generation failed:[/red] {e}")
        raise typer.Exit(1)


@project_app.command("rollback")
def cmd_project_rollback(
    project: str = typer.Option(..., "--project", "-p"),
    snapshot: str = typer.Option("latest", "--snapshot", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Restore context from a snapshot."""
    if not yes:
        confirmed = typer.confirm(
            f"Restore project '{project}' from snapshot '{snapshot}'? "
            "This will overwrite current context files."
        )
        if not confirmed:
            console.print("Rollback cancelled.")
            return
    orch = _orchestrator()
    result = orch.project_rollback(project, snapshot_id=snapshot)
    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Rolled back to snapshot {result['snapshot_id']}")


@project_app.command("ask")
def cmd_project_ask(
    project: str = typer.Option(..., "--project", "-p"),
    question: str = typer.Argument(...),
) -> None:
    """Ask a natural-language question grounded in project context."""
    orch = _orchestrator()
    project_dir, pcfg = orch._load_project(project)
    from .projects.context_manager import ContextManager
    ctx_mgr = ContextManager(project_dir / "context")
    context = ctx_mgr.load_all()

    context_text = "\n\n".join(
        f"[{name}]\n{cf.body[:800]}"
        for name, cf in context.items()
        if cf.body.strip()
    )

    provider = orch._get_provider()
    if not provider:
        console.print("[yellow]Claude provider unavailable. Cannot answer questions.[/yellow]")
        raise typer.Exit(1)

    system = (
        "You are a delivery analyst. Answer the following question using ONLY "
        "the provided project context. Do not invent facts not present in the context."
    )
    prompt = f"Project context:\n\n{context_text}\n\nQuestion: {question}"

    result = provider.complete(system=system, prompt=prompt, max_tokens=800, temperature=0.1)
    console.print(result.content)


# ---------------------------------------------------------------------------
# Dashboard commands
# ---------------------------------------------------------------------------

@dashboard_app.command("generate")
def cmd_dashboard_generate(
    refresh: bool = typer.Option(False, "--refresh", help="Re-sync ADO for all projects first"),
    open_browser: bool = typer.Option(False, "--open"),
) -> None:
    """Build the executive portfolio dashboard."""
    orch = _orchestrator()
    try:
        path = orch.dashboard_generate(refresh=refresh, open_browser=open_browser)
        console.print(f"[green]✓[/green] Dashboard written to: {path}")
    except Exception as e:
        console.print(f"[red]Dashboard generation failed:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# History commands
# ---------------------------------------------------------------------------

@history_app.command("show")
def cmd_history_show(
    project: str = typer.Option(..., "--project", "-p"),
    metric: str = typer.Option("overall_percent", "--metric"),
    since: Optional[str] = typer.Option(None, "--since", help="ISO date e.g. 2026-01-01"),
) -> None:
    """Show metric history for a project."""
    orch = _orchestrator()
    from .storage.repositories import MetricsRepository
    repo = MetricsRepository(orch.db)
    history = repo.get_history(project, metric=metric, since=since)
    if not history:
        console.print("[yellow]No history found.[/yellow]")
        return
    table = Table(title=f"History: {project} / {metric}")
    table.add_column("Date")
    table.add_column("Progress %")
    table.add_column("Health")
    table.add_column("Velocity/day")
    for row in history:
        pct = float(row.get("overall_percent", 0) or 0) * 100
        table.add_row(
            (row.get("measured_at") or "")[:10],
            f"{pct:.1f}%",
            row.get("health", "—"),
            f"{float(row.get('velocity_per_day', 0) or 0):.3f}",
        )
    console.print(table)


@history_app.command("export")
def cmd_history_export(
    project: str = typer.Option(..., "--project", "-p"),
    fmt: str = typer.Option("json", "--format", "-f", help="json or csv"),
) -> None:
    """Export project history to JSON or CSV."""
    orch = _orchestrator()
    from .storage.repositories import MetricsRepository
    repo = MetricsRepository(orch.db)
    history = repo.get_history(project, limit=500)
    if fmt == "json":
        typer.echo(json.dumps(history, indent=2, default=str))
    elif fmt == "csv":
        import csv, io
        output = io.StringIO()
        if history:
            w = csv.DictWriter(output, fieldnames=list(history[0].keys()))
            w.writeheader()
            w.writerows(history)
        typer.echo(output.getvalue())
    else:
        console.print(f"[red]Unknown format: {fmt}. Use json or csv.[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Portfolio commands
# ---------------------------------------------------------------------------

@portfolio_app.command("ask")
def cmd_portfolio_ask(
    question: str = typer.Argument(...),
) -> None:
    """Ask a natural-language question across the entire portfolio."""
    orch = _orchestrator()
    from .projects.scaffolder import ProjectScaffolder
    from .projects.context_manager import ContextManager

    scaffolder = ProjectScaffolder(orch.base_dir / orch.cfg.projects.root_path)
    project_ids = scaffolder.list_projects()

    context_parts = []
    for pid in project_ids:
        project_dir = orch.base_dir / orch.cfg.projects.root_path / pid
        ctx_mgr = ContextManager(project_dir / "context")
        context = ctx_mgr.load_all()
        for name, cf in context.items():
            if cf.body.strip():
                context_parts.append(f"[{pid}/{name}]\n{cf.body[:400]}")

    context_text = "\n\n---\n\n".join(context_parts[:20])  # limit tokens
    provider = orch._get_provider()
    if not provider:
        console.print("[yellow]Claude provider unavailable.[/yellow]")
        raise typer.Exit(1)

    system = (
        "You are a portfolio delivery analyst. Answer the question using ONLY "
        "the provided portfolio context. Cite project IDs when relevant."
    )
    prompt = f"Portfolio context:\n\n{context_text}\n\nQuestion: {question}"
    result = provider.complete(system=system, prompt=prompt, max_tokens=1000, temperature=0.1)
    console.print(result.content)


if __name__ == "__main__":
    app()
