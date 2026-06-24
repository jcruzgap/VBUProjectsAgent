"""Project HTML status report builder."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from ..config.models import GlobalConfig, ProjectConfig
    from ..agents.status_analyst import ProjectStatusView
    from ..claude.provider import ClaudeProvider

from .view_models import (
    ProjectReportVM, MilestoneVM, RiskVM, DecisionVM, ChartData
)
from .charts import build_progress_chart, build_velocity_chart
from ..skills.executive_summary import generate_executive_summary
from ..skills.risk_analysis import generate_risk_analysis
from ..security.scanner import SecretScanner

logger = logging.getLogger(__name__)
_scanner = SecretScanner()


def _age_days(opened_at: str) -> int:
    try:
        opened = date.fromisoformat(opened_at[:10])
        return (date.today() - opened).days
    except (ValueError, TypeError):
        return 0


def _build_vm(
    status: "ProjectStatusView",
    project_config: "ProjectConfig",
    history: list[dict],
    provider: Optional["ClaudeProvider"],
    model: Optional[str],
) -> ProjectReportVM:
    milestones_vm: list[MilestoneVM] = []
    from ..progress.test_case_milestones import MilestoneProgress
    if hasattr(status, "milestones") or True:
        # We get milestone data from the latest metrics snapshot indirectly
        pass

    risks_vm = [
        RiskVM(
            id=r["id"],
            description=r.get("description", ""),
            severity=r.get("severity", ""),
            status=r.get("status", ""),
            owner=r.get("owner", ""),
            opened_at=r.get("opened_at", "")[:10],
            age_days=_age_days(r.get("opened_at", "")),
        )
        for r in status.open_risks
    ]

    decisions_vm = [
        DecisionVM(
            id=d["id"],
            decided_at=d.get("decided_at", "")[:10],
            decision=d.get("decision", ""),
            rationale=d.get("rationale", ""),
            decided_by=d.get("decided_by", ""),
        )
        for d in status.decisions
    ]

    facts = {
        "health": status.health,
        "overall_percent": status.overall_percent,
        "progress_summary": status.progress_summary,
        "next_milestone": status.next_milestone_name,
        "next_milestone_date": status.next_milestone_date,
        "open_risks_count": len(status.open_risks),
        "monthly_revenue": status.revenue_monthly,
    }

    exec_summary = generate_executive_summary(
        facts=facts,
        recent_changes="",
        provider=provider,
        model=model,
    )

    risk_prose = generate_risk_analysis(
        risks=status.open_risks,
        provider=provider,
        model=model,
    )

    progress_chart_html = build_progress_chart(history)
    velocity_chart_html = build_velocity_chart(history)

    return ProjectReportVM(
        project_id=status.project_id,
        project_name=status.project_name,
        client=project_config.project.client,
        delivery_manager=project_config.project.delivery_manager,
        generated_at=datetime.now(timezone.utc).isoformat(),
        health=status.health,
        health_reasons=status.health_reasons,
        overall_percent=status.overall_percent,
        progress_summary=status.progress_summary,
        active_stage=status.active_stage,
        open_risks=risks_vm,
        decisions=decisions_vm,
        executive_summary=exec_summary,
        monthly_revenue=project_config.revenue.monthly_revenue,
        total_contract_value=project_config.revenue.total_contract_value,
        revenue_at_risk=status.revenue_at_risk,
        include_financials=project_config.reporting.include_financials,
        include_risks=project_config.reporting.include_risks,
        include_velocity=project_config.reporting.include_velocity,
        include_timeline=project_config.reporting.include_timeline,
        progress_chart=progress_chart_html,
        velocity_chart=velocity_chart_html,
    )


def build_project_report(
    status: "ProjectStatusView",
    project_config: "ProjectConfig",
    global_config: "GlobalConfig",
    history: list[dict],
    provider: Optional["ClaudeProvider"],
    output_dir: Path,
    base_dir: Path,
) -> Path:
    """Render a standalone HTML project status report. Returns the output path."""
    vm = _build_vm(status, project_config, history, provider, model=None)

    template_path = base_dir / global_config.reports.project_report_template
    if not template_path.exists():
        logger.warning("Template not found at %s — using built-in fallback", template_path)
        html = _builtin_html(vm)
    else:
        env = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            autoescape=select_autoescape(["html", "j2"]),
        )
        tmpl = env.get_template(template_path.name)
        html = tmpl.render(report=vm)

    # Validate
    _validate_report(html, vm)

    # Write
    out_dir = output_dir / status.project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = out_dir / f"status_report_{today}.html"
    _scanner.safe_write(out_path, html)
    logger.info("Project report written to %s", out_path)
    return out_path


def _validate_report(html: str, vm: ProjectReportVM) -> None:
    required = ["executive_summary", "health", "progress"]
    for section in required:
        if section.lower() not in html.lower():
            logger.warning("Report validation: missing section '%s'", section)


def _builtin_html(vm: ProjectReportVM) -> str:
    """Minimal built-in HTML when no Jinja2 template is available."""
    health_color = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}.get(
        vm.health, "#64748b"
    )
    pct = f"{vm.overall_percent * 100:.1f}%"
    risks_html = "".join(
        f"<li><b>{r.id}</b> ({r.severity}): {r.description} — {r.age_days} days open</li>"
        for r in vm.open_risks
    )
    decisions_html = "".join(
        f"<li><b>{d.id}</b> ({d.decided_at}): {d.decision}</li>"
        for d in vm.decisions
    )
    progress_chart = vm.progress_chart or ""
    velocity_chart = vm.velocity_chart or ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{vm.project_name} — Status Report</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1e293b; }}
  .health-badge {{ display: inline-block; padding: 4px 14px; border-radius: 9999px;
                   background: {health_color}; color: white; font-weight: 600; font-size: 1.1em; }}
  .section {{ margin: 2rem 0; border-top: 1px solid #e2e8f0; padding-top: 1rem; }}
  .meta {{ color: #64748b; font-size: 0.85em; }}
  ul {{ padding-left: 1.2rem; }}
  .progress-bar {{ background: #e2e8f0; border-radius: 6px; height: 18px; margin: 8px 0; }}
  .progress-fill {{ background: {health_color}; height: 18px; border-radius: 6px;
                    width: {pct}; transition: width 0.5s; }}
</style>
</head>
<body>
<h1>{vm.project_name}</h1>
<p class="meta">Client: {vm.client} &nbsp;|&nbsp; DM: {vm.delivery_manager} &nbsp;|&nbsp;
Generated: {vm.generated_at[:10]}</p>

<div class="section">
  <h2>Health: <span class="health-badge">{vm.health.upper()}</span></h2>
  <ul>{"".join(f"<li>{r}</li>" for r in vm.health_reasons)}</ul>
</div>

<div class="section">
  <h2>Executive Summary</h2>
  <p>{vm.executive_summary}</p>
</div>

<div class="section">
  <h2>Progress — {pct}</h2>
  <div class="progress-bar"><div class="progress-fill"></div></div>
  <p>{vm.progress_summary}</p>
  {progress_chart}
</div>

{"<div class='section'><h2>Velocity</h2>" + velocity_chart + "</div>" if vm.include_velocity else ""}

{"<div class='section'><h2>Risks (" + str(len(vm.open_risks)) + " open)</h2><ul>" + risks_html + "</ul></div>" if vm.include_risks else ""}

<div class="section">
  <h2>Decisions</h2>
  <ul>{decisions_html or "<li>No decisions recorded.</li>"}</ul>
</div>

{"<div class='section'><h2>Financials</h2><p>Monthly Revenue: USD " + str(vm.monthly_revenue) + ('' if not vm.revenue_at_risk else ' <b style=\"color:red\">[Revenue at Risk]</b>') + "</p></div>" if vm.include_financials else ""}

</body>
</html>"""
