# Design: Simplify VBU-Projects-Agent Onboarding

**Date:** 2026-07-02
**Status:** Approved (pending spec review)
**Author:** Joseph Cruz Monge (with Claude)

## Goal

Make the VBU-Projects-Agent easy to share and adopt: one GitHub repo containing the
delivery manager's own projects, so any teammate can clone the repo, run a single
setup command, and add their own project into the **same shared structure** — without
each person building their own scaffolding.

Chosen model (confirmed with user):

- **One shared repo, all projects.** The whole team's projects live in one repo under
  `projects/`, forming a shared portfolio. Each teammate works inside their own
  `projects/<id>/` folder to minimize merge conflicts.
- **Simplify the setup/install experience** specifically — that is the friction the
  user identified. The engine itself is not the problem.

## Non-Goals

- No changes to the engine (ADO client, progress engine, reporting, MCP server,
  storage, security). This is purely an onboarding/packaging layer.
- No Docker / Dev Container (rejected: needs Docker, heavier first run).
- No second/thin repo or pipx distribution (rejected: contradicts "one repo with
  everything").
- No flattening of the `VBUProjectsAgent/vbu-projects-agent/` nesting in this pass
  (see Open Considerations).

## Current pain (baseline)

A new teammate today must: install Python 3.13 → create a venv →
`pip install -e ".[dev]"` → `vbu-agent init` → set `ANTHROPIC_API_KEY` → set a
per-project ADO PAT env var → `vbu-agent config validate` → `vbu-agent doctor`.
Env-var names must be remembered and exported manually each shell session.

Note: the repo **already commits** the shared structure and each project's
`project.yaml` + `context/` (`.gitignore` excludes only `input/`, `generated/`,
`processed_input/`, `data/`, `reports/`). So "shared portfolio in one repo" is
largely already true — the work is the on-ramp.

## Design

### 1. Repo layout (shared, committed)

```
VBUProjectsAgent/                 ← git repo root (clone target)
  README.md                       ← rewritten 3-step quickstart
  setup.ps1                       ← one-command bootstrap (Windows)
  setup.sh                        ← one-command bootstrap (Mac/Linux)
  vbu-projects-agent/
    .env.example                  ← committed template for secrets
    config/vbu-agent.yaml         ← shared team defaults (committed, as today)
    projects/
      _example/                   ← real, filled-in sample project (committed);
                                     the single template everyone copies
      <alice-project>/            ← each teammate's projects, committed & shared
      <bob-project>/
    src/…                         ← engine, unchanged
```

### 2. One-command setup — `setup.ps1` / `setup.sh`

Idempotent bootstrap placed at the **repo root** so `clone → run one script` works.
The script targets the `vbu-projects-agent/` subfolder and performs:

1. Verify Python 3.13+ is available; if not, print a clear install pointer and exit.
2. Create `.venv` in `vbu-projects-agent/` if missing.
3. `pip install -e .` (normal users; contributors can still use `.[dev]`).
4. Copy `.env.example` → `.env` if `.env` does not exist.
5. Run `vbu-agent doctor` and print next steps.

Re-running must be safe (no clobbering `.env`, no error if `.venv` exists).

### 3. Secrets via a `.env` file

- `.env.example` (committed) contains:
  - `ANTHROPIC_API_KEY=` (blank)
  - A commented example ADO PAT line, e.g. `# MYPROJECT_ADO_PAT=`
- The CLI **auto-loads `.env`** at startup via `python-dotenv` (new dependency), so
  env vars work without manual `export` / `$env:`.
- `.env` stays git-ignored (already covered by `.gitignore`). Each person's secrets
  remain local; secrets are never committed.

### 4. Add-a-project = one command

`vbu-agent project new <id> --name "<Name>"`:

- Copies `projects/_example/` to `projects/<id>/`.
- Substitutes `project.id`, `project.name`, and the `pat_env_var` name.
- Prints the 2–3 fields the user must edit (ADO organization, ADO project, PAT var).

`_example/project.yaml` becomes the **single source of truth** for the project
template. The scaffolder copies `_example/` instead of holding its own inline
`_DEFAULT_PROJECT_YAML` string (removes template drift). The existing
`project create` command remains as an alias to `project new`.

`_example/` ships with realistic placeholder values and empty (scaffolded) context
files so it also serves as a learning reference.

### 5. README — 3 steps

1. `git clone <repo-url>`
2. `./setup.ps1` (Windows) or `bash setup.sh` (Mac/Linux)
3. Put your Claude API key in `vbu-projects-agent/.env`, then
   `vbu-agent project new my-project --name "My Project"` and edit its `project.yaml`.

Followed by the daily/weekly command cheatsheet (reuse existing CLAUDE.md commands),
and a one-line collaboration note: "work inside your own `projects/<id>/` folder and
commit that folder; you rarely touch other people's projects, so merges stay clean."

### 6. Doctor (minor enhancement)

`vbu-agent doctor` gains a check that `.env` was found/loaded and reports whether
`ANTHROPIC_API_KEY` is present, pointing users to `.env` when a secret is missing.
No structural change to the diagnostics table.

## Testing

- **Unit:** `project new` copies `_example/` to a target dir and substitutes
  id/name/pat_env_var correctly; `list_projects` finds the new project.
- **Unit:** config/provider resolution picks up a variable defined only in a temporary
  `.env` file (verifies auto-load).
- **Unit:** scaffolder no longer depends on an inline template string (copies from
  `_example/`), and copying is safe when target exists only with `--force`.
- **Manual:** on a fresh clone on Windows, `setup.ps1` completes and ends at a green
  `vbu-agent doctor`; re-running `setup.ps1` does not clobber `.env`.

## Open Considerations

- **Folder nesting:** the repo root (`VBUProjectsAgent/`) wraps the actual package
  (`vbu-projects-agent/`). This is minor extra complexity. This pass keeps it and
  makes `setup.*` at the root handle the subfolder. Flattening could be a future
  cleanup but is out of scope here to keep the change focused.
- **Multiple teammates, multiple PATs:** each teammate only needs PATs for the
  projects they actually run; `.env` holds whatever subset they have.
