# VBU-Projects-Agent — Implementation Record

> **Purpose:** Cross-machine continuity document. Read this before continuing implementation on a different machine or in a new Claude session.
> **Last updated:** 2026-06-19 (Mac implementation phase)
> **Author:** Joseph Cruz-Monge + Claude (personal account)

---

## Machine / Environment Context

| Item | Mac (current) | Windows (next) |
|------|---------------|----------------|
| OS | macOS 25.5 (Darwin) | Windows (work laptop) |
| Python | 3.13.4 | TBD — install 3.11+ |
| Claude account | Personal | Work |
| ADO access | ❌ Not available | ✅ Available |
| ADO PAT | Not set | Must set as env var |
| `ANTHROPIC_API_KEY` | Set (personal key) | Work API key |

---

## What Was Implemented (Mac phase — 2026-06-19)

All 10 phases from the implementation plan are scaffolded and coded. The following are **fully implemented with passing tests**:

### ✅ Phase 1 — Foundation
- `pyproject.toml` with all dependencies (typer, pydantic, anthropic, jinja2, plotly, httpx, pyyaml, rich)
- `config/vbu-agent.yaml` (global config example with all fields)
- `.gitignore` (excludes secrets, data, reports, generated artifacts)
- `src/vbu_projects_agent/config/models.py` — Pydantic v2 models for GlobalConfig and ProjectConfig
- `src/vbu_projects_agent/config/loader.py` — YAML loading + cross-field validation
- `src/vbu_projects_agent/security/patterns.py` — Anthropic key, ADO PAT, Bearer/Basic auth regexes
- `src/vbu_projects_agent/security/redaction.py` — RedactionFilter for logging, `register_secret()`, `redact()`
- `src/vbu_projects_agent/security/scanner.py` — `SecretScanner.safe_write()` (atomic write with pre-scan)
- CLI commands: `init`, `doctor`, `config validate`

### ✅ Phase 2 — Context Update Agent
- `src/vbu_projects_agent/projects/context_manager.py` — YAML front-matter parsing, SHA-256 hashes, surgical writes
- `src/vbu_projects_agent/projects/scaffolder.py` — `project create`, folder structure, default project.yaml
- `src/vbu_projects_agent/projects/conflicts.py` — `ConflictManager`, `CONFLICT-NNN` blocks in conflicts.md
- `src/vbu_projects_agent/projects/update_workflow.py` — Full §8 workflow (classify → extract → reconcile → snapshot → apply/dry-run/review → archive → summary)
- `src/vbu_projects_agent/storage/snapshots.py` — `SnapshotManager` (create, list, restore/rollback)
- CLI commands: `project create`, `project list`, `project validate`, `project update [--dry-run] [--review-required]`, `project rollback`

### ✅ Phase 3 — Azure DevOps Integration
- `src/vbu_projects_agent/ado/errors.py` — Typed ADO error hierarchy (PatMissing, AuthError, PatExpired, WiqlError, NetworkError)
- `src/vbu_projects_agent/ado/work_items.py` — `WorkItem` dataclass + field mapper
- `src/vbu_projects_agent/ado/wiql.py` — WIQL POST execution
- `src/vbu_projects_agent/ado/cache.py` — In-memory TTL cache
- `src/vbu_projects_agent/ado/client.py` — `AdoClient` (PAT from env, retries, batch ≤200, test_connectivity)
- CLI command: `project sync-ado [--no-cache]`
- **NOT tested against real ADO** — requires Windows machine

### ✅ Phase 4 — Progress Engine
- `src/vbu_projects_agent/progress/staged_tags.py` — Strategy 1: stage/tag-based
- `src/vbu_projects_agent/progress/test_case_milestones.py` — Strategy 2: test case passing milestones
- `src/vbu_projects_agent/progress/weighted_workload.py` — Strategy 3: story-point weighted
- `src/vbu_projects_agent/progress/manual_kpi.py` — Strategy 4: DM-entered KPIs
- `src/vbu_projects_agent/progress/velocity.py` — Linear regression on history
- `src/vbu_projects_agent/progress/forecast.py` — Deterministic date forecast + confidence scoring
- `src/vbu_projects_agent/progress/health.py` — Green/yellow/red with risk/blocker/velocity modifiers
- `src/vbu_projects_agent/progress/engine.py` — `ProgressEngine` strategy registry + `ProgressResult`

### ✅ Phase 5 — Slack Status Generation
- `src/vbu_projects_agent/skills/slack_status.py` — `generate_slack_status()` with retry + deterministic fallback
- `src/vbu_projects_agent/skills/validators.py` — `numeric_guard`, `word_count_check`, `section_check`, `secret_check`
- CLI command: `project slack-status [--style]`

### ✅ Phase 6 — Project HTML Reports
- `src/vbu_projects_agent/skills/executive_summary.py` — Claude-backed 3-5 sentence summary
- `src/vbu_projects_agent/skills/risk_analysis.py` — Prose risk narrative
- `src/vbu_projects_agent/skills/forecast_explanation.py` — Plain-language forecast explanation
- `src/vbu_projects_agent/reporting/view_models.py` — `ProjectReportVM`, `PortfolioDashboardVM`
- `src/vbu_projects_agent/reporting/charts.py` — Plotly progress/velocity/heatmap charts
- `src/vbu_projects_agent/reporting/report_builder.py` — `build_project_report()` (Jinja2 + built-in fallback)
- `templates/project_status_report.html.j2` — Full Jinja2 HTML template
- CLI command: `project report [--open]`

### ✅ Phase 7 — Executive Portfolio Dashboard
- `src/vbu_projects_agent/reporting/dashboard_builder.py` — `build_portfolio_dashboard()` + built-in HTML
- `templates/executive_dashboard.html.j2` — Jinja2 dashboard template
- CLI command: `dashboard generate [--refresh] [--open]`

### ✅ Phase 8 — MCP Tools and Agentic Enhancements
- `src/vbu_projects_agent/mcp/tools.py` — All 6 §16.4 tools (read/write context, list inputs, archive, snapshot, query history)
- `src/vbu_projects_agent/mcp/server.py` — MCP stdio server (requires `pip install mcp`)
- `.claude/settings.json` — MCP server registration + permissions
- `.claude/commands/` — 5 custom slash commands for DMs
- `CLAUDE.md` — Project context for Claude Code sessions
- CLI commands: `project ask`, `portfolio ask`

### ✅ Phase 9 — Security
- Redaction filter installed at startup in `orchestrator.py`
- `register_secret()` called before any PAT usage in `ado/client.py`
- `SecretScanner.safe_write()` used on every context, report, and Slack write
- `.gitignore` excludes all sensitive paths

### ✅ Phase 10 — Test Suite
- 88 tests, all passing (0.94s)
- `test_progress.py` — all 4 strategies, velocity, forecast, health (with golden numbers)
- `test_security.py` — redaction, scanner, atomic write safety
- `test_config.py` — global + project config validation
- `test_context.py` — context manager, scaffolder, conflicts
- `test_slack_skill.py` — validators, numeric guard, fallback, provider integration
- `test_storage.py` — DB init, repositories, snapshots, rollback
- `test_cli.py` — CLI integration via Typer CliRunner

### ✅ Storage Layer
- `src/vbu_projects_agent/storage/db.py` — SQLite + WAL + schema migrations
- `src/vbu_projects_agent/storage/repositories.py` — All 8 typed repositories
- CLI commands: `history show [--metric] [--since]`, `history export [--format json|csv]`

### ✅ Agent Layer
- `src/vbu_projects_agent/agents/context_curator.py` — Drives update workflow
- `src/vbu_projects_agent/agents/ado_metrics.py` — ADO sync → Progress Engine → metric persistence
- `src/vbu_projects_agent/agents/status_analyst.py` — Builds `ProjectStatusView` for reports

### ✅ Claude Provider
- `src/vbu_projects_agent/claude/provider.py` — `ClaudeProvider` Protocol + `resolve_provider()`
- `src/vbu_projects_agent/claude/api_key_provider.py` — Anthropic SDK API key provider
- `src/vbu_projects_agent/claude/local_cli_provider.py` — Local Claude CLI via subprocess
- `src/vbu_projects_agent/claude/routing.py` — Per-task model routing

---

## What Needs Testing on Windows

The following require real ADO access and should be tested on the Windows machine:

1. **ADO PAT resolution** — set `<PROJECT>_ADO_PAT` env var and run `vbu-agent doctor`
2. **`project sync-ado`** — run against a real ADO project; verify work items are fetched correctly
3. **WIQL customization** — adjust `project.yaml` WIQL for actual ADO project/organization
4. **Field mapping** — verify field names match the specific ADO instance (some orgs use custom fields)
5. **`vbu-agent project update`** — drop real standup notes into `input/` and run
6. **Slack status end-to-end** — after a real sync, generate and review the Slack message
7. **HTML report** — generate and open in browser; verify all sections render

---

## Known Issues / TODOs for Windows Session

1. **`mcp` package not installed** — `pip install mcp` needed to run the MCP server (optional)
2. **`plotly` CDN** — reports embed Plotly from CDN; offline viewing requires `embed_mode: inline` in config (note: inline Plotly is ~3MB per file)
3. **Windows path separators** — the code uses `pathlib.Path` throughout so should be fine, but verify `.claude/` folder is recognized by Claude Code on Windows
4. **Template validation** — run `vbu-agent config validate` on Windows; templates exist so no warnings expected
5. **`responses` library for ADO mocking** — currently unused in tests (mocking done via fixtures); ADO contract tests TBD
6. **`report_builder._builtin_html()`** — milestones are not yet passed through to the built-in report fallback; use the Jinja2 template for full output
7. **Claude model version** — currently set to `claude-sonnet-4-6`; work account may have access to different models; update `config/vbu-agent.yaml` as needed

---

## Setup Instructions for Windows

```powershell
# 1. Clone or copy the repo to Windows machine
# 2. Install Python 3.11+ and ensure it's on PATH

# 3. Create and activate venv
python -m venv .venv
.venv\Scripts\activate

# 4. Install the package
pip install -e ".[dev]"

# 5. Set environment variables (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."           # Work Claude API key
$env:PROJECT_ALPHA_ADO_PAT = "your-ado-pat"    # ADO PAT with Work Items: Read scope

# 6. Run doctor
vbu-agent --base-dir . doctor

# 7. Config validate
vbu-agent --base-dir . config validate

# 8. Create a project (or copy existing project.yaml from your ADO setup)
vbu-agent --base-dir . project create --project my-project --name "My Project"
# Then edit projects/my-project/project.yaml

# 9. Test ADO sync
vbu-agent --base-dir . project sync-ado --project my-project

# 10. Full daily workflow
# Drop standup notes into projects/my-project/input/
vbu-agent --base-dir . project update --project my-project --dry-run
vbu-agent --base-dir . project update --project my-project
vbu-agent --base-dir . project slack-status --project my-project
```

---

## Key Files to Adjust on Windows

| File | What to adjust |
|------|----------------|
| `config/vbu-agent.yaml` | `claude.model` (work account model access), `app.default_timezone` |
| `projects/<id>/project.yaml` | `azure_devops.organization`, `azure_devops.project`, `azure_devops.base_url`, `work_items.wiql`, milestone dates |
| `projects/<id>/project.yaml` | `progress_model.type` and milestone `target_passing` values matching your actual test case counts |

---

## Architecture Decisions to Preserve

1. **Never test Claude by putting secrets in prompts** — always use `register_secret()` + redaction
2. **Dry-run first, always** — before any real update on a new project, use `--dry-run`
3. **PAT only from env vars** — `pat_token: null` in YAML is intentional; never change this
4. **`ProgressEngine` is deterministic** — do not let Claude compute or modify numbers; only narrate
5. **Snapshot before every write** — the `SnapshotManager` is always called in `UpdateWorkflow` before `_apply_changes()`

---

## Test Coverage Summary

```
88 tests, 0 failures, 0 errors
Test areas: config, security, context, progress (all 4 strategies), 
            slack skill, storage, CLI integration
NOT covered yet: ADO live tests, HTML report rendering, dashboard rendering
```

---

*Generated by Claude (personal account) on Mac, 2026-06-19. Continue with work account on Windows.*
