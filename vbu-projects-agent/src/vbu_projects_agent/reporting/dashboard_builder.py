"""Executive Portfolio Dashboard builder."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.models import GlobalConfig
    from ..claude.provider import ClaudeProvider

from .view_models import PortfolioDashboardVM, ProjectSummaryVM
from .charts import build_health_heatmap
from ..skills.executive_summary import generate_executive_summary
from ..security.scanner import SecretScanner

logger = logging.getLogger(__name__)
_scanner = SecretScanner()


def _health_trend(history: list[dict]) -> str:
    if len(history) < 3:
        return "stable"
    recent = [r.get("overall_percent", 0) for r in history[-3:]]
    if recent[-1] > recent[0]:
        return "improving"
    elif recent[-1] < recent[0]:
        return "declining"
    return "stable"


def build_portfolio_dashboard(
    project_summaries: list[dict],
    global_config: "GlobalConfig",
    provider: Optional["ClaudeProvider"],
    output_dir: Path,
    base_dir: Path,
) -> Path:
    """Assemble and render the executive portfolio dashboard."""
    projects_vm: list[ProjectSummaryVM] = []
    total_revenue = 0.0
    revenue_at_risk = 0.0

    for p in project_summaries:
        monthly = float(p.get("monthly_revenue", 0) or 0)
        total_revenue += monthly
        health = p.get("health", "red")
        is_at_risk = health in ("yellow", "red") and monthly > 0
        if is_at_risk:
            revenue_at_risk += monthly

        projects_vm.append(ProjectSummaryVM(
            project_id=p.get("project_id", ""),
            project_name=p.get("project_name", ""),
            health=health,
            health_trend=_health_trend(p.get("history", [])),
            overall_percent=float(p.get("overall_percent", 0) or 0),
            last_updated=p.get("last_updated", "")[:10],
            active_milestone=p.get("active_milestone"),
            forecast_date=p.get("forecast_date"),
            open_high_risks=int(p.get("open_high_risks", 0) or 0),
            monthly_revenue=monthly,
            revenue_at_risk=is_at_risk,
            is_blocked=bool(p.get("is_blocked", False)),
            is_negative_trend=(_health_trend(p.get("history", [])) == "declining"),
        ))

    blocked_count = sum(1 for p in projects_vm if p.is_blocked)
    negative_count = sum(1 for p in projects_vm if p.is_negative_trend)

    # Portfolio health = worst of all projects
    all_health = [p.health for p in projects_vm]
    if "red" in all_health:
        portfolio_health = "red"
    elif "yellow" in all_health:
        portfolio_health = "yellow"
    else:
        portfolio_health = "green"

    facts = {
        "portfolio_health": portfolio_health,
        "project_count": len(projects_vm),
        "blocked": blocked_count,
        "negative_trend": negative_count,
        "total_revenue": total_revenue,
        "revenue_at_risk": revenue_at_risk,
    }
    exec_summary = generate_executive_summary(
        facts=facts,
        recent_changes="",
        provider=provider,
    )

    heatmap_html = build_health_heatmap([
        {"project_name": p.project_name, "health": p.health} for p in projects_vm
    ])

    vm = PortfolioDashboardVM(
        generated_at=datetime.now(timezone.utc).isoformat(),
        projects=projects_vm,
        portfolio_health=portfolio_health,
        total_revenue=total_revenue,
        revenue_at_risk=revenue_at_risk,
        blocked_count=blocked_count,
        negative_trend_count=negative_count,
        executive_summary=exec_summary,
    )

    html = _builtin_dashboard_html(vm, heatmap_html)

    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = output_dir / f"executive_dashboard_{today}.html"
    _scanner.safe_write(out_path, html)
    logger.info("Portfolio dashboard written to %s", out_path)
    return out_path


def _builtin_dashboard_html(vm: PortfolioDashboardVM, heatmap_html: str) -> str:
    health_color = {"green": "#16a34a", "yellow": "#ca8a04", "red": "#dc2626"}.get(
        vm.portfolio_health, "#64748b"
    )
    rows = ""
    for p in vm.projects:
        hc = {"green": "#dcfce7", "yellow": "#fef9c3", "red": "#fee2e2"}.get(p.health, "#f1f5f9")
        trend_icon = "↑" if p.health_trend == "improving" else ("↓" if p.health_trend == "declining" else "→")
        rows += f"""<tr style="background:{hc}">
  <td><b>{p.project_name}</b></td>
  <td>{p.health.upper()} {trend_icon}</td>
  <td>{p.overall_percent * 100:.0f}%</td>
  <td>{p.active_milestone or '—'}</td>
  <td>{p.forecast_date or '—'}</td>
  <td>{p.open_high_risks}</td>
  <td>{'🚨 Yes' if p.revenue_at_risk else 'No'}</td>
  <td>{p.last_updated}</td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VBU Executive Portfolio Dashboard</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; color: #1e293b; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border: 1px solid #e2e8f0; }}
  th {{ background: #f8fafc; font-weight: 600; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
  .kpi {{ background: #f8fafc; border-radius: 8px; padding: 1rem; text-align: center; }}
  .kpi-value {{ font-size: 2rem; font-weight: 700; color: #2563eb; }}
  .kpi-label {{ color: #64748b; font-size: 0.85rem; margin-top: 4px; }}
  .health-badge {{ display: inline-block; padding: 4px 14px; border-radius: 9999px;
                   background: {health_color}; color: white; font-weight: 600; }}
  .section {{ margin: 2rem 0; border-top: 1px solid #e2e8f0; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>VBU Executive Portfolio Dashboard</h1>
<p style="color:#64748b">Generated: {vm.generated_at[:10]}</p>

<div class="section">
  <h2>Portfolio Health: <span class="health-badge">{vm.portfolio_health.upper()}</span></h2>
  <p>{vm.executive_summary}</p>
</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-value">{len(vm.projects)}</div><div class="kpi-label">Active Projects</div></div>
  <div class="kpi"><div class="kpi-value">{vm.blocked_count}</div><div class="kpi-label">Blocked</div></div>
  <div class="kpi"><div class="kpi-value">{vm.negative_trend_count}</div><div class="kpi-label">Negative Trend</div></div>
  <div class="kpi"><div class="kpi-value" style="color:#dc2626">${vm.revenue_at_risk:,.0f}</div><div class="kpi-label">Revenue at Risk ($/mo)</div></div>
</div>

<div class="section">
  <h2>Health Heatmap</h2>
  {heatmap_html}
</div>

<div class="section">
  <h2>All Projects</h2>
  <table>
    <thead><tr>
      <th>Project</th><th>Health</th><th>Progress</th>
      <th>Active Milestone</th><th>Forecast</th>
      <th>High Risks</th><th>Revenue at Risk</th><th>Last Updated</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body>
</html>"""
