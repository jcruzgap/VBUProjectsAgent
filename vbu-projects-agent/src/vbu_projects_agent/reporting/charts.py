"""Plotly chart construction for progress, velocity, and forecast."""
from __future__ import annotations

import json
from typing import Optional

try:
    import plotly.graph_objects as go
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

from .view_models import ChartData


def build_progress_chart(history: list[dict], title: str = "Progress Over Time") -> str:
    """Return an inline HTML div with a Plotly progress chart, or empty string."""
    if not _PLOTLY_AVAILABLE or not history:
        return ""

    dates = [r.get("measured_at", "")[:10] for r in history]
    values = [float(r.get("overall_percent", 0) or 0) * 100 for r in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode="lines+markers",
        name="Progress %",
        line=dict(color="#2563eb", width=2),
        marker=dict(size=5),
    ))
    fig.add_hline(y=85, line_dash="dot", line_color="green",
                  annotation_text="Green threshold (85%)")
    fig.add_hline(y=65, line_dash="dot", line_color="orange",
                  annotation_text="Yellow threshold (65%)")
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Progress (%)",
        yaxis=dict(range=[0, 105]),
        height=300,
        margin=dict(l=40, r=20, t=40, b=40),
        template="plotly_white",
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_velocity_chart(history: list[dict]) -> str:
    if not _PLOTLY_AVAILABLE or len(history) < 2:
        return ""

    dates = [r.get("measured_at", "")[:10] for r in history]
    velocities = [float(r.get("velocity_per_day", 0) or 0) for r in history]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=velocities,
        name="Velocity (units/day)",
        marker_color="#7c3aed",
    ))
    fig.update_layout(
        title="Daily Velocity Trend",
        xaxis_title="Date",
        yaxis_title="Units / Day",
        height=250,
        margin=dict(l=40, r=20, t=40, b=40),
        template="plotly_white",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_health_heatmap(projects: list[dict]) -> str:
    """Portfolio heatmap: projects × health color."""
    if not _PLOTLY_AVAILABLE or not projects:
        return ""

    color_map = {"green": 1.0, "yellow": 0.5, "red": 0.0}
    names = [p.get("project_name", p.get("project_id", "?")) for p in projects]
    health_vals = [color_map.get(p.get("health", "red"), 0) for p in projects]

    fig = go.Figure(go.Bar(
        x=names,
        y=[1] * len(names),
        marker_color=[
            "#16a34a" if v == 1.0 else "#ca8a04" if v == 0.5 else "#dc2626"
            for v in health_vals
        ],
        text=[p.get("health", "?").upper() for p in projects],
        textposition="inside",
    ))
    fig.update_layout(
        title="Portfolio Health Overview",
        yaxis=dict(visible=False),
        height=220,
        margin=dict(l=20, r=20, t=40, b=40),
        template="plotly_white",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)
