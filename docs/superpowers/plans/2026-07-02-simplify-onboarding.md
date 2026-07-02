# Simplify VBU-Projects-Agent Onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a teammate clone the repo, run one setup command, drop their Claude key in a `.env` file, and add a project with a single command — all sharing one committed structure.

**Architecture:** Add a thin onboarding layer on top of the existing engine. A root bootstrap script installs the package into a venv; a `.env` file (auto-loaded at startup) supplies secrets; new projects are created by copying a committed `projects/_example/` template. The engine (ADO, progress, reporting, MCP, storage, security) is untouched.

**Tech Stack:** Python 3.11+, Typer CLI, python-dotenv (new), PowerShell + Bash scripts, pytest.

**Path conventions in this plan:**
- Repo root = `c:\Dev\Agents\VBUProjectsAgent` (the clone target).
- Package root = `vbu-projects-agent/` under the repo root.
- All command examples run from the **package root** (`vbu-projects-agent/`), because the CLI resolves `config/vbu-agent.yaml` and `projects/` relative to the current working directory.

---

## File Structure

- `vbu-projects-agent/src/vbu_projects_agent/env.py` — **new**: `.env` loader (single responsibility: read secrets into `os.environ`).
- `vbu-projects-agent/src/vbu_projects_agent/cli.py` — **modify**: load `.env` in the callback; add `project new` command.
- `vbu-projects-agent/src/vbu_projects_agent/orchestrator.py` — **modify**: load `.env` in `__init__`; add a `.env` row to `doctor`.
- `vbu-projects-agent/src/vbu_projects_agent/projects/scaffolder.py` — **modify**: copy `_example/` instead of inline template; exclude `_example` from `list_projects`.
- `vbu-projects-agent/pyproject.toml` — **modify**: add `python-dotenv` dependency.
- `vbu-projects-agent/.env.example` — **new**: committed secrets template.
- `vbu-projects-agent/projects/_example/` — **new**: committed sample project (the template).
- `setup.ps1`, `setup.sh` — **new** at repo root: one-command bootstrap.
- `README.md` (repo root) — **modify**: 3-step quickstart.
- `vbu-projects-agent/.claude/commands/onboard-project.md`, `vbu-projects-agent/CLAUDE.md` — **modify**: reflect the simpler flow.
- Tests: `vbu-projects-agent/src/vbu_projects_agent/tests/test_env.py` (**new**), `test_context.py` (**modify**).

---

## Task 1: `.env` auto-loading

**Files:**
- Create: `vbu-projects-agent/src/vbu_projects_agent/env.py`
- Create test: `vbu-projects-agent/src/vbu_projects_agent/tests/test_env.py`
- Modify: `vbu-projects-agent/pyproject.toml:10-22`

- [ ] **Step 1: Add the dependency**

In `vbu-projects-agent/pyproject.toml`, add `python-dotenv` to `dependencies` (after `"python-dateutil>=2.9",`):

```toml
    "python-dateutil>=2.9",
    "python-dotenv>=1.0",
    "rich>=13.7",
```

- [ ] **Step 2: Install it**

Run (from `vbu-projects-agent/`, venv active): `pip install -e ".[dev]"`
Expected: installs `python-dotenv` with no errors.

- [ ] **Step 3: Write the failing test**

Create `vbu-projects-agent/src/vbu_projects_agent/tests/test_env.py`:

```python
"""Tests for .env auto-loading."""
import os
from pathlib import Path

from ..env import load_env_file


class TestLoadEnvFile:
    def test_loads_var_from_explicit_base_dir(self, tmp_dir: Path, monkeypatch):
        monkeypatch.delenv("VBU_ENV_TEST", raising=False)
        (tmp_dir / ".env").write_text("VBU_ENV_TEST=loaded\n", encoding="utf-8")
        used = load_env_file(tmp_dir)
        assert used == tmp_dir / ".env"
        assert os.environ["VBU_ENV_TEST"] == "loaded"

    def test_does_not_override_existing_var(self, tmp_dir: Path, monkeypatch):
        monkeypatch.setenv("VBU_ENV_TEST", "from-shell")
        (tmp_dir / ".env").write_text("VBU_ENV_TEST=from-file\n", encoding="utf-8")
        load_env_file(tmp_dir)
        assert os.environ["VBU_ENV_TEST"] == "from-shell"

    def test_returns_none_when_no_env_file(self, tmp_dir: Path):
        missing = tmp_dir / "no-such-dir"
        missing.mkdir()
        assert load_env_file(missing) is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest src/vbu_projects_agent/tests/test_env.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vbu_projects_agent.env'`

- [ ] **Step 5: Write the implementation**

Create `vbu-projects-agent/src/vbu_projects_agent/env.py`:

```python
"""Load secrets from a .env file into the environment at startup.

Existing environment variables always win over .env values, so a value
exported in the shell is never clobbered by the file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv


def load_env_file(base_dir: Optional[Path] = None) -> Optional[Path]:
    """Load `.env` into os.environ (without overriding existing vars).

    If `base_dir` is given and `base_dir/.env` exists, that file is used.
    Otherwise the nearest `.env` walking up from the current directory is used.
    Returns the path loaded, or None if no `.env` was found.
    """
    if base_dir is not None:
        candidate = Path(base_dir) / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate

    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
        return Path(found)
    return None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest src/vbu_projects_agent/tests/test_env.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add vbu-projects-agent/pyproject.toml vbu-projects-agent/src/vbu_projects_agent/env.py vbu-projects-agent/src/vbu_projects_agent/tests/test_env.py
git commit -m "feat: add .env auto-loader"
```

---

## Task 2: Hook `.env` loading into the CLI and orchestrator

**Files:**
- Modify: `vbu-projects-agent/src/vbu_projects_agent/cli.py:48-65`
- Modify: `vbu-projects-agent/src/vbu_projects_agent/orchestrator.py:29-35`

- [ ] **Step 1: Load `.env` in the CLI callback**

In `vbu-projects-agent/src/vbu_projects_agent/cli.py`, inside `main_callback`, after the `global` statement and before configuring logging, add the load call. Replace this block:

```python
    global _BASE_DIR, _CONFIG_PATH, _VERBOSE
    _BASE_DIR = base_dir
    _CONFIG_PATH = config
    _VERBOSE = verbose
```

with:

```python
    global _BASE_DIR, _CONFIG_PATH, _VERBOSE
    _BASE_DIR = base_dir
    _CONFIG_PATH = config
    _VERBOSE = verbose

    from .env import load_env_file
    load_env_file(base_dir)
```

- [ ] **Step 2: Load `.env` in the orchestrator**

In `vbu-projects-agent/src/vbu_projects_agent/orchestrator.py`, in `Orchestrator.__init__`, load `.env` before reading config. Replace:

```python
    def __init__(self, base_dir: Path, config_path: Optional[Path] = None) -> None:
        self.base_dir = base_dir
        self.cfg = load_global_config(config_path or base_dir / "config" / "vbu-agent.yaml",
                                      base_dir=base_dir)
```

with:

```python
    def __init__(self, base_dir: Path, config_path: Optional[Path] = None) -> None:
        self.base_dir = base_dir
        from .env import load_env_file
        load_env_file(base_dir)
        self.cfg = load_global_config(config_path or base_dir / "config" / "vbu-agent.yaml",
                                      base_dir=base_dir)
```

- [ ] **Step 3: Verify nothing broke**

Run: `pytest -q`
Expected: all existing tests still pass (no new failures).

- [ ] **Step 4: Commit**

```bash
git add vbu-projects-agent/src/vbu_projects_agent/cli.py vbu-projects-agent/src/vbu_projects_agent/orchestrator.py
git commit -m "feat: auto-load .env in CLI and orchestrator"
```

---

## Task 3: Scaffolder copies `_example/` template

**Files:**
- Modify: `vbu-projects-agent/src/vbu_projects_agent/projects/scaffolder.py` (whole file)
- Modify test: `vbu-projects-agent/src/vbu_projects_agent/tests/test_context.py:59-86`

- [ ] **Step 1: Write the failing tests**

In `vbu-projects-agent/src/vbu_projects_agent/tests/test_context.py`, replace the entire `class TestScaffolder:` block (lines 59-86) with:

```python
class TestScaffolder:
    def test_create_project(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        project_dir = scaffolder.create("my-project", "My Project")
        assert project_dir.exists()
        assert (project_dir / "project.yaml").exists()
        assert (project_dir / "context").exists()
        assert (project_dir / "input").exists()

    def test_create_substitutes_id_name_and_pat_var(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        project_dir = scaffolder.create("my-project", "My Project")
        text = (project_dir / "project.yaml").read_text(encoding="utf-8")
        assert "id: my-project" in text
        assert "name: My Project" in text
        assert "MY_PROJECT_ADO_PAT" in text

    def test_create_from_committed_example(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("my-project", "My Project")
        assert (tmp_dir / "projects" / "_example" / "project.yaml").exists()

    def test_create_already_exists_raises(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("my-project", "My Project")
        with pytest.raises(FileExistsError):
            scaffolder.create("my-project", "My Project")

    def test_create_force_overwrites(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("my-project", "My Project")
        scaffolder.create("my-project", "My Project v2", force=True)
        assert (tmp_dir / "projects" / "my-project" / "project.yaml").exists()

    def test_list_projects_excludes_example(self, tmp_dir: Path):
        scaffolder = ProjectScaffolder(tmp_dir / "projects")
        scaffolder.create("alpha", "Alpha")
        scaffolder.create("beta", "Beta")
        projects = scaffolder.list_projects()
        assert "alpha" in projects
        assert "beta" in projects
        assert "_example" not in projects
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest src/vbu_projects_agent/tests/test_context.py::TestScaffolder -v`
Expected: FAIL — `test_create_substitutes_id_name_and_pat_var`, `test_create_from_committed_example`, and `test_list_projects_excludes_example` fail (the current scaffolder generates from an inline template and lists `_example`).

- [ ] **Step 3: Rewrite the scaffolder**

Replace the entire contents of `vbu-projects-agent/src/vbu_projects_agent/projects/scaffolder.py` with:

```python
"""Project scaffolding — new projects are created by copying the committed
`_example/` template and substituting the project id, name, and PAT var name.

`_example/` is the single source of truth for the project template. If it is
missing (fresh checkout with the example not yet generated, or tests), it is
regenerated from `_EXAMPLE_PROJECT_YAML` below.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from .context_manager import ContextManager

EXAMPLE_ID = "_example"

_EXAMPLE_PROJECT_YAML = """\
project:
  id: example
  name: Example Project
  client: "Example Client"
  delivery_manager: "Your Name"
  account_executive: ""
  delivery_director: ""
  timezone: America/Costa_Rica
  health_thresholds:
    green: 0.85
    yellow: 0.65
    red: 0.0

azure_devops:
  # Fill these three in for your own project:
  organization: "your-org"          # e.g. the org in https://dev.azure.com/<org>
  project: "Your ADO Project"        # the Azure DevOps project name
  base_url: "https://dev.azure.com/your-org"
  # Name of the environment variable (set it in your .env) holding your PAT:
  pat_env_var: EXAMPLE_ADO_PAT
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
      target_date: ""
    - id: beta
      name: Beta Ready
      target_passing: 200
      target_date: ""
    - id: production
      name: Production Ready
      target_passing: 300
      target_date: ""

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
  channel_hint: ""
  tone: concise_executive
  include: [health, progress, next_milestone, risks, asks]
"""

_SUBDIRS = ["context", "input", "processed_input", "generated"]


def _substitute(text: str, project_id: str, project_name: str, pat_env_var: str) -> str:
    """Rewrite the first `id:`, first `name:`, and `pat_env_var:` lines.

    In the template the first `id:`/`name:` belong to the top-level `project:`
    block, so a single substitution each targets the right lines.
    """
    text = re.sub(r"(?m)^(\s*id:\s*).*$", rf"\g<1>{project_id}", text, count=1)
    text = re.sub(r"(?m)^(\s*name:\s*).*$", rf"\g<1>{project_name}", text, count=1)
    text = re.sub(r"(?m)^(\s*pat_env_var:\s*).*$", rf"\g<1>{pat_env_var}", text, count=1)
    return text


def ensure_example_project(projects_root: Path) -> Path:
    """Create `projects_root/_example/` from the canonical template if missing.

    Idempotent — never overwrites an existing `_example/project.yaml`.
    """
    projects_root.mkdir(parents=True, exist_ok=True)
    example_dir = projects_root / EXAMPLE_ID
    example_dir.mkdir(exist_ok=True)
    for sub in _SUBDIRS:
        (example_dir / sub).mkdir(exist_ok=True)
    yaml_path = example_dir / "project.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(_EXAMPLE_PROJECT_YAML, encoding="utf-8")
    ContextManager(example_dir / "context").scaffold_empty_files("Example Project")
    return example_dir


class ProjectScaffolder:
    def __init__(self, projects_root: Path) -> None:
        self.root = projects_root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        project_id: str,
        project_name: str,
        force: bool = False,
    ) -> Path:
        """Create a new project by copying the `_example/` template."""
        project_dir = self.root / project_id
        if project_dir.exists() and not force:
            raise FileExistsError(
                f"Project directory already exists: {project_dir}. "
                "Use --force to overwrite."
            )

        example_dir = ensure_example_project(self.root)
        shutil.copytree(example_dir, project_dir, dirs_exist_ok=force)

        pat_env_var = f"{project_id.upper().replace('-', '_')}_ADO_PAT"
        yaml_path = project_dir / "project.yaml"
        yaml_path.write_text(
            _substitute(
                yaml_path.read_text(encoding="utf-8"),
                project_id,
                project_name,
                pat_env_var,
            ),
            encoding="utf-8",
        )
        return project_dir

    def list_projects(self) -> list[str]:
        """Return project IDs (folders with a project.yaml), excluding `_example`."""
        return sorted(
            d.name
            for d in self.root.iterdir()
            if d.is_dir()
            and not d.name.startswith("_")
            and (d / "project.yaml").exists()
        )

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest src/vbu_projects_agent/tests/test_context.py::TestScaffolder -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: all pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add vbu-projects-agent/src/vbu_projects_agent/projects/scaffolder.py vbu-projects-agent/src/vbu_projects_agent/tests/test_context.py
git commit -m "feat: create projects by copying committed _example template"
```

---

## Task 4: Generate and commit `projects/_example/`

**Files:**
- Create: `vbu-projects-agent/projects/_example/` (via the CLI)

- [ ] **Step 1: Generate the example**

Run (from `vbu-projects-agent/`, venv active):

```bash
python -c "from pathlib import Path; from vbu_projects_agent.projects.scaffolder import ensure_example_project; ensure_example_project(Path('projects'))"
```

Expected: creates `projects/_example/project.yaml`, `projects/_example/context/*.md`, and empty `input/`, `processed_input/`, `generated/` dirs.

- [ ] **Step 2: Confirm the example content**

Run: `cat projects/_example/project.yaml`
Expected: shows `id: example`, `name: Example Project`, `pat_env_var: EXAMPLE_ADO_PAT`, with the "Fill these three in" comments.

- [ ] **Step 3: Force-add the example (its subfolders are otherwise git-ignored)**

Note: `.gitignore` excludes `projects/*/input/`, `projects/*/generated/`, and `projects/*/processed_input/`. We only want the committed reference to include `project.yaml` and `context/`, which are NOT ignored — so a normal add is correct and the ignored empty dirs are simply left out.

```bash
git add vbu-projects-agent/projects/_example/project.yaml vbu-projects-agent/projects/_example/context
git status
```

Expected: `project.yaml` and the `context/*.md` files are staged; the ignored subfolders do not appear.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: add committed _example project template"
```

---

## Task 5: Add the `project new` command

**Files:**
- Modify: `vbu-projects-agent/src/vbu_projects_agent/cli.py:127-144`

- [ ] **Step 1: Refactor `create` and add `new`**

In `vbu-projects-agent/src/vbu_projects_agent/cli.py`, replace the whole `cmd_project_create` function (lines 127-144) with a shared helper plus two commands:

```python
def _create_project(project: str, name: str, force: bool) -> None:
    from .projects.scaffolder import ProjectScaffolder
    orch = _orchestrator()
    scaffolder = ProjectScaffolder(orch.base_dir / orch.cfg.projects.root_path)
    try:
        project_dir = scaffolder.create(project, name, force=force)
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] Project created at {project_dir}")
    console.print("  Next steps:")
    console.print(f"    1. Edit [bold]{project_dir / 'project.yaml'}[/bold] — set azure_devops.organization, project, base_url")
    console.print(f"    2. Add your PAT to [bold].env[/bold] as [bold]{project.upper().replace('-', '_')}_ADO_PAT=...[/bold]")
    console.print(f"    3. Run: [bold]vbu-agent project sync-ado --project {project}[/bold]")


@project_app.command("new")
def cmd_project_new(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (folder name)"),
    name: str = typer.Option(..., "--name", "-n", help="Human-readable project name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create a new project by copying the _example template."""
    _create_project(project, name, force)


@project_app.command("create")
def cmd_project_create(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (folder name)"),
    name: str = typer.Option(..., "--name", "-n", help="Human-readable project name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Alias for `project new`."""
    _create_project(project, name, force)
```

- [ ] **Step 2: Smoke-test the command**

Run (from `vbu-projects-agent/`): `vbu-agent project new --project demo-proj --name "Demo Project"`
Expected: prints "Project created at …/projects/demo-proj" and the 3 next-steps lines.

- [ ] **Step 3: Verify the generated file**

Run: `cat projects/demo-proj/project.yaml`
Expected: `id: demo-proj`, `name: Demo Project`, `pat_env_var: DEMO_PROJ_ADO_PAT`.

- [ ] **Step 4: Clean up the smoke-test project**

```bash
rm -rf projects/demo-proj
```

- [ ] **Step 5: Commit**

```bash
git add vbu-projects-agent/src/vbu_projects_agent/cli.py
git commit -m "feat: add 'project new' command (create by copying template)"
```

---

## Task 6: Add a `.env` check to `doctor`

**Files:**
- Modify: `vbu-projects-agent/src/vbu_projects_agent/orchestrator.py:324-334`

- [ ] **Step 1: Add the check**

In `vbu-projects-agent/src/vbu_projects_agent/orchestrator.py`, in the `doctor` method, immediately after `results: dict[str, str] = {}` (the first line of the method body), insert:

```python
        import os
        env_path = self.base_dir / ".env"
        has_key = bool(os.environ.get(self.cfg.claude.api_key_env_var, "").strip())
        if env_path.exists() and has_key:
            results["secrets"] = "OK (.env loaded, API key present)"
        elif env_path.exists():
            results["secrets"] = f"WARN: .env found but {self.cfg.claude.api_key_env_var} is empty"
        else:
            results["secrets"] = "WARN: no .env file — copy .env.example to .env and add your key"
```

- [ ] **Step 2: Verify doctor runs**

Run (from `vbu-projects-agent/`): `vbu-agent doctor`
Expected: the diagnostics table now includes a `secrets` row.

- [ ] **Step 3: Commit**

```bash
git add vbu-projects-agent/src/vbu_projects_agent/orchestrator.py
git commit -m "feat: report .env/secret status in doctor"
```

---

## Task 7: `.env.example` and `.gitignore` confirmation

**Files:**
- Create: `vbu-projects-agent/.env.example`
- Read: `vbu-projects-agent/.gitignore`

- [ ] **Step 1: Create `.env.example`**

Create `vbu-projects-agent/.env.example`:

```bash
# Copy this file to `.env` (same folder) and fill in your secrets.
# `.env` is git-ignored — your secrets never get committed.

# Required: your Anthropic API key (for Claude-written prose).
ANTHROPIC_API_KEY=

# Optional: Azure DevOps Personal Access Tokens, one per project.
# The variable name must match `azure_devops.pat_env_var` in that project's
# project.yaml. Example for a project created as `--project my-project`:
# MY_PROJECT_ADO_PAT=
```

- [ ] **Step 2: Confirm `.env` is git-ignored**

Run: `grep -n "^.env$" vbu-projects-agent/.gitignore`
Expected: matches line `.env` (already present). If it is NOT present, add a line `.env` to `vbu-projects-agent/.gitignore`.

- [ ] **Step 3: Commit**

```bash
git add vbu-projects-agent/.env.example
git commit -m "docs: add .env.example secrets template"
```

---

## Task 8: One-command setup scripts

**Files:**
- Create: `setup.ps1` (repo root)
- Create: `setup.sh` (repo root)

- [ ] **Step 1: Create `setup.ps1`**

Create `setup.ps1` at the repo root:

```powershell
#!/usr/bin/env pwsh
# One-command setup for VBU-Projects-Agent (Windows / PowerShell).
# Safe to re-run.
$ErrorActionPreference = "Stop"
$pkg = Join-Path $PSScriptRoot "vbu-projects-agent"

Write-Host "==> Checking Python..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python 3.11+ is required but was not found. Install from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
    exit 1
}

Set-Location $pkg

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "==> Installing the vbu-agent package..." -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".venv\Scripts\python.exe" -m pip install -e .

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
}

Write-Host "==> Running diagnostics..." -ForegroundColor Cyan
& ".venv\Scripts\vbu-agent.exe" doctor

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. cd vbu-projects-agent"
Write-Host "  2. Activate the venv:  .venv\Scripts\Activate.ps1"
Write-Host "  3. Edit .env and set ANTHROPIC_API_KEY"
Write-Host "  4. Add your project:  vbu-agent project new --project my-project --name ""My Project"""
```

- [ ] **Step 2: Create `setup.sh`**

Create `setup.sh` at the repo root:

```bash
#!/usr/bin/env bash
# One-command setup for VBU-Projects-Agent (macOS / Linux).
# Safe to re-run.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$SCRIPT_DIR/vbu-projects-agent"

echo "==> Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required but was not found. Install it and re-run." >&2
  exit 1
fi

cd "$PKG"

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi

echo "==> Installing the vbu-agent package..."
./.venv/bin/python -m pip install --upgrade pip >/dev/null
./.venv/bin/python -m pip install -e .

if [ ! -f ".env" ]; then
  echo "==> Creating .env from .env.example..."
  cp .env.example .env
fi

echo "==> Running diagnostics..."
./.venv/bin/vbu-agent doctor || true

cat <<'EOF'

Setup complete. Next steps:
  1. cd vbu-projects-agent
  2. Activate the venv:  source .venv/bin/activate
  3. Edit .env and set ANTHROPIC_API_KEY
  4. Add your project:  vbu-agent project new --project my-project --name "My Project"
EOF
```

- [ ] **Step 3: Make `setup.sh` executable**

Run: `git update-index --chmod=+x setup.sh` (or `chmod +x setup.sh` on a POSIX shell)
Expected: no output; the file becomes executable.

- [ ] **Step 4: Commit**

```bash
git add setup.ps1 setup.sh
git commit -m "feat: add one-command setup scripts for Windows and Unix"
```

---

## Task 9: Rewrite the README and update onboarding docs

**Files:**
- Modify: `README.md` (repo root) — replace whole file
- Modify: `vbu-projects-agent/.claude/commands/onboard-project.md` — replace whole file
- Modify: `vbu-projects-agent/CLAUDE.md:7-30` — update the Setup command block

- [ ] **Step 1: Rewrite the root `README.md`**

Replace the entire contents of `README.md` (repo root) with:

```markdown
# VBU-Projects-Agent

A shared workspace for Velocity Business Unit Delivery Managers. It keeps project
context, measures delivery progress from Azure DevOps, and produces executive Slack
messages, HTML reports, and a portfolio dashboard.

Everyone on the team uses **one repo**. Your projects live under
`vbu-projects-agent/projects/` alongside everyone else's — clone once, add your own.

## Get started (3 steps)

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd VBUProjectsAgent
   ```

2. **Run setup** (creates the venv, installs the tool, makes your `.env`)
   - Windows:  `./setup.ps1`
   - macOS/Linux:  `bash setup.sh`

3. **Add your key and your project**
   ```bash
   cd vbu-projects-agent
   # Windows: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
   # Edit .env and set ANTHROPIC_API_KEY
   vbu-agent project new --project my-project --name "My Project"
   ```
   Then edit `projects/my-project/project.yaml` (Azure DevOps org/project) and add
   your ADO PAT to `.env` as `MY_PROJECT_ADO_PAT=...`.

Run `vbu-agent doctor` any time to check your setup.

## Working with the team

- Each person works inside their **own** `projects/<id>/` folder and commits it.
- Look at `projects/_example/` for a template of every field.
- Because everyone stays in their own folder, merges are clean.

## Daily / weekly commands

```bash
vbu-agent project update --project <id>       # ingest notes into context
vbu-agent project slack-status --project <id> # copy-ready Slack status
vbu-agent project sync-ado --project <id>     # pull ADO metrics
vbu-agent project report --project <id> --open# HTML report
vbu-agent dashboard generate --open           # portfolio dashboard
vbu-agent project list                        # all projects + health
```

## Secrets

Secrets live only in `vbu-projects-agent/.env` (git-ignored). Never commit keys or
PATs. See `.env.example` for the template.
```

- [ ] **Step 2: Rewrite the onboarding slash-command doc**

Replace the entire contents of `vbu-projects-agent/.claude/commands/onboard-project.md` with:

```markdown
# Onboard New Project

Create and configure a new project in the shared workspace.

**Usage:** `/onboard-project <project-id> <"Project Name">`

## Steps

Parse the arguments: first word = project-id, rest = project name.

1. Create the project by copying the `_example` template:
```bash
vbu-agent project new --project <project-id> --name "<Project Name>"
```

2. Open `projects/<project-id>/project.yaml` and help the user fill in the three
   Azure DevOps fields: `organization`, `project`, `base_url`.

3. Add the PAT to `.env` (never to YAML). The variable name is printed by
   `project new` — e.g. `MY_PROJECT_ADO_PAT=...`.

4. Confirm setup:
```bash
vbu-agent doctor
```

5. Pull metrics and generate the first Slack status:
```bash
vbu-agent project sync-ado --project <project-id>
vbu-agent project slack-status --project <project-id>
```
```

- [ ] **Step 3: Update the CLAUDE.md setup block**

In `vbu-projects-agent/CLAUDE.md`, replace the `# Setup` portion of the Key commands block (lines 9-15, from `# Setup` through `vbu-agent doctor`) with:

```bash
# Setup (from the repo root, one command)
./setup.ps1            # Windows   (bash setup.sh on macOS/Linux)
# then, inside vbu-projects-agent/ with the venv active:
vbu-agent project new --project <id> --name "<Name>"  # add a project
vbu-agent doctor                                        # check setup
```

- [ ] **Step 4: Commit**

```bash
git add README.md vbu-projects-agent/.claude/commands/onboard-project.md vbu-projects-agent/CLAUDE.md
git commit -m "docs: rewrite README and onboarding for the simplified flow"
```

---

## Task 10: End-to-end manual verification (fresh setup)

**Files:** none (verification only)

- [ ] **Step 1: Simulate a clean setup**

From the repo root, delete the venv to simulate a fresh clone, then run setup:

```bash
rm -rf vbu-projects-agent/.venv
./setup.ps1
```

Expected: creates `.venv`, installs the package, creates `vbu-projects-agent/.env` from the example, prints a `doctor` table ending with the next-steps message. The `secrets` row shows a WARN (key not set yet) — that is expected.

- [ ] **Step 2: Re-run setup (idempotency)**

Run: `./setup.ps1`
Expected: completes without error and does **not** overwrite `.env` (any edits you made are preserved).

- [ ] **Step 3: Create and remove a test project**

```bash
cd vbu-projects-agent
.venv/Scripts/vbu-agent.exe project new --project verify-me --name "Verify Me"
cat projects/verify-me/project.yaml   # id: verify-me, name: Verify Me, VERIFY_ME_ADO_PAT
.venv/Scripts/vbu-agent.exe project list   # shows verify-me, NOT _example
rm -rf projects/verify-me
```

Expected: project created with substituted values; `project list` excludes `_example`.

- [ ] **Step 4: Full test suite**

Run (from `vbu-projects-agent/`): `pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Final commit (if any incidental fixes were needed)**

```bash
git add -A
git commit -m "chore: verify simplified onboarding end-to-end" || echo "nothing to commit"
```

---

## Self-Review Notes

- **Spec coverage:** repo layout (Tasks 4, 8, 9) · one-command setup (Task 8) · `.env` secrets + auto-load (Tasks 1, 2, 7) · `project new` copies `_example` single-source template (Tasks 3, 4, 5) · 3-step README (Task 9) · doctor `.env` check (Task 6) · engine unchanged (no engine files modified) · tests (Tasks 1, 3, 10).
- **Type/name consistency:** `load_env_file(base_dir)`, `ensure_example_project(projects_root)`, `EXAMPLE_ID`, `_substitute(...)`, and the `MY_PROJECT_ADO_PAT` PAT-var convention are used identically everywhere they appear.
- **Non-goal respected:** the `VBUProjectsAgent/vbu-projects-agent/` nesting is kept; setup scripts sit at the repo root and operate on the subfolder.
```
