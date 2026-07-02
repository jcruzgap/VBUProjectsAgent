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
