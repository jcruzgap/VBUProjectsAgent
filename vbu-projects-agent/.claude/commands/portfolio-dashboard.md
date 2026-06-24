# Generate Portfolio Dashboard

Build the executive portfolio dashboard across all active projects.

**Usage:** `/portfolio-dashboard`

## Steps

1. Generate dashboard from cached metrics (fast):
```bash
vbu-agent dashboard generate --open
```

Or refresh ADO data for all projects first (slower but current):
```bash
vbu-agent dashboard generate --refresh --open
```

The dashboard includes:
- Portfolio health summary (green/yellow/red roll-up)
- All projects with health, trend, progress, next milestone, and forecast
- Revenue at risk (sum of monthly revenue on yellow/red projects)
- Blocked and negative-trend projects highlighted
- Portfolio health heatmap (Plotly interactive chart)
