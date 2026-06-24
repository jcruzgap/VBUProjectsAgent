# VBU-Projects-Agent — Claude Code Project Context

## What this project is

A Python CLI (`vbu-agent`) that helps Velocity Business Unit Delivery Managers maintain project context, measure delivery progress from Azure DevOps, and produce executive-ready Slack messages, HTML reports, and a portfolio dashboard.

## Key commands

```bash
# Setup
pip install -e ".[dev]"
vbu-agent init
vbu-agent config validate
vbu-agent doctor

# Daily DM workflow
vbu-agent project update --project <id> --dry-run   # preview
vbu-agent project update --project <id>              # apply
vbu-agent project slack-status --project <id>         # Slack message

# Weekly
vbu-agent project sync-ado --project <id>            # pull ADO metrics
vbu-agent project report --project <id> --open        # HTML report
vbu-agent dashboard generate --open                   # portfolio dashboard

# Management
vbu-agent project list
vbu-agent project rollback --project <id> --snapshot latest
vbu-agent history show --project <id>
```

## Architecture principles

1. **Deterministic core, generative edges** — metrics computed in Python; Claude writes prose only
2. **Config over code** — per-project behavior declared in `projects/<id>/project.yaml`
3. **Snapshot before write** — every update is reversible via `project rollback`
4. **Secrets never logged** — redaction filter installed on all log output; scanner blocks writes

## Source layout

```
src/vbu_projects_agent/
  cli.py             ← Typer command tree (entry point)
  orchestrator.py    ← sequences all workflows
  config/            ← Pydantic models + YAML loader
  claude/            ← ClaudeProvider protocol (API key + local CLI)
  projects/          ← context manager, update workflow, conflicts, scaffolder
  ado/               ← Azure DevOps client (WIQL, batch, field mapping)
  progress/          ← 4 progress strategies + velocity + forecast + health
  storage/           ← SQLite DB, repositories, snapshots
  reporting/         ← HTML report + dashboard builder (Jinja2 + Plotly)
  skills/            ← Claude-backed prose generators (Slack, summary, risks, forecast)
  agents/            ← higher-level agent orchestrations
  security/          ← redaction filter, pre-write scanner, secret patterns
  mcp/               ← MCP server exposing tools to Claude Code
  tests/             ← pytest suite
```

## MCP tools available (when server is running)

- `read_project_context` — read all context/*.md files for a project
- `write_project_context` — surgical write to one context file (snapshot-guarded)
- `list_project_input_files` — list pending input files
- `archive_processed_input` — move inputs to timestamped archive
- `save_project_snapshot` — persist a context snapshot
- `query_project_history` — time-series for a project metric

## Testing

```bash
pytest -q                          # run all tests
pytest -k "test_progress"         # specific subset
pytest --cov=vbu_projects_agent   # with coverage
```

## Key design rules for Claude Code

- Never hardcode secrets — use `claude.api_key_env_var` and `azure_devops.pat_env_var` in YAML
- All context writes go through `ContextManager.write_file()` which applies the secret scanner
- ADO PAT is registered with `register_secret()` before any HTTP call so it's always redacted
- Dry-run and review-required modes must be respected — never skip them
- Snapshots are immutable; rollback creates a new safety snapshot before restoring

## Current implementation status (as of 2026-06-19)

- [x] Phase 1: Foundation (config, security, CLI skeleton, doctor, logging)
- [x] Phase 2: Context Update Agent (context manager, update workflow, conflicts, snapshot/rollback)
- [x] Phase 3: ADO Integration (client, WIQL, batching, cache, typed errors)
- [x] Phase 4: Progress Engine (staged_tags, test_case_milestones, weighted_workload, manual_kpi)
- [x] Phase 5: Slack Status Generation (skill + validators + deterministic fallback)
- [x] Phase 6: Project HTML Reports (Jinja2 template + Plotly charts + validation)
- [x] Phase 7: Executive Portfolio Dashboard
- [x] Phase 8: MCP Tools and server
- [x] Phase 9: Security (redaction + scanner + patterns)
- [ ] Phase 10: pytest test suite (pending — see tests/)
- [ ] ADO live testing (requires Windows machine with work Claude account + ADO PAT)
