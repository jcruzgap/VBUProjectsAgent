# VBU-Projects-Agent

A Python CLI powered by Claude that standardizes how Velocity Business Unit (VBU) Delivery Managers maintain project context, track delivery progress from Azure DevOps, and produce executive-ready Slack messages, HTML reports, and portfolio dashboards.

---

## What it does

| Pain | Solution |
|------|----------|
| Scattered standup notes, client emails, and ADO exports | Drop files into `input/` and run one command — agent reads, summarizes, and surgically updates project context |
| Manual status updates take 30+ minutes | `vbu-agent project slack-status` generates a copy-ready Slack message in seconds |
| No consistent progress measurement across projects | Pluggable progress engine: staged tags, test-case milestones, weighted workload, or manual KPIs |
| No portfolio view for executives | `vbu-agent dashboard generate` builds an interactive HTML portfolio dashboard |
| Risk of stale, overwritten context | Every update snapshots first; any change is reversible via `project rollback` |
| Secrets in logs or config files | Redaction filter on all logging; secrets never written to YAML, reports, or snapshots |

---

## Architecture overview

```
┌─────────────────────────────────────────────────┐
│          CLI  (vbu-agent — Typer)               │
└──────────────────┬──────────────────────────────┘
                   │
          Orchestrator (workflow engine)
                   │
     ┌─────────────┼──────────────┬──────────────┐
     │             │              │              │
  Config       ADO Client    Progress       Context
  (Pydantic)   (WIQL/batch)  Engine         Manager
                              (4 strategies) (MD files)
     │             │              │              │
     └─────────────┴──────────────┴──────────────┘
                   │
     ┌─────────────┼──────────────┐
     │             │              │
  Skills        Storage       Reporting
  (Claude prose) (SQLite +    (Jinja2 +
                 snapshots)    Plotly HTML)
```

**Key principle:** Metrics are computed deterministically in Python from ADO data. Claude is used **only** to write prose — Slack messages, executive summaries, risk narratives, forecast explanations. No number in any output is invented by the model.

---

## Quick start

### Requirements

- Python 3.11+
- One of: `ANTHROPIC_API_KEY` env var **or** Claude CLI installed locally
- (For ADO sync) Azure DevOps PAT with Work Items: Read scope

### Install

```bash
git clone <repo-url>
cd vbu-projects-agent

# Create and activate virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -e ".[dev]"
```

### One-time workspace setup

```bash
# Scaffold directories and verify environment
vbu-agent init
vbu-agent config validate
vbu-agent doctor
```

### Set credentials

```bash
# Claude (choose one)
export ANTHROPIC_API_KEY=sk-ant-...          # API key mode
# OR install Claude CLI and authenticate — LocalCli mode is used automatically

# Azure DevOps (one per project, named per project.yaml)
export PROJECT_ALPHA_ADO_PAT=<your-ado-pat>
```

---

## Onboarding a project

```bash
# 1. Create project folder with scaffolded files
vbu-agent project create --project project-alpha --name "Project Alpha"

# 2. Edit the project config
#    Fill in: azure_devops section, progress_model milestones/stages, revenue
open projects/project-alpha/project.yaml

# 3. Validate everything looks right
vbu-agent project validate --project project-alpha
vbu-agent doctor

# 4. Pull first ADO metrics
vbu-agent project sync-ado --project project-alpha

# 5. See current status
vbu-agent project status --project project-alpha

# 6. Generate your first Slack message
vbu-agent project slack-status --project project-alpha
```

---

## Daily DM workflow (5 minutes)

```bash
# Drop standup notes, client emails, or exported ADO summaries into input/
cp ~/Downloads/standup-notes-2026-06-19.md projects/project-alpha/input/

# Preview what the agent would change (no writes)
vbu-agent project update --project project-alpha --dry-run

# Apply changes to context files
vbu-agent project update --project project-alpha

# Generate Slack status (copy-paste ready)
vbu-agent project slack-status --project project-alpha
```

---

## Weekly workflow

```bash
# Refresh ADO metrics
vbu-agent project sync-ado --project project-alpha

# Generate interactive HTML report (opens in browser)
vbu-agent project report --project project-alpha --open

# Build executive portfolio dashboard across all projects
vbu-agent dashboard generate --open

# Export history for analysis
vbu-agent history export --project project-alpha --format csv > history.csv
```

---

## Command reference

### Root commands

| Command | Description |
|---------|-------------|
| `vbu-agent init` | Scaffold workspace directories |
| `vbu-agent doctor` | Diagnose Claude provider, ADO reachability, paths, DB |
| `vbu-agent config validate` | Validate `config/vbu-agent.yaml`; exits non-zero on error |

### Project commands

| Command | Description | Key flags |
|---------|-------------|-----------|
| `project create` | Scaffold project folder + `project.yaml` + empty context | `--project`, `--name`, `--force` |
| `project list` | List all projects with health and last-update | `--json` |
| `project validate` | Validate `project.yaml` + context file integrity | `--project` |
| `project update` | Run the full context update workflow | `--dry-run`, `--review-required` |
| `project sync-ado` | Pull ADO metrics + recompute progress | `--no-cache` |
| `project status` | Print current computed metrics | `--json` |
| `project slack-status` | Generate copy-ready Slack message | `--style` |
| `project report` | Generate standalone interactive HTML report | `--open` |
| `project rollback` | Restore context from a snapshot | `--snapshot latest\|<run_id>`, `--yes` |
| `project ask` | Ask a natural-language question about a project | positional question |

### Dashboard

| Command | Description | Key flags |
|---------|-------------|-----------|
| `dashboard generate` | Build executive portfolio dashboard | `--refresh`, `--open` |

### History

| Command | Description | Key flags |
|---------|-------------|-----------|
| `history show` | Show metric time-series for a project | `--metric`, `--since` |
| `history export` | Export history to JSON or CSV | `--format json\|csv` |

### Portfolio

| Command | Description |
|---------|-------------|
| `portfolio ask` | Ask a natural-language question across the entire portfolio |

### Global flags

All commands accept: `--config <path>`, `--base-dir <path>`, `--verbose/-v`, `--quiet/-q`

---

## Update modes

| Mode | Command | Writes context? | Archives input? | Use when |
|------|---------|-----------------|-----------------|----------|
| Default | `project update` | Yes | Yes | Routine trusted updates |
| Dry-run | `project update --dry-run` | No | No | Preview proposed changes |
| Review | `project update --review-required` | Only after approval | Only after approval | Sensitive projects |

---

## Progress measurement strategies

Set `progress_model.type` in `project.yaml`:

### `test_case_milestones`
For projects with milestone targets defined as "N passing test cases". Computes passing test cases from ADO, calculates velocity from history, and forecasts completion dates.

```yaml
progress_model:
  type: test_case_milestones
  done_states: [Done, Closed, Passed]
  milestones:
    - id: alpha
      name: Alpha Ready
      target_passing: 100
      target_date: 2026-07-12
    - id: beta
      name: Beta Ready
      target_passing: 200
      target_date: 2026-08-30
```

### `staged_tags`
For projects where PBIs are grouped into stages by ADO tags (e.g., `AlphaReady`, `BetaReady`).

```yaml
progress_model:
  type: staged_tags
  stages:
    - id: alpha
      name: Alpha Ready
      tag: AlphaReady
      target_count: 100
      done_states: [Done, Closed]
    - id: beta
      name: Beta Ready
      tag: BetaReady
      target_count: 200
```

### `weighted_workload`
Uses story points / effort weights. Completion = done weight ÷ total weight.

```yaml
progress_model:
  type: weighted_workload
  weight_field: story_points
  done_states: [Done, Closed]
  type_weights:
    "Product Backlog Item": 1.0
    "Bug": 0.5
```

### `manual_kpi`
For delivery where ADO doesn't capture true progress. DM supplies KPI values directly in the config.

```yaml
progress_model:
  type: manual_kpi
  kpis:
    - id: data_migration
      name: Data migration completeness
      weight: 0.5
      current: 60
      target: 100
    - id: integration_signoff
      name: Integration sign-offs
      weight: 0.5
      current: 3
      target: 5
```

---

## Project folder layout

```
projects/
  project-alpha/
    project.yaml              # project config (ADO, progress model, reporting)
    context/                  # living knowledge base — human-readable Markdown
      overview.md             # scope, objectives, client, stakeholders
      current_status.md       # current narrative delivery state
      milestones.md           # milestone list with targets and states
      risks.md                # risks with IDs, severity, aging
      decisions.md            # append-only decision log
      dependencies.md         # dependencies and blockers
      financials.md           # revenue context (TCV, monthly, at-risk)
      team.md                 # roster, roles, capacity
      delivery_notes.md       # rolling working notes
      conflicts.md            # auto-generated when contradictions detected
    input/                    # drop raw daily artifacts here
      2026-06-19-standup.md
    processed_input/          # archived inputs (timestamped per run)
      20260619T1432Z-9f2c/
    generated/                # latest generated artifacts
      slack_status.md
      change_summary_<run_id>.md
```

---

## Context update workflow (what happens on `project update`)

1. **Inventory** — reads all files from `input/`
2. **Classify & extract** — Claude (Haiku-class) extracts structured facts: status updates, new risks, decisions, milestone movements, blockers, asks
3. **Reconcile** — Claude (Sonnet-class) compares extracted facts against existing context and produces a surgical change set
4. **Conflict detection** — contradictions (e.g., two different milestone dates) are written to `conflicts.md` with full provenance; never silently merged
5. **Snapshot** — a full copy of `context/` + `metrics.json` is captured to `data/snapshots/<project>/<run_id>/` **before any write**
6. **Apply** — each context file is updated only where facts changed; front-matter (`last_updated`, `last_update_source`, `content_sha256`) is refreshed
7. **Persist** — snapshot row + metrics written to SQLite
8. **Archive** — processed input files moved to `processed_input/<timestamp>/`
9. **Change summary** — human-readable summary of what changed, what conflicted, and what needs DM attention

---

## Slack message examples

**Test-case milestone project (Yellow)**
```
Project Alpha — Status: Yellow
Progress: Alpha Ready is 78% complete, with 22 test cases remaining.
Next milestone: Alpha Ready targeted for July 12.
Key risk: Environment readiness may impact validation velocity.
Ask: Need client confirmation on UAT data availability by Friday.
```

**Stage/tag project (Green)**
```
Project Beta — Status: Green
Progress: Beta Ready stage is 64% complete (128/200 items); Alpha Ready done.
Next milestone: Beta Ready targeted for August 30 (on track).
Key risk: None blocking this week.
Ask: None.
```

**When Claude is unavailable (deterministic fallback)**
```
Project Alpha — Status: Yellow
Progress: Alpha Ready 78% (22 test cases remaining).
Next milestone: Alpha Ready — 2026-07-12.
Key risk: RISK-014 (high) — UAT environment readiness.
Ask: Confirm UAT data availability by Friday.
[Generated without narrative model; figures are computed.]
```

---

## Security model

- **Secrets never in YAML** — `pat_token: null` always; only env-var names are stored
- **Redaction filter** — installed on the root logger at startup; every log line is scanned and secrets replaced with `[REDACTED]`
- **Pre-write scanner** — every file write (context, reports, Slack output) is scanned before hitting disk; a secret-shaped string aborts the write
- **Data minimization** — Claude only receives computed facts (health, percent, milestone name, risk text); never raw ADO payloads, PATs, or API keys
- **`.gitignore`** — excludes `data/`, `reports/`, `projects/*/input/`, `projects/*/generated/`, `.env`, `*.pat`

---

## Claude provider configuration

The tool supports two modes, tried in order defined by `provider_priority`:

| Mode | When used | Configuration |
|------|-----------|--------------|
| `api_key` | `ANTHROPIC_API_KEY` env var is set | Set env var or `claude.api_key` in config (env var preferred) |
| `local_cli` | Claude CLI is installed and authenticated | `claude.local_cli_enabled: true` in config |

`vbu-agent doctor` reports which provider resolved and why others were skipped, without revealing secret values.

### Per-task model routing

Different tasks can use different Claude models to balance cost and quality:

```yaml
claude:
  model: claude-sonnet-4-6          # default for all tasks
  task_models:
    classify_input: claude-haiku-4-5-20251001   # high-volume, low-nuance
    reconcile_context: claude-sonnet-4-6         # needs judgment
    executive_summary: claude-sonnet-4-6         # highest-visibility prose
```

---

## Configuration reference

### `config/vbu-agent.yaml` (global)

```yaml
app:
  name: VBU-Projects-Agent
  environment: local               # local | staging | prod
  default_timezone: America/Costa_Rica

claude:
  provider_priority: [api_key, local_cli]
  api_key_env_var: ANTHROPIC_API_KEY
  api_key: null                    # never hardcode; use env var
  model: claude-sonnet-4-6
  max_tokens: 8000
  temperature: 0.2
  local_cli_enabled: true

storage:
  provider: sqlite
  sqlite_path: data/vbu_projects_agent.db
  snapshots_path: data/snapshots

projects:
  root_path: projects
  input_folder_name: input
  archive_folder_name: processed_input

reports:
  output_path: reports
  project_report_template: templates/project_status_report.html.j2
  executive_dashboard_template: templates/executive_dashboard.html.j2

slack:
  default_message_style: executive_short
  max_words: 180

ado:
  default_api_version: "7.1"
  batch_size: 200
  cache_ttl_seconds: 900
  max_retries: 3
```

### `projects/<id>/project.yaml` (per-project)

Key sections:

```yaml
project:
  id: project-alpha
  name: Project Alpha
  client: Example Client
  delivery_manager: Joseph
  health_thresholds:
    green: 0.85      # ≥ 85% = green
    yellow: 0.65     # ≥ 65% = yellow; below = red
    red: 0.0

azure_devops:
  organization: my-org
  project: MyADOProject
  base_url: https://dev.azure.com/my-org
  pat_env_var: PROJECT_ALPHA_ADO_PAT    # name of env var that holds the PAT
  pat_token: null                        # always null — PAT comes from env only

work_items:
  wiql: |
    SELECT [System.Id], [System.Title], [System.State], [System.Tags],
           [Microsoft.VSTS.Scheduling.StoryPoints]
    FROM WorkItems
    WHERE [System.TeamProject] = @project
      AND [System.WorkItemType] IN ('Product Backlog Item', 'Test Case')
      AND [System.State] <> 'Removed'

progress_model:
  type: test_case_milestones
  # ... (see Progress strategies section)

revenue:
  currency: USD
  total_contract_value: 600000
  monthly_revenue: 50000
  revenue_recognition_model: manual

reporting:
  include_risks: true
  include_financials: true
  include_velocity: true
  include_timeline: true

slack:
  tone: concise_executive
  include: [health, progress, next_milestone, risks, asks]
```

---

## MCP server (Claude Code integration)

The MCP server exposes project tools so Claude Code can operate on projects through typed contracts:

```bash
# Requires: pip install mcp
python -m vbu_projects_agent.mcp.server
```

The server is pre-registered in `.claude/settings.json`. Available tools:

| Tool | Description |
|------|-------------|
| `read_project_context` | Read all context/*.md files for a project |
| `write_project_context` | Surgical write to one context file (snapshot-guarded) |
| `list_project_input_files` | List pending input files |
| `archive_processed_input` | Move inputs to timestamped archive |
| `save_project_snapshot` | Persist a context + metrics snapshot |
| `query_project_history` | Time-series data for a project metric |

---

## Custom Claude Code slash commands

Five commands are available in `.claude/commands/` for use within Claude Code sessions:

| Command | Description |
|---------|-------------|
| `/update-project <id>` | Run daily context update workflow (dry-run first, then apply) |
| `/project-status <id>` | Get status, generate Slack message, optionally generate report |
| `/sync-ado <id>` | Pull latest ADO metrics for a project |
| `/onboard-project <id> <name>` | Walk through full project onboarding flow |
| `/portfolio-dashboard` | Build the executive portfolio dashboard |

---

## History and rollback

Every update and ADO sync is recorded. History enables:

- **Trends** — `history show --project <id> --metric overall_percent`
- **Velocity** — computed from `overall_percent` time-series using linear regression
- **Forecasts** — days remaining ÷ velocity + confidence score (high/medium/low)
- **Health evolution** — sequence of green/yellow/red changes over time
- **Revenue timeline** — monthly revenue captured per snapshot
- **Risk aging** — days-open tracked from `opened_at` through `last_seen_at`

Rollback to any previous state:

```bash
# Restore latest snapshot
vbu-agent project rollback --project project-alpha --snapshot latest

# Restore a specific run
vbu-agent project rollback --project project-alpha --snapshot 20260619T1432Z-9f2c
```

---

## Testing

```bash
# Run all tests
python3 -m pytest

# With coverage
python3 -m pytest --cov=vbu_projects_agent --cov-report=term-missing

# Specific test file
python3 -m pytest src/vbu_projects_agent/tests/test_progress.py -v
```

Test coverage:

| Area | Test file |
|------|-----------|
| Config validation | `test_config.py` |
| Security (redaction + scanner) | `test_security.py` |
| Context manager + scaffolder + conflicts | `test_context.py` |
| All 4 progress strategies + velocity + forecast + health | `test_progress.py` |
| Slack status skill + validators + numeric guard | `test_slack_skill.py` |
| SQLite storage + repositories + snapshots + rollback | `test_storage.py` |
| CLI integration (all commands) | `test_cli.py` |

No real ADO connection is needed for any test — the suite uses fixtures and `FakeClaudeProvider`.

---

## Source layout

```
vbu-projects-agent/
  pyproject.toml
  CLAUDE.md                         # Claude Code project context
  IMPLEMENTATION_RECORD.md          # Cross-machine continuity doc
  config/
    vbu-agent.yaml                  # Global config
  templates/
    project_status_report.html.j2  # Jinja2 project report template
    executive_dashboard.html.j2    # Jinja2 dashboard template
  .claude/
    settings.json                   # MCP server + permissions + hooks
    commands/                       # Custom slash commands
  src/vbu_projects_agent/
    cli.py                          # Typer command tree
    orchestrator.py                 # Workflow sequencer
    config/                         # Pydantic models + YAML loader
    claude/                         # ClaudeProvider (API key + local CLI)
    projects/                       # Context manager, update workflow, conflicts, scaffolder
    ado/                            # Azure DevOps client (WIQL, batch, cache, typed errors)
    progress/                       # 4 strategies + velocity + forecast + health
    storage/                        # SQLite DB, repositories, snapshot manager
    reporting/                      # HTML report + dashboard (Jinja2 + Plotly)
    skills/                         # Claude prose generators (Slack, summary, risks, forecast)
    agents/                         # Context curator, ADO metrics, status analyst
    security/                       # Redaction filter, pre-write scanner, secret patterns
    mcp/                            # MCP server + typed tool implementations
    tests/                          # pytest suite (88 tests, ~1s)
```

---

## Transferring to a new machine

See [IMPLEMENTATION_RECORD.md](IMPLEMENTATION_RECORD.md) for full details. Short version:

1. Copy project directory
2. `pip install -e ".[dev]"`
3. Set `ANTHROPIC_API_KEY` + `<PROJECT>_ADO_PAT` environment variables
4. Run `vbu-agent doctor` to verify everything resolves
5. Fill in real ADO values in `projects/<id>/project.yaml`
6. Run `vbu-agent project sync-ado --project <id>` to test ADO connectivity

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `pydantic` | Config models + validation |
| `anthropic` | Claude API SDK |
| `httpx` | ADO HTTP client |
| `jinja2` | HTML report templates |
| `plotly` | Interactive charts in reports |
| `pyyaml` | Config + front-matter parsing |
| `rich` | Terminal output formatting |
| `python-dateutil` | Date parsing utilities |

Dev/test: `pytest`, `pytest-mock`, `responses`, `freezegun`, `pytest-cov`

Optional: `mcp` (for MCP server mode — `pip install mcp`)
