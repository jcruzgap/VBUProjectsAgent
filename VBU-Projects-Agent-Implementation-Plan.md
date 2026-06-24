# VBU-Projects-Agent Implementation Plan

> **Document type:** Engineering-ready implementation plan
> **Target audience:** Delivery Managers, Agentic Solutions Architects, Python developers, and Claude Code
> **Status:** Ready for implementation
> **Owner:** Velocity Business Unit (VBU) — Delivery Management

---

## 1. Executive Summary

`VBU-Projects-Agent` is a Python-based, Claude Code–powered agentic solution that standardizes how Delivery Managers (DMs) in the Velocity Business Unit maintain project context, ingest daily updates, measure delivery progress, and produce executive-ready communications.

The system is built around four pillars:

1. **A config-driven, per-project context model.** Every project lives in its own folder with structured Markdown context files and a `project.yaml` that declares how that project measures progress, where its Azure DevOps data lives, and how it should be reported.
2. **An agentic update workflow.** DMs drop raw daily artifacts (standup notes, client emails, ADO exports) into an `input/` folder. The agent reads, summarizes, reconciles, and surgically updates the correct context files — never blindly overwriting, always snapshotting first.
3. **A deterministic metrics core with AI-generated narrative.** All numbers (progress %, velocity, forecasts, health) are computed deterministically in Python from Azure DevOps and historical snapshots. Claude is used **only** to write prose: Slack messages, executive summaries, risk narratives, and forecast explanations. This separation makes outputs auditable and reproducible.
4. **Layered outputs.** From the same underlying state the system generates short executive Slack messages, interactive single-project HTML reports, and a cross-portfolio executive dashboard.

The solution supports two Claude access modes — a default **API key** mode and a **local Claude CLI/SDK fallback** — so it runs equally well in a DM's local environment or in a more controlled API-keyed setup. Historical data is persisted to SQLite plus JSON/Markdown snapshots, enabling trends, velocity, forecasts, health-change tracking, and revenue views over time.

The design deliberately **does not assume all projects measure progress the same way**. A pluggable Progress Measurement Engine supports stage/tag-based progress, test-case-passing milestones, weighted-workload (story-point) progress, and manual KPI progress — selectable per project via `project.yaml`.

---

## 2. Goals and Non-Goals

### 2.1 Goals

- Provide a **single, repeatable standard** every VBU Delivery Manager can adopt for project context management and executive reporting.
- Keep project context **continuously current** through a low-friction "drop files in a folder, run one command" workflow.
- Make all delivery metrics **deterministic, configurable, and auditable**, with AI confined to narrative generation.
- Support **heterogeneous progress models** so each project measures delivery the way that genuinely reflects its work.
- Produce **three tiers of output** (Slack one-liner, project HTML report, portfolio dashboard) from one source of truth.
- Maintain **full history** for trends, velocity, forecasting, health evolution, risk aging, and revenue timelines.
- Treat **secrets as first-class hazards**: never log, never embed in reports, never commit.
- Be **safe by default**: snapshot-before-write, dry-run, review-required, and rollback are core, not afterthoughts.

### 2.2 Non-Goals

- **Not** a replacement for Azure DevOps as the system of record for work items. ADO remains authoritative; this agent reads and summarizes.
- **Not** an automated decision-maker. It surfaces information and drafts language; humans approve and act.
- **Not** a real-time monitoring system. It operates on a pull/refresh cadence (on-demand or scheduled), not streaming.
- **Not** a multi-tenant SaaS in v1. It is a local/single-DM tool with a clean path to shared hosting later.
- **Not** responsible for **posting** to Slack in v1 (copy-ready output only). Optional posting is a future enhancement.
- **Not** a financial system. Revenue figures are DM-entered context, not derived from billing systems.

---

## 3. Target Users and Use Cases

### 3.1 Primary user: the Delivery Manager

A VBU DM typically owns one to several projects, attends daily standups, fields client emails, and is repeatedly asked for status by Account Executives, Delivery Directors, and executives. The DM's pain is **synthesis under time pressure** — turning scattered daily signals into a crisp, trustworthy status.

### 3.2 Secondary consumers

- **Account Executives / Delivery Directors** — read Slack status and HTML reports.
- **Executives** — consume the portfolio dashboard and Slack summaries.
- **The DM's future self** — relies on history to answer "how did we get here?" and "are we trending up or down?".

### 3.3 Representative use cases

| # | Use case | Command(s) |
|---|----------|-----------|
| UC-1 | Onboard a new project into the standard | `project create`, `project validate` |
| UC-2 | Ingest today's signals and refresh context | `project update --project X` |
| UC-3 | Preview changes before committing them | `project update --project X --dry-run` |
| UC-4 | Pull latest delivery metrics from ADO | `project sync-ado --project X` |
| UC-5 | Draft an executive Slack status | `project slack-status --project X` |
| UC-6 | Produce an interactive status report | `project report --project X` |
| UC-7 | Produce the portfolio dashboard | `dashboard generate` |
| UC-8 | Ask a natural-language question of one project | `project ask --project X "..."` |
| UC-9 | Ask across the portfolio | `portfolio ask "..."` |
| UC-10 | Inspect or export history | `history show`, `history export` |
| UC-11 | Recover from a bad update | `project rollback --project X --snapshot latest` |
| UC-12 | Diagnose environment / config problems | `doctor`, `config validate` |

---

## 4. High-Level Architecture

### 4.1 Architectural principles

1. **Deterministic core, generative edges.** Metrics are computed; prose is generated. Never let the model invent a number.
2. **Config over code.** Per-project behavior (queries, progress model, thresholds, reporting) is declared in YAML, not hardcoded.
3. **Files are the interface.** Markdown context files are human-readable, diff-able, and git-friendly. The DM can always read and hand-edit them.
4. **Snapshot before mutate.** No update path writes context without first capturing a restorable snapshot.
5. **Fail safe and loud.** Bad PATs, bad WIQL, empty results, and schema violations produce clear, actionable errors — never silent corruption.

### 4.2 Component overview

```
                          ┌─────────────────────────────────────────┐
                          │                  CLI                     │
                          │            (Typer command tree)          │
                          └───────────────────┬─────────────────────┘
                                              │
                ┌─────────────────────────────┼─────────────────────────────┐
                │                             │                             │
        ┌───────▼────────┐          ┌─────────▼─────────┐         ┌─────────▼─────────┐
        │  Config Layer  │          │   Orchestrator    │         │  Security Layer   │
        │ global + proj  │          │ (workflow engine) │         │ redaction/scan    │
        │   validation   │          └─────────┬─────────┘         └───────────────────┘
        └────────────────┘                    │
                ┌────────────────┬─────────────┼──────────────┬────────────────┐
                │                │             │              │                │
        ┌───────▼──────┐ ┌───────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌───────▼──────┐
        │  ADO Client  │ │  Progress    │ │ Context  │ │  Storage    │ │  Claude      │
        │ WIQL/batch   │ │  Engine      │ │ Manager  │ │ SQLite +    │ │  Provider    │
        │ field map    │ │ (pluggable)  │ │ MD files │ │ snapshots   │ │ api/cli      │
        └──────────────┘ └──────────────┘ └──────────┘ └─────────────┘ └──────────────┘
                                              │
                ┌─────────────────────────────┼─────────────────────────────┐
                │                             │                             │
        ┌───────▼────────┐          ┌─────────▼─────────┐         ┌─────────▼─────────┐
        │ Slack Writer   │          │ HTML Report Gen   │         │ Portfolio Dash    │
        │ (skill)        │          │ (Jinja2+Plotly)   │         │ Generator         │
        └────────────────┘          └───────────────────┘         └───────────────────┘
```

### 4.3 Data flow (update path)

```
input/*.md ──► Context Curator Agent ──► proposed diffs
                       │                       │
                       ▼                       ▼
              snapshot (pre-update)    conflict detection
                       │                       │
                       ▼                       ▼
            write context/*.md  ◄── human review gate (optional)
                       │
                       ▼
        persist snapshot row + metrics to SQLite
                       │
                       ▼
            move input/* ──► processed_input/<timestamp>/
                       │
                       ▼
                change summary
```

### 4.4 Agentic execution model

The orchestrator is plain Python and remains in control of the workflow. Claude is invoked through a **provider abstraction** for discrete, well-scoped tasks (summarize input, reconcile context, write Slack message, explain a forecast). Agents and skills are prompt + tool contracts rather than long-running autonomous loops; this keeps behavior predictable and testable.

---

## 5. Claude Access Strategy

### 5.1 Two modes, one interface

All Claude usage goes through a single `ClaudeProvider` interface so the rest of the codebase never cares which mode is active:

```python
class ClaudeProvider(Protocol):
    def complete(self, *, system: str, prompt: str,
                 max_tokens: int, temperature: float,
                 model: str | None = None) -> ClaudeResult: ...

    @property
    def mode(self) -> Literal["api_key", "local_cli"]: ...
```

Two concrete implementations:

- `ApiKeyProvider` — uses the Anthropic Python SDK with a key resolved from config/env.
- `LocalCliProvider` — shells out to the local Claude CLI / SDK using the user's existing credentials (no key needed in this tool).

### 5.2 Mode detection and fallback

Resolution order is driven by `claude.provider_priority` (default `[api_key, local_cli]`):

```
For each provider in provider_priority:
    api_key:
        key = config.claude.api_key
              or os.environ[config.claude.api_key_env_var]
        if key is non-empty and well-formed:
            return ApiKeyProvider(key)
    local_cli:
        if config.claude.local_cli_enabled
           and claude CLI is discoverable on PATH
           and a lightweight auth probe succeeds:
            return LocalCliProvider()
If none resolve:
    raise ClaudeProviderUnavailable with remediation guidance
```

Key rules:

- **No secrets hardcoded.** `claude.api_key` defaults to `null`; the env var name is configurable via `claude.api_key_env_var` (default `ANTHROPIC_API_KEY`).
- **Well-formed check** validates shape only (non-empty, expected prefix), never logs the value.
- **Auth probe** for local CLI is a cheap `claude --version` / minimal call so failures surface at startup, not mid-workflow.
- `vbu-agent doctor` reports the resolved mode and the reason others were skipped (without revealing secret values).

### 5.3 Model selection and routing

`claude.model` sets the default (`claude-sonnet-4-5`). The provider supports a **per-task model override** so cheap/structural tasks can route to a smaller model and synthesis tasks to a larger one:

| Task | Suggested tier | Rationale |
|------|----------------|-----------|
| Input file classification / extraction | Haiku-class | High volume, low nuance |
| Context reconciliation & conflict detection | Sonnet-class | Needs judgment, moderate volume |
| Executive summary / forecast narrative | Sonnet- or Opus-class | Highest-visibility prose |

Routing is config-overridable; the default keeps everything on the configured `claude.model` for simplicity.

### 5.4 Determinism guardrails

- Default `temperature: 0.2` for reproducible, low-variance prose.
- Numeric facts are injected into prompts as **pre-computed values**; prompts instruct the model to use only provided figures and never compute or invent numbers.
- A post-generation validation step (see §12, §19) checks that generated text does not introduce numbers absent from the supplied context.

---

## 6. Configuration Design

### 6.1 Global configuration file

Located at `config/vbu-agent.yaml`. Full example in **Appendix A**. Structure:

```yaml
app:
  name: VBU-Projects-Agent
  environment: local
  default_timezone: America/Costa_Rica
claude:
  provider_priority: [api_key, local_cli]
  api_key_env_var: ANTHROPIC_API_KEY
  api_key: null
  model: claude-sonnet-4-5
  max_tokens: 8000
  temperature: 0.2
  local_cli_enabled: true
storage:
  provider: sqlite
  sqlite_path: data/vbu_projects_agent.db
  snapshots_path: data/snapshots
  artifacts_path: artifacts
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
```

### 6.2 Validation rules (global)

Validation is performed with **Pydantic** models at load time. `vbu-agent config validate` runs these and exits non-zero on any failure.

| Field | Rule |
|-------|------|
| `app.name` | Non-empty string. |
| `app.environment` | One of `local`, `staging`, `prod`. |
| `app.default_timezone` | Must be a valid IANA timezone (validated via `zoneinfo`). |
| `claude.provider_priority` | Non-empty list; each item in `{api_key, local_cli}`; no duplicates. |
| `claude.api_key_env_var` | Valid env-var name (`^[A-Z_][A-Z0-9_]*$`). |
| `claude.api_key` | `null` or string; if a literal key is present, emit a **warning** recommending env-var use. |
| `claude.model` | Non-empty string. |
| `claude.max_tokens` | Integer in `[256, 64000]`. |
| `claude.temperature` | Float in `[0.0, 1.0]`. |
| `claude.local_cli_enabled` | Boolean. |
| `storage.provider` | Currently must be `sqlite`. |
| `storage.sqlite_path` | Parent directory creatable/writable. |
| `storage.snapshots_path` / `artifacts_path` | Creatable/writable directories. |
| `projects.root_path` | Existing or creatable directory. |
| `projects.input_folder_name` / `archive_folder_name` | Safe folder names (no path separators). |
| `reports.output_path` | Creatable/writable. |
| `reports.*_template` | Template file must exist and parse as valid Jinja2. |
| `slack.default_message_style` | One of the registered styles. |
| `slack.max_words` | Integer in `[40, 400]`. |

Cross-field rule: if `provider_priority` contains `api_key` but neither `api_key` nor the env var is set **and** `local_cli` is absent or disabled, `config validate` warns that no Claude provider will resolve.

### 6.3 Configuration precedence

`CLI flags` > `environment variables` > `config/vbu-agent.yaml` > `built-in defaults`. Project-level YAML overrides global only for the fields it owns (e.g., timezone, reporting toggles).

---

## 7. Project Folder and Context Model

### 7.1 Folder layout

Each project is a self-contained folder under `projects/`:

```
projects/
  project-alpha/
    project.yaml              # project config (see §6 / Appendix B)
    context/                  # the living, human-readable knowledge base
      overview.md             # what the project is, scope, stakeholders
      current_status.md       # the current narrative state of delivery
      milestones.md           # milestone list, targets, status
      risks.md                # active risks (with IDs, severity, aging)
      decisions.md            # decision log
      dependencies.md         # internal/external dependencies & blockers
      financials.md           # revenue, TCV, run-rate context
      team.md                 # roster, roles, capacity notes
      delivery_notes.md       # rolling working notes / scratchpad
      conflicts.md            # auto-generated when contradictions detected
    input/                    # DM drops raw daily artifacts here
      2026-06-19-standup-notes.md
      2026-06-19-client-email-summary.md
      2026-06-19-ado-export.md
    processed_input/          # archived inputs, timestamped per run
      2026-06-19T1432Z/
    generated/                # latest generated artifacts
      slack_status.md
      status_report.html
```

### 7.2 Purpose of each context file

| File | Purpose | Typical update trigger |
|------|---------|------------------------|
| `overview.md` | Stable description: scope, objectives, client, key stakeholders. | Rarely; scope changes. |
| `current_status.md` | The single best paragraph(s) describing where delivery stands now. | Most updates. |
| `milestones.md` | Structured milestone list with target dates and states. | Milestone movement, re-planning. |
| `risks.md` | Active risks with `RISK-NNN` IDs, severity, owner, opened date, last-seen date. | New risks, mitigation, closure. |
| `decisions.md` | Append-mostly decision log: `DEC-NNN`, date, decision, rationale. | When decisions are made. |
| `dependencies.md` | Dependencies and blockers, with status and owner. | New/cleared blockers. |
| `financials.md` | Revenue context: TCV, monthly revenue, revenue-at-risk notes. | Commercial changes. |
| `team.md` | Roster, roles, capacity/availability notes. | Staffing changes. |
| `delivery_notes.md` | Rolling working notes that don't fit elsewhere. | Frequently; low ceremony. |
| `conflicts.md` | Auto-written when new input contradicts existing context. | Conflict detection only. |

### 7.3 Context file conventions

- Each context file begins with a YAML front-matter block carrying `last_updated`, `last_update_source`, and a content hash:

```markdown
---
last_updated: 2026-06-19T14:32:00-06:00
last_update_source: 2026-06-19-standup-notes.md
content_sha256: 9f2c...e1
---
# Current Status
...
```

- Structured files (`risks.md`, `decisions.md`, `milestones.md`) use stable, parseable item blocks so the deterministic core can read them back:

```markdown
## RISK-014  (severity: high, status: open)
- opened: 2026-06-02
- last_seen: 2026-06-19
- owner: Joseph
- description: UAT environment readiness may delay validation.
- mitigation: Escalated to client infra team; awaiting ETA.
```

- The agent **edits surgically**: it modifies only the blocks affected by new input and preserves everything else verbatim, updating front-matter and hashes.

### 7.4 Input and archive model

- The DM places any number of `.md`, `.txt`, `.csv`, or exported files in `input/`.
- On a successful (non-dry-run) update, processed files are moved to `processed_input/<UTC timestamp>/` so `input/` is always "what's pending."
- The original bytes are preserved on archive (never rewritten), giving a verifiable audit trail of what drove each change.

---

## 8. Project Update Workflow

### 8.1 Command surface

```
vbu-agent project update --project project-alpha
vbu-agent project update --project project-alpha --dry-run
vbu-agent project update --project project-alpha --review-required
```

### 8.2 Step-by-step workflow

1. **Load & validate** the project's `project.yaml` and the global config. Abort early on schema errors.
2. **Inventory input.** Read all files in `input/`. Classify each (standup notes, client email, ADO export, freeform) using a Haiku-class call; large/binary/unsupported files are flagged, not parsed blindly.
3. **Summarize & extract.** Produce a structured, per-file extraction of facts, changes, new risks, decisions, milestone movements, and asks.
4. **Load current context.** Parse all `context/*.md` into in-memory structures (status text, risk blocks, decision blocks, milestones).
5. **Reconcile.** For each extracted fact, determine whether it is *new*, *an update to existing context*, *a confirmation*, or *a contradiction*. This is the core agentic step (Sonnet-class), constrained to output a structured change set, not free-form rewrites.
6. **Detect conflicts.** Any contradiction (e.g., new date conflicts with `milestones.md`) is recorded in `context/conflicts.md` with both versions and provenance, and flagged in the change summary.
7. **Snapshot (pre-update).** Capture a full copy of `context/` plus a metrics snapshot to `data/snapshots/<project>/<run_id>/` and a `project_snapshots` row. **This always happens before any write.**
8. **Apply changes.**
   - *Dry-run:* render the proposed diff to stdout and `generated/update_preview.md`; write nothing to `context/`.
   - *Review-required:* render the diff and pause for explicit approval (interactive confirm or an approval token); apply only on approval.
   - *Default:* apply surgical edits to the affected context files, updating front-matter + hashes.
9. **Persist history.** Write a `project_snapshots` record and any derived `project_metrics`, `milestone_snapshots`, `risks`, `decisions` rows.
10. **Archive input.** Move processed files to `processed_input/<timestamp>/`.
11. **Emit change summary.** Human-readable summary of what changed, what conflicted, and what needs DM attention; also stored as a generated artifact.

### 8.3 Modes

| Mode | Writes context? | Archives input? | Use when |
|------|-----------------|-----------------|----------|
| Default | Yes | Yes | Routine trusted updates. |
| `--dry-run` | No | No | Preview the agent's proposed changes. |
| `--review-required` | Only after approval | Only after approval | Sensitive projects / high-stakes weeks. |

### 8.4 Idempotency & safety

- A **stable `run_id`** (UTC timestamp + short hash of input filenames+sizes) ties together the snapshot, DB rows, archive folder, and change summary.
- Re-running with the same unchanged inputs is detected and short-circuited ("no new input").
- All writes are snapshot-guarded, so any update is reversible via `project rollback`.

### 8.5 Conflict handling detail

A conflict block in `context/conflicts.md`:

```markdown
## CONFLICT-2026-06-19-01  (status: unresolved)
- field: milestones.alpha_ready.target_date
- existing: 2026-07-12  (source: milestones.md, 2026-06-10)
- incoming: 2026-07-19  (source: 2026-06-19-client-email-summary.md)
- note: Client email implies a one-week slip; not yet confirmed in ADO.
- recommended_action: Confirm with AE before updating milestone target.
```

The agent **does not silently pick a winner** on contradictions; it preserves both, flags the conflict, and leaves resolution to the DM.

---

## 9. Azure DevOps Integration

### 9.1 Responsibilities

The ADO module turns a project's declarative config into work-item data the Progress Engine can consume, while guaranteeing PAT safety.

Modules:

- `ado/client.py` — HTTP client, auth, retries.
- `ado/wiql.py` — WIQL execution and ID pagination.
- `ado/work_items.py` — batched detail fetch + field mapping.
- `ado/cache.py` — response caching.
- `ado/errors.py` — typed, actionable errors.

### 9.2 PAT token handling

- The PAT is **never** stored in `project.yaml`. The YAML references an env-var name only (`azure_devops.pat_env_var`), with `pat_token: null`.
- Resolution: read `os.environ[pat_env_var]`; if absent, raise `AdoPatMissing` with remediation text (which env var to set), never echoing any value.
- The PAT is used solely as an HTTP basic-auth secret and is held in memory only for the request lifetime.
- The secret-redaction hook (§20) guarantees the PAT cannot appear in logs, errors, snapshots, or reports.

### 9.3 WIQL execution and batching

1. POST the project's `work_items.wiql` to `/_apis/wit/wiql?api-version=<v>`.
2. Collect returned work-item IDs.
3. Fetch details in **batches of ≤200 IDs** via `/_apis/wit/workitemsbatch`, requesting only the fields named in the field mapping (minimizes payload and data exposure).
4. Map raw fields → normalized internal model using the configurable field map.

```python
@dataclass(frozen=True)
class WorkItem:
    id: int
    title: str
    state: str
    tags: tuple[str, ...]
    story_points: float | None
    work_item_type: str
    raw: dict  # retained only in-memory; never serialized to reports
```

### 9.4 Configurable field mapping

Defaults map common ADO reference names; projects can override:

```yaml
field_mappings:
  id: System.Id
  title: System.Title
  state: System.State
  tags: System.Tags
  story_points: Microsoft.VSTS.Scheduling.StoryPoints
  work_item_type: System.WorkItemType
```

Tags are split on `;` and trimmed into a normalized set.

### 9.5 Caching strategy

- Keyed on `(project_id, sha256(wiql), field_map_hash, api_version)`.
- TTL configurable (default 15 minutes); `--no-cache` and `sync-ado` bypass/refresh.
- Cache stores normalized work items only (never PATs, never raw auth headers).

### 9.6 Error handling matrix

| Condition | Detection | Behavior |
|-----------|-----------|----------|
| Missing PAT | env var unset | `AdoPatMissing`; remediation text; exit non-zero. |
| Bad/invalid PAT | HTTP 401/403 | `AdoAuthError`; advise PAT regeneration/scopes; **no value logged**. |
| Expired PAT | HTTP 401 + ADO signal | `AdoPatExpired`; advise renewal. |
| Bad WIQL | HTTP 400 + WIQL error body | `AdoWiqlError` with sanitized server message and the offending query echoed back (no secrets). |
| Network failure / timeout | exception / 5xx | Retry with backoff (max 3); then `AdoNetworkError`; suggest `doctor`. |
| Empty result set | 0 IDs returned | Not an error: return empty set; Progress Engine yields 0% with a "no items matched" note. |
| Rate limiting | HTTP 429 | Honor `Retry-After`; backoff; surface if persistent. |

### 9.7 Security rules

- PATs are redacted from every log line, exception message, snapshot, and report (enforced centrally, see §20).
- Only mapped fields are requested from ADO.
- Raw ADO payloads stay in memory; persisted history stores normalized metrics, not raw item dumps containing potentially sensitive titles unless `reporting` explicitly permits.

---

## 10. Progress Measurement Engine

### 10.1 Design: pluggable strategies

Progress is **not** one-size-fits-all. The engine defines a strategy interface; each project's `progress_model.type` selects an implementation. All strategies consume normalized `WorkItem`s plus historical snapshots and emit a common `ProgressResult`.

```python
class ProgressStrategy(Protocol):
    type: str
    def compute(self, items: list[WorkItem],
                config: ProgressModelConfig,
                history: list[MetricSnapshot]) -> ProgressResult: ...

@dataclass
class ProgressResult:
    overall_percent: float
    stages: list[StageProgress]        # may be empty
    active_stage: str | None
    health: Literal["green", "yellow", "red"]
    velocity: VelocityResult | None
    forecast: ForecastResult | None
    notes: list[str]
    measured_at: datetime
```

Strategies register by `type`, so adding a new model is a self-contained class + tests.

### 10.2 Strategy 1 — Stage/Tag-Based Progress (`staged_tags`)

For PBIs grouped into stages by tags. Per stage, computes total items (or `target_count`), completed items (state in `done_states` **and** carrying the stage tag), percent complete, the active stage (first non-complete), and per-stage health vs. thresholds. Overall progress is a weighted roll-up across stages.

```python
stage_completed = sum(
    1 for wi in items
    if stage.tag in wi.tags and wi.state in stage.done_states
)
denominator = stage.target_count or stage_total_tagged
stage_percent = (stage_completed / denominator) if denominator else 0.0
```

### 10.3 Strategy 2 — Test-Case-Passing Milestones (`test_case_milestones`)

For milestones defined as "N passing test cases" (e.g., Alpha=100, Beta=200, Production=300). Computes passing test cases (Test Case items in a passing/done state), remaining to target, completion %, **velocity** from historical snapshots, and a **forecast** completion date.

```
passing            = count(Test Case items with state in done_states)
remaining          = max(target - passing, 0)
completion_percent = min(passing / target, 1.0) * 100

# velocity from history (passing cases gained per day)
velocity_per_day   = linear_fit_slope(history.passing_over_time)   # robust to noise
forecast_date      = today + ceil(remaining / velocity_per_day) days   # if velocity > 0
forecast_confidence = f(history_points, variance, recency)
```

Velocity uses a robust fit over a configurable trailing window; forecast is suppressed (with a note) when history is insufficient or velocity ≤ 0.

### 10.4 Strategy 3 — Weighted Workload (`weighted_workload`)

Uses story points / effort / configured weights. Percent complete = completed weight ÷ total weight. Supports per-type weighting and optional capacity-based velocity. Useful for backlog-burndown-style projects.

```python
total_weight     = sum(weight_of(wi) for wi in items)
completed_weight = sum(weight_of(wi) for wi in items if wi.state in done_states)
overall_percent  = (completed_weight / total_weight * 100) if total_weight else 0.0
```

### 10.5 Strategy 4 — Manual KPI (`manual_kpi`)

For delivery whose true progress ADO doesn't capture. The DM defines KPIs in `project.yaml` and supplies values via context/input; the engine normalizes them to a 0–100 scale and rolls up by weight.

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

### 10.6 Health scoring

Health derives from `project.health_thresholds` applied to overall progress **and** modifiers (open high-severity risks, negative velocity trend, active blockers). The result is one of green/yellow/red plus the reasons, which feed Slack and reports. Health changes are persisted so the dashboard can show trajectory.

### 10.7 Velocity & forecasting (shared)

- Velocity and forecasts are computed **only** from persisted snapshots, making them reproducible and inspectable.
- Forecasts always carry a **confidence score** (see §25) reflecting history depth, variance, and recency.
- All forecasting is deterministic math; Claude only *explains* it (Forecast Explanation Skill, §19).

---

## 11. Historical Storage and Snapshot Model

### 11.1 Storage approach

- **SQLite** (`data/vbu_projects_agent.db`) for queryable, structured history.
- **JSON + Markdown snapshots** under `data/snapshots/<project>/<run_id>/` for auditability and rollback (full context copy + a `metrics.json`).

History is written on every context update **and** every ADO sync, so trends, velocity, health changes, milestone progress, forecasts, risk evolution, and revenue timelines are all reconstructable.

### 11.2 What a snapshot contains

```
data/snapshots/project-alpha/2026-06-19T1432Z-9f2c/
  context/                 # verbatim copy of all context/*.md at snapshot time
  metrics.json             # ProgressResult + raw counts + health + revenue
  meta.json                # run_id, mode, provider, source files, hashes
```

### 11.3 Tables (overview; full DDL in §18)

| Table | Purpose |
|-------|---------|
| `projects` | Registry of known projects and current metadata. |
| `project_snapshots` | One row per update/sync run; links to snapshot folder. |
| `project_metrics` | Time-series of computed metrics per snapshot. |
| `milestone_snapshots` | Per-milestone state/percent over time. |
| `risks` | Risk records with open/close dates for aging & evolution. |
| `decisions` | Decision log entries. |
| `generated_artifacts` | Index of generated Slack/HTML/dashboard outputs. |
| `ado_sync_runs` | ADO sync attempts, outcomes, item counts, errors. |

### 11.4 How history is reused

| Output | History used |
|--------|--------------|
| Velocity | `project_metrics` time-series (passing cases / completed weight over time). |
| Forecast | velocity + remaining work; `milestone_snapshots` for milestone-specific forecasts. |
| Trend charts | `project_metrics`, `milestone_snapshots`. |
| Health change | sequence of health values in `project_snapshots`/`project_metrics`. |
| Risk aging / evolution | `risks.opened_at` vs `last_seen_at`, status transitions. |
| Revenue timeline | revenue fields captured per snapshot in `project_metrics`. |
| Data-quality / missing-info | completeness flags stored per snapshot. |

### 11.5 Retention & integrity

- Snapshots are immutable once written; rollback restores from them but never edits them.
- Content hashes (front-matter `content_sha256`) let the system detect tampering or drift.
- Optional pruning policy keeps all DB rows but compresses/ages old snapshot folders (configurable; default: keep everything).

---

## 12. Slack Status Generation

### 12.1 Command

```
vbu-agent project slack-status --project project-alpha
```

Output is written to `generated/slack_status.md` and printed copy-ready to stdout.

### 12.2 Requirements

The message must be short, executive, clear, copy-ready, and appropriate for an executive Slack channel, focused on **health, progress, next milestone, risks/blockers, and asks**. Word count is capped by `slack.max_words` (global) and refined by per-project `slack` settings.

### 12.3 Example output

```
Project Alpha — Status: Yellow
Progress: Alpha Ready is 78% complete, with 22 test cases remaining.
Next milestone: Alpha Ready targeted for July 12.
Key risk: Environment readiness may impact validation velocity.
Ask: Need client confirmation on UAT data availability by Friday.
```

### 12.4 Slack Status Writer Skill

A dedicated skill (prompt + validators) governs generation:

- **Inputs (all pre-computed):** project name, health + reasons, progress object, next milestone + target/forecast date, top risks, open asks.
- **Prompt template:** see §19.2. Instructs the model to use only supplied figures, hit the structure (Status / Progress / Next milestone / Key risk / Ask), and stay within the word budget.
- **Tone control:** `slack.tone` (e.g., `concise_executive`) maps to a tone directive.
- **Output validation:**
  - Word count ≤ `max_words`.
  - Required sections present (health line + at least progress + next milestone).
  - **Numeric guard:** every number in the output must appear in the supplied inputs; otherwise reject and regenerate (max N retries), then fall back to a deterministic template.
  - No secrets / no raw work-item titles unless permitted.
- **Determinism:** temperature pinned low; deterministic template fallback guarantees an output even if the model is unavailable.

### 12.5 Failure behavior

If Claude is unavailable, the skill emits a deterministic, template-filled message (clearly all figures are real/computed) so the DM is never blocked.

---

## 13. Interactive Project Status Reports

### 13.1 Command

```
vbu-agent project report --project project-alpha
```

Output: `reports/project-alpha/status_report_2026-06-19.html` (standalone, self-contained HTML).

### 13.2 Report contents

1. Executive summary (Claude-written from computed facts).
2. Health status (with reasons and trajectory).
3. Timeline and milestones.
4. Current milestone progress.
5. Azure DevOps metrics.
6. Risks and blockers (with aging).
7. Decisions.
8. Dependencies.
9. Revenue information (if `reporting.include_financials`).
10. Historical trend charts.
11. Velocity charts.
12. Forecasts (when enough history exists; otherwise a clear "insufficient history" note).
13. Last-update timestamp + provenance.

### 13.3 Implementation

- **Jinja2** templates (`templates/project_status_report.html.j2`).
- **Plotly** for interactive trend/velocity/forecast charts, embedded inline so the HTML is standalone (no external CDN dependency required for offline viewing; CDN optional via config).
- **Bootstrap / lightweight CSS** for layout; print-friendly.
- Charts are built from `project_metrics` / `milestone_snapshots`; the template receives a fully-resolved view-model (no live queries at render time).

### 13.4 Report validation

A report-validation hook (§16) checks: required sections rendered, no secret patterns present, all numeric claims trace to the view-model, and the file is valid standalone HTML before it is written to `reports/`.

---

## 14. Executive Portfolio Dashboard

### 14.1 Command

```
vbu-agent dashboard generate
```

Output: `reports/executive_dashboard_2026-06-19.html`.

### 14.2 Dashboard contents

1. Portfolio health (roll-up).
2. All active projects with at-a-glance health.
3. Health per project (current + trend arrow).
4. Milestone timeline across projects.
5. Revenue view (and revenue-at-risk).
6. Risks requiring executive attention (high-severity, aging, or escalated).
7. Projects trending negatively (health/velocity decline).
8. Blocked projects.
9. Recent changes (last-update digest per project).
10. Forecasted milestone dates.

### 14.3 Aggregation logic

- Iterates all projects under `projects.root_path`, loading each project's latest snapshot + recent history (no recomputation of stale data unless `--refresh` is passed, which runs `sync-ado` per project first).
- Produces a **portfolio heatmap** (project × dimension: health, schedule, risk, velocity).
- Computes **revenue-at-risk** = sum of monthly/▲revenue on projects flagged yellow/red, surfaced explicitly for executives.
- Highlights **negative trends** using the same velocity/health history that powers per-project reports.

### 14.4 Implementation

Same stack as project reports (Jinja2 + Plotly + lightweight CSS), with a dashboard-specific template and a portfolio view-model assembled from each project's persisted metrics.

---

## 15. CLI Design

### 15.1 Framework

Built with **Typer** (Click under the hood) for typed commands, subcommand groups, and auto-generated help. Command groups: root, `project`, `dashboard`, `history`, `portfolio`, `report`.

### 15.2 Required commands

```
vbu-agent init
vbu-agent config validate
vbu-agent project create --project project-alpha --name "Project Alpha"
vbu-agent project list
vbu-agent project validate --project project-alpha
vbu-agent project update --project project-alpha
vbu-agent project update --project project-alpha --dry-run
vbu-agent project sync-ado --project project-alpha
vbu-agent project status --project project-alpha
vbu-agent project slack-status --project project-alpha
vbu-agent project report --project project-alpha
vbu-agent dashboard generate
vbu-agent history show --project project-alpha
vbu-agent history export --project project-alpha --format json
vbu-agent project rollback --project project-alpha --snapshot latest
vbu-agent doctor
```

### 15.3 Suggested extra commands

```
vbu-agent project ask --project project-alpha "What are the main risks this week?"
vbu-agent portfolio ask "Which projects need executive attention?"
vbu-agent report open --latest
```

### 15.4 Command reference (selected)

| Command | Purpose | Key flags |
|---------|---------|-----------|
| `init` | Scaffold `config/`, `projects/`, `data/`, `reports/`, `templates/`, `.gitignore`. | `--force` |
| `config validate` | Validate global config; non-zero on error. | — |
| `project create` | Scaffold a project folder + `project.yaml` + empty context files. | `--project`, `--name`, `--from-template` |
| `project list` | List projects with current health/last-update. | `--json` |
| `project validate` | Validate `project.yaml` + context integrity. | `--project` |
| `project update` | Run the update workflow (§8). | `--dry-run`, `--review-required` |
| `project sync-ado` | Refresh ADO metrics + persist snapshot. | `--no-cache` |
| `project status` | Print current computed status (no generation). | `--json` |
| `project slack-status` | Generate Slack message (§12). | `--style` |
| `project report` | Generate HTML report (§13). | `--open` |
| `dashboard generate` | Build portfolio dashboard (§14). | `--refresh`, `--open` |
| `history show` | Show metric history. | `--metric`, `--since` |
| `history export` | Export history. | `--format {json,csv}` |
| `project rollback` | Restore from a snapshot. | `--snapshot {latest,<run_id>}` |
| `project ask` / `portfolio ask` | NL Q&A grounded in context/history. | — |
| `doctor` | Diagnose env, providers, ADO reachability, paths. | — |

### 15.5 Global flags & UX

- `--config <path>`, `--verbose/-v`, `--quiet/-q`, `--json` where applicable.
- All commands exit non-zero on failure with actionable messages.
- Destructive actions (`rollback`, `init --force`) confirm unless `--yes` is passed.

---

## 16. Agent, Skill, Hook, and MCP Design

### 16.1 Agents

| Agent | Responsibility | Primary model tier |
|-------|----------------|--------------------|
| **Project Context Curator** | Summarize input, reconcile with context, produce surgical change set + conflicts. | Sonnet |
| **Azure DevOps Metrics Agent** | Orchestrate WIQL → batch → field-map → normalized items; hand to Progress Engine. | (deterministic; minimal/no LLM) |
| **Delivery Status Analyst** | Turn computed metrics into health reasoning + executive summary inputs. | Sonnet |
| **HTML Report Generator** | Assemble view-model + narrative into the report template. | Sonnet for prose only |
| **Portfolio Executive Dashboard** | Aggregate portfolio metrics + executive narrative. | Sonnet for prose only |
| **Historical Trend Analyst** | Interpret trends/velocity/forecast for narrative explanation. | Sonnet |

Agents are scoped, single-purpose, and return **structured** outputs validated by Pydantic before use.

### 16.2 Skills

| Skill | Output | Validators |
|-------|--------|-----------|
| **Slack Status Writer** | Executive Slack message | word cap, section presence, numeric guard, secret scan |
| **Executive Summary** | Report/dashboard summary paragraph(s) | length, numeric guard, secret scan |
| **Risk Analysis** | Prose risk narrative + severity rationale | references only known risks, secret scan |
| **Decision Log Summarizer** | Condensed decision digest | references only known `DEC-NNN`, no fabrication |
| **Forecast Explanation** | Plain-language forecast rationale | uses only computed forecast + confidence |

### 16.3 Hooks and guardrails

1. **Pre-update backup hook** — snapshot before any write.
2. **Post-update validation hook** — re-parse context, verify front-matter/hashes, schema-valid.
3. **Secret redaction hook** — central filter on all logs/errors/artifacts.
4. **YAML schema validation hook** — validate global + project YAML before use.
5. **Report validation hook** — verify sections, numeric traceability, no secrets, valid HTML.
6. **Human review mode** — `--review-required` gate before applying changes.
7. **Conflict detection** — contradictions routed to `conflicts.md`, never silently merged.
8. **Dry-run mode** — compute and preview, write nothing.
9. **Rollback support** — restore any snapshot via CLI.

### 16.4 MCP tools

Each tool below is exposed via an MCP server so agents (and Claude Code) can operate on projects through a typed contract.

| Tool | Purpose | Input → Output | Errors | Security |
|------|---------|----------------|--------|----------|
| `read_project_context(project_id)` | Read all context files. | `{project_id}` → `{files: {name: content}}` | `ProjectNotFound` | read-only; secret scan on return |
| `write_project_context(project_id, file_name, content)` | Surgical write to one context file. | `{project_id, file_name, content}` → `{ok, content_sha256}` | `InvalidFile`, `WriteBlocked` | snapshot-guarded; secret scan pre-write |
| `list_project_input_files(project_id)` | List pending inputs. | `{project_id}` → `{files: [...]}` | `ProjectNotFound` | read-only |
| `archive_processed_input(project_id)` | Move inputs to timestamped archive. | `{project_id}` → `{archived_to}` | `NothingToArchive` | atomic move; preserves bytes |
| `execute_ado_wiql(project_id, wiql)` | Run WIQL, return normalized items. | `{project_id, wiql}` → `{items: [...]}` | `AdoAuth/Wiql/Network` | PAT from env only; never echoed |
| `calculate_project_progress(project_id)` | Run Progress Engine. | `{project_id}` → `ProgressResult` | `ProgressConfigError` | deterministic; no secrets |
| `save_project_snapshot(project_id)` | Persist snapshot + DB rows. | `{project_id}` → `{run_id, path}` | `SnapshotError` | immutable snapshot |
| `query_project_history(project_id, metric_name)` | Time-series for a metric. | `{project_id, metric_name}` → `{points: [...]}` | `UnknownMetric` | read-only |
| `generate_project_report(project_id)` | Build HTML report. | `{project_id}` → `{path}` | `RenderError`, `ValidationError` | report validation hook |
| `generate_portfolio_dashboard()` | Build dashboard. | `{}` → `{path}` | `RenderError` | report validation hook |

All MCP tools: validate inputs with Pydantic, run outputs through secret redaction, return structured errors, and never accept or return raw secret material.

---

## 17. Python Package Structure

```
vbu-projects-agent/
  pyproject.toml
  README.md
  .gitignore
  config/
    vbu-agent.yaml
  projects/                       # project folders (gitignored content)
  data/
    vbu_projects_agent.db
    snapshots/
  reports/
  templates/
    project_status_report.html.j2
    executive_dashboard.html.j2
    partials/
  src/
    vbu_projects_agent/
      __init__.py
      cli.py                      # Typer command tree
      orchestrator.py             # workflow engine (update/report/dashboard)
      config/
        __init__.py
        models.py                 # Pydantic models (global + project)
        loader.py                 # load + precedence + validation
      claude/
        provider.py               # ClaudeProvider protocol + resolution
        api_key_provider.py
        local_cli_provider.py
        routing.py                # per-task model routing
      projects/
        context_manager.py        # parse/write context files, front-matter, hashes
        update_workflow.py        # the §8 workflow
        conflicts.py
        scaffolder.py             # project create / init
      ado/
        client.py
        wiql.py
        work_items.py
        cache.py
        errors.py
      progress/
        engine.py                 # strategy registry + ProgressResult
        staged_tags.py
        test_case_milestones.py
        weighted_workload.py
        manual_kpi.py
        velocity.py
        forecast.py
        health.py
      storage/
        db.py                     # SQLite connection + migrations
        repositories.py           # typed CRUD per table
        snapshots.py              # snapshot write/read/rollback
      reporting/
        view_models.py
        report_builder.py         # project HTML
        dashboard_builder.py      # portfolio HTML
        charts.py                 # Plotly chart construction
      skills/
        slack_status.py
        executive_summary.py
        risk_analysis.py
        decision_summarizer.py
        forecast_explanation.py
        prompts/                  # prompt templates (.txt/.j2)
        validators.py             # numeric guard, word cap, section checks
      agents/
        context_curator.py
        ado_metrics.py
        status_analyst.py
        report_generator.py
        dashboard_agent.py
        trend_analyst.py
      security/
        redaction.py              # central secret filter
        scanner.py                # pre-write secret scan
        patterns.py               # PAT/key regexes
      mcp/
        server.py                 # MCP server exposing the §16.4 tools
        tools.py
      tests/
        ...
```

### 17.1 Module responsibilities

| Module | Responsibility |
|--------|----------------|
| `cli` | Thin Typer layer; parses args, calls orchestrator/services. No business logic. |
| `orchestrator` | Sequences workflows (update, report, dashboard); owns transactions and ordering of hooks. |
| `config` | Pydantic models + loader enforcing validation and precedence. |
| `claude` | Provider abstraction, mode detection/fallback, model routing. |
| `projects` | Context parsing/writing, the update workflow, conflict handling, scaffolding. |
| `ado` | All Azure DevOps I/O: WIQL, batching, mapping, caching, typed errors. |
| `progress` | Pluggable strategies, velocity, forecasting, health. **Deterministic.** |
| `storage` | SQLite schema/migrations, repositories, snapshot/rollback. |
| `reporting` | View-models, Jinja2 rendering, Plotly charts for report + dashboard. |
| `skills` | Claude-backed prose generators + their output validators + prompts. |
| `agents` | Higher-level orchestration of skills/tools into the §16.1 agents. |
| `security` | Redaction filter, pre-write scanner, secret patterns. |
| `mcp` | MCP server exposing typed tools to agents/Claude Code. |
| `tests` | pytest suite (see §22). |

---

## 18. Data Models and Database Schema

### 18.1 Core internal models (Pydantic / dataclasses)

```python
class HealthThresholds(BaseModel):
    green: float
    yellow: float
    red: float = 0.0

class StageConfig(BaseModel):
    id: str
    name: str
    tag: str
    target_count: int | None = None
    done_states: list[str] = ["Done", "Closed", "Passed"]

class ProgressModelConfig(BaseModel):
    type: Literal["staged_tags", "test_case_milestones",
                  "weighted_workload", "manual_kpi"]
    tag_field: str = "System.Tags"
    stages: list[StageConfig] = []
    kpis: list[ManualKpi] = []
    # strategy-specific extras validated per type
```

### 18.2 SQLite DDL

```sql
CREATE TABLE projects (
    id                TEXT PRIMARY KEY,            -- e.g. 'project-alpha'
    name              TEXT NOT NULL,
    client            TEXT,
    delivery_manager  TEXT,
    progress_type     TEXT NOT NULL,
    current_health    TEXT,                        -- green/yellow/red
    last_updated_at   TEXT,                        -- ISO8601
    created_at        TEXT NOT NULL
);

CREATE TABLE project_snapshots (
    run_id            TEXT PRIMARY KEY,            -- stable run id
    project_id        TEXT NOT NULL REFERENCES projects(id),
    created_at        TEXT NOT NULL,
    mode              TEXT NOT NULL,               -- update/sync/dry-run
    claude_provider   TEXT,                        -- api_key/local_cli/none
    source_files      TEXT,                        -- JSON array of input filenames
    snapshot_path     TEXT NOT NULL,               -- data/snapshots/.../
    context_hashes    TEXT,                        -- JSON {file: sha256}
    change_summary    TEXT
);

CREATE TABLE project_metrics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL REFERENCES project_snapshots(run_id),
    project_id        TEXT NOT NULL REFERENCES projects(id),
    measured_at       TEXT NOT NULL,
    overall_percent   REAL,
    active_stage      TEXT,
    health            TEXT,
    velocity_per_day  REAL,
    forecast_date     TEXT,
    forecast_conf     REAL,
    monthly_revenue   REAL,
    revenue_at_risk   REAL,
    raw_counts        TEXT                         -- JSON of per-stage/raw counts
);

CREATE TABLE milestone_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL REFERENCES project_snapshots(run_id),
    project_id        TEXT NOT NULL REFERENCES projects(id),
    milestone_id      TEXT NOT NULL,
    name              TEXT,
    target_date       TEXT,
    forecast_date     TEXT,
    percent_complete  REAL,
    state             TEXT,                        -- on_track/at_risk/late/done
    measured_at       TEXT NOT NULL
);

CREATE TABLE risks (
    id                TEXT PRIMARY KEY,            -- RISK-NNN (per project namespaced)
    project_id        TEXT NOT NULL REFERENCES projects(id),
    description       TEXT,
    severity          TEXT,                        -- low/medium/high/critical
    status            TEXT,                        -- open/mitigating/closed
    owner             TEXT,
    opened_at         TEXT NOT NULL,
    last_seen_at      TEXT,
    closed_at         TEXT
);

CREATE TABLE decisions (
    id                TEXT PRIMARY KEY,            -- DEC-NNN
    project_id        TEXT NOT NULL REFERENCES projects(id),
    decided_at        TEXT NOT NULL,
    decision          TEXT,
    rationale         TEXT,
    decided_by        TEXT
);

CREATE TABLE generated_artifacts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id        TEXT REFERENCES projects(id),  -- NULL for portfolio dashboard
    run_id            TEXT REFERENCES project_snapshots(run_id),
    kind              TEXT NOT NULL,               -- slack/report/dashboard
    path              TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE ado_sync_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id        TEXT NOT NULL REFERENCES projects(id),
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    status            TEXT,                        -- success/auth_error/wiql_error/network_error/empty
    item_count        INTEGER,
    error_summary     TEXT                         -- redacted
);

CREATE INDEX idx_metrics_project_time   ON project_metrics(project_id, measured_at);
CREATE INDEX idx_milestone_project_time ON milestone_snapshots(project_id, measured_at);
CREATE INDEX idx_risks_project_status   ON risks(project_id, status);
CREATE INDEX idx_snapshots_project_time ON project_snapshots(project_id, created_at);
```

### 18.3 Migration strategy

A lightweight, version-tracked migration runner (`storage/db.py`) applies ordered SQL migrations and records the schema version in a `schema_version` table, so future schema changes are additive and safe.

---

## 19. Prompt Templates

All prompts share a **system preamble** enforcing the determinism contract.

### 19.1 Shared system preamble

```
You are a delivery-status writing assistant for an executive audience.
Rules:
- Use ONLY the figures, dates, names, and facts provided in the input block.
- NEVER invent, compute, round differently, or estimate any number or date.
- If a value is missing, omit it rather than guessing.
- Do not include secrets, tokens, PATs, internal IDs, or raw work-item titles
  unless explicitly present and permitted in the input.
- Match the requested structure and word budget exactly.
- Write in a {tone} tone.
```

### 19.2 Slack Status Writer prompt

```
[INPUT]
project_name: {name}
health: {health}  (reasons: {reasons})
progress: {progress_summary}            # e.g. "Alpha Ready 78% complete, 22 test cases remaining"
next_milestone: {milestone_name} target {target_or_forecast_date}
top_risk: {top_risk_text}
open_ask: {ask_text}
max_words: {max_words}

[TASK]
Write a copy-ready executive Slack status with exactly these lines:
1) "{project_name} — Status: {Health}"
2) "Progress: ..."
3) "Next milestone: ..."
4) "Key risk: ..."   (omit if no risk)
5) "Ask: ..."        (omit if no ask)
Stay within {max_words} words. Use only the figures above.
```

### 19.3 Executive Summary prompt (report/dashboard)

```
[INPUT]
computed_facts: {facts_json}    # health, progress, milestones, velocity, forecast, revenue
recent_changes: {change_digest}
[TASK]
Write a 3–5 sentence executive summary of delivery status and trajectory.
State health and the single most important driver. Reference the next milestone
and any forecast with its confidence qualifier ("high/medium/low confidence").
Use only provided figures.
```

### 19.4 Risk Analysis prompt

```
[INPUT]
risks: {risks_json}   # id, description, severity, status, opened_at, last_seen_at (age)
[TASK]
Summarize the risk posture in prose: lead with the highest-severity/oldest open risks,
note aging (e.g., "open 17 days"), and mitigation status. Reference only listed risks.
```

### 19.5 Decision Log Summarizer prompt

```
[INPUT]
decisions: {decisions_json}   # id, decided_at, decision, rationale
[TASK]
Produce a concise digest of recent decisions (most recent first), one line each:
"DEC-NNN ({date}): {decision} — {one-clause rationale}". Reference only listed decisions.
```

### 19.6 Forecast Explanation prompt

```
[INPUT]
forecast: {date}, confidence: {low|medium|high}
basis: velocity {v}/day over {window} days; remaining {r}; history_points {n}; variance {var}
[TASK]
Explain in 2–3 plain-language sentences how the forecast was derived and what would
change it. Do not restate raw numbers beyond what is provided. Convey the confidence level.
```

### 19.7 Output validators (applied to every skill)

- **Numeric guard:** extract numbers/dates from output; assert each appears in the input block; else reject.
- **Word/length budget:** enforce caps.
- **Section/structure check:** required lines/sections present.
- **Secret scan:** run output through `security/scanner.py`.
- **Retry then fallback:** up to N regenerations, then a deterministic template.

---

## 20. Security and Secret Management

### 20.1 Principles

1. **Never commit secrets.** Secrets live only in the environment.
2. **Prefer environment variables** for the Claude API key and ADO PATs.
3. **YAML references env-var names only** (`api_key_env_var`, `pat_env_var`); literal secret fields default to `null`.
4. **Redact secrets from logs** via a central logging filter.
5. **Redact secrets from reports** via the report-validation hook.
6. **Minimize data sent to Claude** — only the computed facts needed for prose; never PATs, never full raw ADO payloads.
7. **Support local-only mode** — local Claude CLI provider needs no key stored in this tool.
8. **`.gitignore`** excludes local configs, data, snapshots, reports, and generated artifacts.
9. **Secret scan before writing files** — pre-write scanner blocks any artifact containing a secret-shaped string.
10. **No PATs or API keys in generated artifacts** — enforced by scanner + redaction.

### 20.2 Redaction & scanning

- `security/patterns.py` holds regexes for Anthropic key shapes, Azure DevOps PAT shapes (long base32/base64-like tokens), and generic `Bearer`/basic-auth headers.
- `security/redaction.py` is installed as a `logging.Filter` on the root logger and is also applied to exception messages before they surface.
- `security/scanner.py` runs on **every** file write (context, snapshots, reports, Slack output). A positive hit aborts the write with a clear, value-free error.

### 20.3 `.gitignore` (essentials)

```gitignore
# secrets / local config
config/*.local.yaml
.env
*.pat
# state
data/
!data/.gitkeep
reports/
projects/*/processed_input/
projects/*/generated/
projects/*/input/
# python
__pycache__/
*.pyc
.venv/
```

### 20.4 Data minimization to Claude

The orchestrator builds a **scrubbed fact bundle** for each skill: only the computed metrics, named milestones, and sanitized risk/decision text required for the prose. Raw ADO items, PATs, and unmapped fields never enter a prompt.

---

## 21. Error Handling and Observability

### 21.1 Error taxonomy

Typed exception hierarchy (`VbuError` base) covering: `ConfigError`, `ProjectError` (`ProjectNotFound`, `ProjectValidationError`), `AdoError` (`AdoPatMissing`, `AdoAuthError`, `AdoPatExpired`, `AdoWiqlError`, `AdoNetworkError`), `ProgressError`, `SnapshotError`, `ClaudeProviderUnavailable`, `SkillValidationError`, `ReportRenderError`, `SecretDetected`. Every error carries a human remediation hint and maps to a stable non-zero exit code.

### 21.2 Logging

- Structured logging (JSON option) with levels; default human-readable.
- Every run logs its `run_id`, mode, resolved Claude provider, and timing per stage.
- The redaction filter is mandatory and always-on.

### 21.3 Observability

- `vbu-agent doctor` checks: config validity, Claude provider resolution (and why others were skipped), ADO reachability per project (auth probe), writable paths, DB connectivity, template parseability.
- `ado_sync_runs` and `project_snapshots` give a durable audit trail of what ran, when, with what outcome.
- Per-run change summaries are persisted as artifacts.

---

## 22. Testing Strategy

Framework: **pytest** (+ `pytest-mock`, `responses`/`respx` for HTTP, `freezegun` for time, `hypothesis` optional for progress math).

### 22.1 Coverage matrix

| # | Area | Representative tests |
|---|------|----------------------|
| 1 | Global config | valid load; each validation rule rejects bad input; precedence. |
| 2 | Project YAML | required fields; progress-model-specific validation; env-var refs. |
| 3 | ADO WIQL | mocked WIQL → IDs → batch; field mapping; pagination. |
| 4 | Progress calcs | each strategy with fixtures; edge cases (empty, zero targets, all-done). |
| 5 | Context update | reconcile new/update/confirm/contradict; surgical edits preserve untouched blocks. |
| 6 | Snapshot creation | snapshot written before write; contents complete; hashes correct. |
| 7 | Rollback | restore latest and specific `run_id`; idempotent. |
| 8 | Slack status | structure, word cap, numeric guard rejects fabricated numbers, fallback path. |
| 9 | HTML report | renders all sections; validation hook catches missing section/secret. |
| 10 | Dashboard | aggregation across N project fixtures; revenue-at-risk; heatmap. |
| 11 | Secret redaction | logs/errors/artifacts never contain seeded fake secrets; scanner blocks writes. |
| 12 | CLI | each command's happy path + key failure exit codes (Typer `CliRunner`). |
| 13 | Agent prompt output | validators enforce numeric guard/structure on canned model outputs. |

### 22.2 Mocking & fixtures

- **Mocked Azure DevOps:** canned WIQL + batch responses (auth-error, bad-WIQL, empty, network-error variants) so no live PAT is needed in CI.
- **Mocked Claude provider:** a `FakeClaudeProvider` returns deterministic strings (and deliberately-bad strings to test validators/fallbacks).
- **Time control:** `freezegun` for forecast/velocity determinism.
- **Temp project fixtures:** factory builds a temp `projects/<id>/` with seeded context for workflow tests.

### 22.3 Quality gates

- Target ≥ 85% coverage on `progress/`, `security/`, `config/`, `projects/`.
- Progress math has golden-file fixtures; any change to output is an explicit review.

---

## 23. Implementation Roadmap

Each phase lists deliverables, tasks, validation criteria, and risks.

### Phase 1 — Foundation
- **Deliverables:** repo scaffold, `pyproject.toml`, config models + loader, `init`, `config validate`, `doctor`, logging + redaction filter.
- **Tasks:** Pydantic config models; precedence; CLI skeleton (Typer); `.gitignore`; logging setup.
- **Validation:** `config validate` passes/fails correctly; `doctor` reports provider resolution; redaction unit tests.
- **Risks:** over-engineering config early — mitigate by validating against the Appendix A example only.

### Phase 2 — Context Update Agent
- **Deliverables:** context parser/writer, update workflow (dry-run/review/default), conflict detection, snapshots, change summary.
- **Tasks:** front-matter + hash handling; reconcile step with `FakeClaudeProvider`; conflict writer; snapshot/rollback.
- **Validation:** surgical-edit tests; snapshot-before-write proven; rollback restores exactly.
- **Risks:** reconciliation hallucination — mitigate with structured output + numeric guard + review mode.

### Phase 3 — Azure DevOps Integration
- **Deliverables:** ADO client, WIQL, batching, field mapping, caching, typed errors, `sync-ado`.
- **Tasks:** auth via env PAT; batch ≤200; error matrix; cache keys; `ado_sync_runs` logging.
- **Validation:** mocked-response suite covers every error path; no PAT in any log.
- **Risks:** ADO API/version drift — mitigate with configurable `api_version` and contract tests.

### Phase 4 — Progress Engine
- **Deliverables:** strategy registry + 4 strategies, velocity, forecasting, health.
- **Tasks:** implement `staged_tags`, `test_case_milestones`, `weighted_workload`, `manual_kpi`; robust velocity fit; confidence scoring.
- **Validation:** golden fixtures per strategy; forecast suppressed on thin history.
- **Risks:** forecast over-confidence — mitigate with explicit confidence + suppression thresholds.

### Phase 5 — Slack Status Generation
- **Deliverables:** Slack Status Writer skill + validators + `slack-status`.
- **Tasks:** prompt template; numeric guard; word cap; deterministic fallback.
- **Validation:** fabricated-number outputs are rejected; fallback always produces a valid message.
- **Risks:** tone/length drift — mitigate with validators + low temperature.

### Phase 6 — Project HTML Reports
- **Deliverables:** view-models, Jinja2 template, Plotly charts, report-validation hook, `report`.
- **Tasks:** trend/velocity/forecast charts; standalone HTML; section completeness checks.
- **Validation:** all sections render; validation hook blocks missing-section/secret reports.
- **Risks:** large standalone HTML — mitigate with inline-vs-CDN config and chart data thinning.

### Phase 7 — Executive Portfolio Dashboard
- **Deliverables:** portfolio aggregation, dashboard template, heatmap, revenue-at-risk, `dashboard generate`.
- **Tasks:** cross-project view-model; trend/blocked/negative detection; `--refresh`.
- **Validation:** multi-project fixtures aggregate correctly; revenue-at-risk math verified.
- **Risks:** stale data confusion — mitigate by showing per-project last-update timestamps prominently.

### Phase 8 — MCP Tools and Agentic Enhancements
- **Deliverables:** MCP server exposing the §16.4 tools; `project ask` / `portfolio ask`.
- **Tasks:** typed tool contracts; input validation; secret scrubbing on I/O.
- **Validation:** each tool's schema + error behavior tested; NL Q&A grounded in real context only.
- **Risks:** tool misuse / over-broad writes — mitigate with snapshot-guard + write scoping.

### Phase 9 — Security Hardening
- **Deliverables:** pre-write scanner everywhere, finalized redaction patterns, `.gitignore` audit, data-minimization review.
- **Tasks:** seed-secret tests across all write paths; verify no secret reaches Claude.
- **Validation:** red-team fixtures fail to leak; scanner blocks writes.
- **Risks:** pattern gaps — mitigate with conservative patterns + tests for known token shapes.

### Phase 10 — Delivery Manager Adoption
- **Deliverables:** onboarding template generator, daily checklist, README/runbook, sample project.
- **Tasks:** `project create --from-template`; documented weekly cadence; example outputs.
- **Validation:** a new DM can onboard a project and produce a Slack status + report in <30 min following the runbook.
- **Risks:** low adoption — mitigate with minimal-friction defaults and copy-ready outputs.

---

## 24. Adoption Plan for Delivery Managers

### 24.1 Onboarding flow

1. `vbu-agent init` (once per machine).
2. Set `ANTHROPIC_API_KEY` **or** rely on local Claude CLI.
3. `vbu-agent project create --project <id> --name "<Name>" --from-template`.
4. Fill `project.yaml` (ADO org/project, PAT env-var name, WIQL, progress model).
5. `export <PROJECT>_ADO_PAT=...`; `vbu-agent project validate` + `doctor`.
6. Drop first inputs into `input/`; `project update --dry-run` then real update.
7. `project sync-ado`, `slack-status`, `report`.

### 24.2 Daily / weekly cadence

- **Daily (5 min):** drop standup notes/emails into `input/`; `project update`; optional `slack-status`.
- **Weekly:** `sync-ado`; `report`; `dashboard generate`; review risks/decisions; weekly status digest (§25).

### 24.3 Enablement materials

- A one-page **daily update checklist** (§25 item 1).
- A runbook with the commands above and troubleshooting (`doctor`).
- A reference sample project (`project-alpha`) with realistic context and outputs.

### 24.4 Success metrics

- Time-to-status reduced; context freshness (days since last update) low across portfolio; consistent report format adopted by ≥ the target set of DMs.

---

## 25. Future Enhancements

1. **Daily update checklist** generator (per project, surfaced by the CLI).
2. **Risk aging** indicators (days open) surfaced in reports/dashboard.
3. **Risk trend detection** (rising count/severity over time).
4. **Milestone forecast confidence score** (history depth × inverse variance × recency).
5. **Executive ask tracking** (open asks with age and owner across the portfolio).
6. **Decision log summarization** digest (weekly).
7. **Weekly status digest** (auto-compiled multi-project summary).
8. **Project health scoring** refinement (composite of progress, risk, velocity, schedule).
9. **Portfolio heatmap** (project × dimension).
10. **Revenue-at-risk calculation** (sum of revenue on yellow/red projects).
11. **Velocity drop detection** (alert when trailing velocity falls below threshold).
12. **Data quality score** (completeness/freshness of context + ADO coverage).
13. **Missing information detector** (flags empty/stale context sections before reporting).
14. **Project onboarding template generator** (richer scaffolds per delivery type).
15. **Optional Slack posting integration** (post generated status to a channel via webhook/bot, behind explicit opt-in and approval).

---

## 26. Acceptance Criteria

The solution is acceptance-ready when:

- [ ] `config validate` and `doctor` pass on a clean install with the Appendix A config.
- [ ] Both Claude modes resolve correctly; fallback works when the API key is absent; `doctor` reports the active mode without revealing secrets.
- [ ] `project create` scaffolds a valid project; `project validate` enforces `project.yaml` rules.
- [ ] `project update` reads `input/`, updates the correct context files surgically, snapshots **before** writing, archives inputs, records history, and emits a change summary.
- [ ] `--dry-run` writes nothing to `context/`; `--review-required` applies only after approval.
- [ ] Conflicting inputs are recorded in `conflicts.md` and never silently merged.
- [ ] `sync-ado` executes WIQL, batches details, maps fields, persists a snapshot, and handles every error in the §9.6 matrix; **no PAT ever appears in logs/errors/artifacts.**
- [ ] Each of the four progress strategies computes correctly against golden fixtures; forecasts carry confidence and are suppressed on thin history.
- [ ] `slack-status` produces a structured, copy-ready message within the word cap; fabricated numbers are rejected; a deterministic fallback exists.
- [ ] `report` produces a standalone interactive HTML with all 13 sections and passes the report-validation hook.
- [ ] `dashboard generate` aggregates all projects with health, milestone timeline, revenue-at-risk, negative-trend and blocked detection.
- [ ] History supports trends, velocity, forecasts, health changes, milestone progress, risk evolution, and revenue timeline; snapshots enable `rollback`.
- [ ] All file writes pass the secret scanner; `.gitignore` excludes secrets/state/outputs.
- [ ] pytest suite covers the §22 matrix with mocked ADO and Claude; quality gates met.
- [ ] A new DM can onboard a project and produce a Slack status + report by following the runbook.

---

## 27. Appendix A — Example Global YAML

`config/vbu-agent.yaml`:

```yaml
app:
  name: VBU-Projects-Agent
  environment: local
  default_timezone: America/Costa_Rica

claude:
  provider_priority:
    - api_key
    - local_cli
  api_key_env_var: ANTHROPIC_API_KEY
  api_key: null                 # never hardcode; prefer the env var above
  model: claude-sonnet-4-5
  max_tokens: 8000
  temperature: 0.2
  local_cli_enabled: true
  # optional per-task routing (falls back to `model` if omitted)
  task_models:
    classify_input: claude-haiku-4-5
    reconcile_context: claude-sonnet-4-5
    executive_summary: claude-sonnet-4-5

storage:
  provider: sqlite
  sqlite_path: data/vbu_projects_agent.db
  snapshots_path: data/snapshots
  artifacts_path: artifacts

projects:
  root_path: projects
  input_folder_name: input
  archive_folder_name: processed_input

reports:
  output_path: reports
  project_report_template: templates/project_status_report.html.j2
  executive_dashboard_template: templates/executive_dashboard.html.j2
  charts:
    embed_mode: inline          # inline | cdn
    trailing_window_days: 30

slack:
  default_message_style: executive_short
  max_words: 180

ado:
  default_api_version: "7.1"
  batch_size: 200
  cache_ttl_seconds: 900
  max_retries: 3
```

---

## 28. Appendix B — Example Project YAML Files

### B.1 Test-case-milestone project (`projects/project-alpha/project.yaml`)

```yaml
project:
  id: project-alpha
  name: Project Alpha
  client: Example Client
  delivery_manager: Joseph
  account_executive: TBD
  delivery_director: TBD
  timezone: America/Costa_Rica
  health_thresholds:
    green: 0.85
    yellow: 0.65
    red: 0.0

azure_devops:
  organization: gap-example
  project: ExampleADOProject
  base_url: https://dev.azure.com/gap-example
  pat_env_var: PROJECT_ALPHA_ADO_PAT
  pat_token: null
  api_version: "7.1"

field_mappings:
  id: System.Id
  title: System.Title
  state: System.State
  tags: System.Tags
  story_points: Microsoft.VSTS.Scheduling.StoryPoints
  work_item_type: System.WorkItemType

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
    - id: production
      name: Production Ready
      target_passing: 300
      target_date: 2026-10-15

revenue:
  currency: USD
  total_contract_value: 0
  monthly_revenue: 0
  revenue_recognition_model: manual

reporting:
  include_risks: true
  include_financials: true
  include_velocity: true
  include_timeline: true

slack:
  channel_hint: executive-team
  tone: concise_executive
  include: [health, progress, next_milestone, risks, asks]
```

### B.2 Stage/tag-based project (`projects/project-beta/project.yaml` — excerpt)

```yaml
progress_model:
  type: staged_tags
  tag_field: System.Tags
  stages:
    - id: alpha
      name: Alpha Ready
      tag: AlphaReady
      target_count: 100
      done_states: [Done, Closed, Passed]
    - id: beta
      name: Beta Ready
      tag: BetaReady
      target_count: 200
      done_states: [Done, Closed, Passed]
    - id: production
      name: Production Ready
      tag: ProductionReady
      target_count: 300
      done_states: [Done, Closed, Passed]
```

### B.3 Weighted-workload project (excerpt)

```yaml
progress_model:
  type: weighted_workload
  weight_field: story_points
  done_states: [Done, Closed]
  type_weights:               # optional per-work-item-type multipliers
    "Product Backlog Item": 1.0
    "Bug": 0.5
```

### B.4 Manual-KPI project (excerpt)

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

## 29. Appendix C — Example CLI Usage

```bash
# One-time setup
vbu-agent init
export ANTHROPIC_API_KEY=...                  # or rely on local Claude CLI
vbu-agent config validate
vbu-agent doctor

# Onboard a project
vbu-agent project create --project project-alpha --name "Project Alpha" --from-template
export PROJECT_ALPHA_ADO_PAT=...
vbu-agent project validate --project project-alpha

# Daily loop
#   (drop files into projects/project-alpha/input/ first)
vbu-agent project update --project project-alpha --dry-run
vbu-agent project update --project project-alpha
vbu-agent project slack-status --project project-alpha

# Weekly loop
vbu-agent project sync-ado --project project-alpha
vbu-agent project status --project project-alpha --json
vbu-agent project report --project project-alpha --open
vbu-agent dashboard generate --refresh --open

# History & recovery
vbu-agent history show --project project-alpha --metric overall_percent --since 2026-05-01
vbu-agent history export --project project-alpha --format json
vbu-agent project rollback --project project-alpha --snapshot latest

# Natural-language queries
vbu-agent project ask --project project-alpha "What are the main risks this week?"
vbu-agent portfolio ask "Which projects need executive attention?"
vbu-agent report open --latest
```

---

## 30. Appendix D — Example Slack Message Outputs

### D.1 Test-case-milestone project (Yellow)

```
Project Alpha — Status: Yellow
Progress: Alpha Ready is 78% complete, with 22 test cases remaining.
Next milestone: Alpha Ready targeted for July 12.
Key risk: Environment readiness may impact validation velocity.
Ask: Need client confirmation on UAT data availability by Friday.
```

### D.2 Stage/tag-based project (Green)

```
Project Beta — Status: Green
Progress: Beta Ready stage is 64% complete (128/200 items); Alpha Ready done.
Next milestone: Beta Ready targeted for August 30 (on track).
Key risk: None blocking this week.
Ask: None.
```

### D.3 Weighted-workload project (Red)

```
Project Gamma — Status: Red
Progress: 41% of weighted backlog complete; velocity down ~30% over the last two weeks.
Next milestone: Release Candidate forecast Sep 9 (low confidence).
Key risk: Two senior engineers rolled off; capacity gap unresolved.
Ask: Approve backfill or rescope by end of week to protect the date.
```

### D.4 Deterministic fallback (Claude unavailable)

```
Project Alpha — Status: Yellow
Progress: Alpha Ready 78% (22 test cases remaining).
Next milestone: Alpha Ready — 2026-07-12.
Key risk: RISK-014 (high) — UAT environment readiness.
Ask: Confirm UAT data availability by Friday.
[Generated without narrative model; figures are computed.]
```

---

*End of implementation plan.*
