"""View models — pre-resolved data structures passed to Jinja2 templates."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MilestoneVM:
    id: str
    name: str
    target_date: str
    forecast_date: str
    percent: float
    state: str


@dataclass
class RiskVM:
    id: str
    description: str
    severity: str
    status: str
    owner: str
    opened_at: str
    age_days: int


@dataclass
class DecisionVM:
    id: str
    decided_at: str
    decision: str
    rationale: str
    decided_by: str


@dataclass
class ChartData:
    dates: list[str]
    values: list[float]
    label: str


@dataclass
class ProjectReportVM:
    project_id: str
    project_name: str
    client: str
    delivery_manager: str
    generated_at: str
    health: str
    health_reasons: list[str]
    overall_percent: float
    progress_summary: str
    active_stage: Optional[str]
    milestones: list[MilestoneVM] = field(default_factory=list)
    open_risks: list[RiskVM] = field(default_factory=list)
    decisions: list[DecisionVM] = field(default_factory=list)
    executive_summary: str = ""
    velocity_per_day: Optional[float] = None
    forecast_date: Optional[str] = None
    forecast_confidence: Optional[str] = None
    forecast_explanation: str = ""
    monthly_revenue: float = 0.0
    total_contract_value: float = 0.0
    revenue_at_risk: bool = False
    progress_chart: Optional[str] = None   # rendered HTML string from Plotly
    velocity_chart: Optional[str] = None   # rendered HTML string from Plotly
    include_financials: bool = True
    include_risks: bool = True
    include_velocity: bool = True
    include_timeline: bool = True


@dataclass
class ProjectSummaryVM:
    project_id: str
    project_name: str
    health: str
    health_trend: str               # "improving" | "stable" | "declining"
    overall_percent: float
    last_updated: str
    active_milestone: Optional[str]
    forecast_date: Optional[str]
    open_high_risks: int
    monthly_revenue: float
    revenue_at_risk: bool
    is_blocked: bool
    is_negative_trend: bool


@dataclass
class PortfolioDashboardVM:
    generated_at: str
    projects: list[ProjectSummaryVM] = field(default_factory=list)
    portfolio_health: str = "green"
    total_revenue: float = 0.0
    revenue_at_risk: float = 0.0
    blocked_count: int = 0
    negative_trend_count: int = 0
    executive_summary: str = ""
