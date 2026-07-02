"""Workflow orchestrator — sequences agents, manages transactions and hooks."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config.loader import load_global_config, load_project_config, validate_global_config
from .config.models import GlobalConfig, ProjectConfig
from .claude.provider import resolve_provider, ClaudeProviderUnavailable
from .storage.db import init_db, Database
from .storage.snapshots import SnapshotManager
from .storage.repositories import ProjectRepository, MetricsRepository
from .security.redaction import install_redaction_filter
from .agents.context_curator import ContextCuratorAgent
from .agents.ado_metrics import AdoMetricsAgent
from .agents.status_analyst import StatusAnalystAgent
from .skills.slack_status import generate_slack_status, SlackStatusInputs
from .reporting.report_builder import build_project_report
from .reporting.dashboard_builder import build_portfolio_dashboard
from .projects.scaffolder import ProjectScaffolder

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central entry point — initializes all dependencies and drives workflows."""

    def __init__(self, base_dir: Path, config_path: Optional[Path] = None) -> None:
        self.base_dir = base_dir
        from .env import load_env_file
        load_env_file(base_dir)
        self.cfg = load_global_config(config_path or base_dir / "config" / "vbu-agent.yaml",
                                      base_dir=base_dir)
        install_redaction_filter()
        self._db: Optional[Database] = None
        self._snap_mgr: Optional[SnapshotManager] = None

    @property
    def db(self) -> Database:
        if self._db is None:
            db_path = self.base_dir / self.cfg.storage.sqlite_path
            self._db = init_db(db_path)
        return self._db

    @property
    def snap_mgr(self) -> SnapshotManager:
        if self._snap_mgr is None:
            snap_path = self.base_dir / self.cfg.storage.snapshots_path
            self._snap_mgr = SnapshotManager(snap_path)
        return self._snap_mgr

    def _get_provider(self):
        try:
            return resolve_provider(self.cfg)
        except ClaudeProviderUnavailable as e:
            logger.warning("Claude provider unavailable: %s — proceeding with fallbacks", e)
            return None

    def _load_project(self, project_id: str) -> tuple[Path, ProjectConfig]:
        project_dir = self.base_dir / self.cfg.projects.root_path / project_id
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        pcfg = load_project_config(project_dir)
        return project_dir, pcfg

    def _ensure_project_registered(self, pcfg: ProjectConfig) -> None:
        proj_repo = ProjectRepository(self.db)
        proj_repo.upsert(
            id=pcfg.project.id,
            name=pcfg.project.name,
            client=pcfg.project.client,
            delivery_manager=pcfg.project.delivery_manager,
            progress_type=pcfg.progress_model.type,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def project_update(self, project_id: str, dry_run: bool = False,
                       review_required: bool = False) -> dict:
        project_dir, pcfg = self._load_project(project_id)
        self._ensure_project_registered(pcfg)
        provider = self._get_provider()

        agent = ContextCuratorAgent(
            project_dir=project_dir,
            project_config=pcfg,
            global_config=self.cfg,
            db=self.db,
            claude_provider=provider,
            snapshot_manager=self.snap_mgr,
        )
        result = agent.run(dry_run=dry_run, review_required=review_required)
        return {
            "run_id": result.run_id,
            "mode": result.mode,
            "dry_run": result.dry_run,
            "changes": result.changes_applied,
            "conflicts": len(result.conflicts_detected),
            "change_summary": result.change_summary,
            "skipped": result.skipped,
        }

    def project_sync_ado(self, project_id: str, no_cache: bool = False) -> dict:
        project_dir, pcfg = self._load_project(project_id)
        self._ensure_project_registered(pcfg)

        agent = AdoMetricsAgent(
            project_config=pcfg,
            global_config=self.cfg,
            db=self.db,
            snapshot_manager=self.snap_mgr,
        )
        result = agent.run(no_cache=no_cache)
        if result is None:
            return {"error": "ADO sync failed"}
        return {
            "health": result.health,
            "overall_percent": result.overall_percent,
            "active_stage": result.active_stage,
        }

    def project_status(self, project_id: str) -> dict:
        project_dir, pcfg = self._load_project(project_id)
        metrics_repo = MetricsRepository(self.db)
        latest = metrics_repo.get_latest(project_id)
        if not latest:
            return {"error": "No metrics found. Run sync-ado first."}
        return latest

    def project_slack_status(self, project_id: str, style: Optional[str] = None) -> str:
        project_dir, pcfg = self._load_project(project_id)
        self._ensure_project_registered(pcfg)

        # Load latest metrics
        metrics_repo = MetricsRepository(self.db)
        latest = metrics_repo.get_latest(project_id)
        if not latest:
            return (
                f"{pcfg.project.name} — Status: Unknown\n"
                "Run 'vbu-agent project sync-ado' first to compute metrics."
            )

        from .storage.repositories import RiskRepository, MilestoneRepository
        risk_repo = RiskRepository(self.db)
        open_risks = risk_repo.get_open(project_id)
        ms_repo = MilestoneRepository(self.db)
        milestones = ms_repo.get_latest_all(project_id)

        active_ms = next((m for m in milestones if m.get("state") != "done"), None)
        ms_name = active_ms["name"] if active_ms else "—"
        ms_date = active_ms.get("forecast_date") or active_ms.get("target_date") or "TBD" if active_ms else "TBD"

        high_risk = next((r for r in open_risks if r.get("severity") in ("high", "critical")), None)
        top_risk = high_risk.get("description", "")[:120] if high_risk else "None"

        pct = float(latest.get("overall_percent", 0) or 0) * 100
        progress_summary = f"{pct:.0f}% complete"

        inputs = SlackStatusInputs(
            project_name=pcfg.project.name,
            health=latest.get("health", "unknown"),
            health_reasons=[],
            progress_summary=progress_summary,
            milestone_name=ms_name,
            target_or_forecast_date=ms_date,
            top_risk_text=top_risk,
            ask_text="",
            max_words=pcfg.slack.max_words if hasattr(pcfg.slack, "max_words") else self.cfg.slack.max_words,
            tone=pcfg.slack.tone,
        )

        provider = self._get_provider()
        slack_msg = generate_slack_status(inputs, provider)

        # Write to generated/
        generated_dir = project_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)
        from .security.scanner import SecretScanner
        SecretScanner().safe_write(generated_dir / "slack_status.md", slack_msg)

        from .storage.repositories import ArtifactRepository
        art_repo = ArtifactRepository(self.db)
        art_repo.insert(
            project_id=project_id,
            run_id=None,
            kind="slack",
            path=str(generated_dir / "slack_status.md"),
        )
        return slack_msg

    def project_report(self, project_id: str, open_browser: bool = False) -> Path:
        project_dir, pcfg = self._load_project(project_id)
        self._ensure_project_registered(pcfg)

        # Need a ProgressResult — use a dummy if no ADO
        from .storage.repositories import MetricsRepository, RiskRepository, DecisionRepository
        metrics_repo = MetricsRepository(self.db)
        latest = metrics_repo.get_latest(project_id)

        if latest:
            from .progress.engine import ProgressResult
            from .progress.health import compute_health
            health_color, health_reasons = compute_health(
                float(latest.get("overall_percent", 0) or 0),
                pcfg.project.health_thresholds,
            )
            # Build a minimal ProgressResult from stored metrics
            progress = ProgressResult(
                overall_percent=float(latest.get("overall_percent", 0) or 0),
                health=health_color,
                health_reasons=health_reasons,
                active_stage=latest.get("active_stage"),
            )
        else:
            from .progress.engine import ProgressResult
            progress = ProgressResult(
                overall_percent=0.0,
                health="red",
                health_reasons=["No ADO data — run sync-ado first"],
            )

        history = MetricsRepository(self.db).get_history(project_id)
        risk_data = RiskRepository(self.db).get_open(project_id)
        dec_data = DecisionRepository(self.db).get_all(project_id)

        analyst = StatusAnalystAgent(db=self.db, project_config=pcfg)
        analyst_status = analyst.analyze(progress)
        analyst_status.open_risks = risk_data
        analyst_status.decisions = dec_data

        provider = self._get_provider()
        output_dir = self.base_dir / self.cfg.reports.output_path
        report_path = build_project_report(
            status=analyst_status,
            project_config=pcfg,
            global_config=self.cfg,
            history=history,
            provider=provider,
            output_dir=output_dir,
            base_dir=self.base_dir,
        )

        if open_browser:
            import webbrowser
            webbrowser.open(f"file://{report_path.resolve()}")

        return report_path

    def project_rollback(self, project_id: str, snapshot_id: str = "latest") -> dict:
        project_dir, pcfg = self._load_project(project_id)
        context_dir = project_dir / "context"

        if snapshot_id == "latest":
            snap = self.snap_mgr.get_latest_snapshot_path(project_id)
            if snap is None:
                return {"error": "No snapshots found for this project."}
            snapshot_id = snap.name

        restored = self.snap_mgr.restore_snapshot(project_id, snapshot_id, context_dir)
        return {"restored_from": str(restored), "snapshot_id": snapshot_id}

    def project_list(self) -> list[dict]:
        scaffolder = ProjectScaffolder(self.base_dir / self.cfg.projects.root_path)
        project_ids = scaffolder.list_projects()
        proj_repo = ProjectRepository(self.db)
        result = []
        for pid in project_ids:
            row = proj_repo.get(pid)
            if row:
                result.append(row)
            else:
                result.append({"id": pid, "name": pid, "current_health": "unknown"})
        return result

    def dashboard_generate(self, refresh: bool = False, open_browser: bool = False) -> Path:
        scaffolder = ProjectScaffolder(self.base_dir / self.cfg.projects.root_path)
        project_ids = scaffolder.list_projects()

        if refresh:
            for pid in project_ids:
                try:
                    self.project_sync_ado(pid)
                except Exception as e:
                    logger.warning("ADO sync failed for %s during refresh: %s", pid, e)

        summaries: list[dict] = []
        metrics_repo = MetricsRepository(self.db)
        proj_repo = ProjectRepository(self.db)

        for pid in project_ids:
            prow = proj_repo.get(pid)
            latest = metrics_repo.get_latest(pid)
            history = metrics_repo.get_history(pid, limit=30)
            if not prow:
                continue
            summaries.append({
                "project_id": pid,
                "project_name": prow.get("name", pid),
                "health": (latest or {}).get("health", "unknown"),
                "overall_percent": (latest or {}).get("overall_percent", 0),
                "last_updated": (prow or {}).get("last_updated_at", "")[:10],
                "monthly_revenue": (latest or {}).get("monthly_revenue", 0),
                "history": history,
                "open_high_risks": 0,
            })

        provider = self._get_provider()
        output_dir = self.base_dir / self.cfg.reports.output_path
        dash_path = build_portfolio_dashboard(
            project_summaries=summaries,
            global_config=self.cfg,
            provider=provider,
            output_dir=output_dir,
            base_dir=self.base_dir,
        )

        if open_browser:
            import webbrowser
            webbrowser.open(f"file://{dash_path.resolve()}")

        return dash_path

    def doctor(self) -> dict:
        """Diagnose environment, providers, paths, DB connectivity."""
        results: dict[str, str] = {}

        import os
        env_path = self.base_dir / ".env"
        has_key = bool(os.environ.get(self.cfg.claude.api_key_env_var, "").strip())
        if env_path.exists() and has_key:
            results["secrets"] = "OK (.env loaded, API key present)"
        elif env_path.exists():
            results["secrets"] = f"WARN: .env found but {self.cfg.claude.api_key_env_var} is empty"
        else:
            results["secrets"] = "WARN: no .env file — copy .env.example to .env and add your key"

        # Config
        try:
            issues = validate_global_config(self.cfg, self.base_dir)
            results["config"] = "OK" if not issues else f"WARN: {'; '.join(issues)}"
        except Exception as e:
            results["config"] = f"ERROR: {e}"

        # Claude provider
        try:
            provider = resolve_provider(self.cfg)
            results["claude_provider"] = f"OK ({provider.mode})"
        except ClaudeProviderUnavailable as e:
            results["claude_provider"] = f"UNAVAILABLE: {e.tried}"

        # DB
        try:
            self.db.execute("SELECT 1")
            results["database"] = "OK"
        except Exception as e:
            results["database"] = f"ERROR: {e}"

        # Paths
        for label, rel_path in [
            ("projects_root", self.cfg.projects.root_path),
            ("snapshots_path", self.cfg.storage.snapshots_path),
            ("reports_path", self.cfg.reports.output_path),
        ]:
            p = self.base_dir / rel_path
            results[label] = "OK" if p.exists() else f"MISSING (will be created on use): {p}"

        # ADO connectivity (per project, light probe only)
        scaffolder = ProjectScaffolder(self.base_dir / self.cfg.projects.root_path)
        for pid in scaffolder.list_projects():
            try:
                project_dir = self.base_dir / self.cfg.projects.root_path / pid
                pcfg = load_project_config(project_dir)
                from .ado.client import AdoClient
                client = AdoClient(
                    ado_config=pcfg.azure_devops,
                    field_mappings=pcfg.field_mappings,
                    global_ado=self.cfg.ado,
                )
                ok = client.test_connectivity()
                results[f"ado_{pid}"] = "OK" if ok else "UNREACHABLE (PAT may be missing/invalid)"
            except Exception as e:
                results[f"ado_{pid}"] = f"SKIPPED: {type(e).__name__}"

        return results

    def init(self, force: bool = False) -> None:
        """Scaffold the workspace directory structure."""
        for d in [
            self.base_dir / "config",
            self.base_dir / self.cfg.projects.root_path,
            self.base_dir / "data" / "snapshots",
            self.base_dir / self.cfg.reports.output_path,
            self.base_dir / "templates" / "partials",
            self.base_dir / "artifacts",
        ]:
            d.mkdir(parents=True, exist_ok=True)

        gitignore = self.base_dir / ".gitignore"
        if not gitignore.exists() or force:
            from importlib.resources import files
            logger.info("Workspace initialized at %s", self.base_dir)
