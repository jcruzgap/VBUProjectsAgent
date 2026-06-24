"""Project scaffolding — create folder structure + project.yaml + empty context files."""
from __future__ import annotations

from pathlib import Path

import yaml

from .context_manager import ContextManager

_DEFAULT_PROJECT_YAML = """\
project:
  id: {project_id}
  name: {project_name}
  client: ""
  delivery_manager: ""
  account_executive: ""
  delivery_director: ""
  timezone: America/Costa_Rica
  health_thresholds:
    green: 0.85
    yellow: 0.65
    red: 0.0

azure_devops:
  organization: ""
  project: ""
  base_url: ""
  pat_env_var: {pat_env_var}
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
        """Scaffold a new project folder. Returns the project directory."""
        project_dir = self.root / project_id
        if project_dir.exists() and not force:
            raise FileExistsError(
                f"Project directory already exists: {project_dir}. "
                "Use --force to overwrite."
            )
        project_dir.mkdir(parents=True, exist_ok=True)

        # Sub-directories
        for sub in ["context", "input", "processed_input", "generated"]:
            (project_dir / sub).mkdir(exist_ok=True)

        # project.yaml
        pat_env_var = f"{project_id.upper().replace('-', '_')}_ADO_PAT"
        yaml_path = project_dir / "project.yaml"
        if not yaml_path.exists() or force:
            yaml_path.write_text(
                _DEFAULT_PROJECT_YAML.format(
                    project_id=project_id,
                    project_name=project_name,
                    pat_env_var=pat_env_var,
                ),
                encoding="utf-8",
            )

        # Scaffold empty context files
        ctx_mgr = ContextManager(project_dir / "context")
        ctx_mgr.scaffold_empty_files(project_name)

        return project_dir

    def list_projects(self) -> list[str]:
        """Return project IDs (folder names that have a project.yaml)."""
        return sorted(
            d.name
            for d in self.root.iterdir()
            if d.is_dir() and (d / "project.yaml").exists()
        )

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id
