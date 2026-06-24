"""Pydantic v2 models for global and project configuration."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Global config models
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    name: str = "VBU-Projects-Agent"
    environment: Literal["local", "staging", "prod"] = "local"
    default_timezone: str = "America/Costa_Rica"

    @field_validator("default_timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            import zoneinfo
            zoneinfo.ZoneInfo(v)
        except Exception:
            raise ValueError(f"Invalid IANA timezone: {v!r}")
        return v


class ClaudeTaskModels(BaseModel):
    classify_input: Optional[str] = None
    reconcile_context: Optional[str] = None
    executive_summary: Optional[str] = None


class ClaudeConfig(BaseModel):
    provider_priority: list[Literal["api_key", "local_cli"]] = ["api_key", "local_cli"]
    api_key_env_var: str = "ANTHROPIC_API_KEY"
    api_key: Optional[str] = None
    model: str = "claude-sonnet-4-6"
    max_tokens: int = Field(default=8000, ge=256, le=64000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    local_cli_enabled: bool = True
    task_models: ClaudeTaskModels = ClaudeTaskModels()

    @field_validator("api_key_env_var")
    @classmethod
    def validate_env_var_name(cls, v: str) -> str:
        if not re.match(r"^[A-Z_][A-Z0-9_]*$", v):
            raise ValueError(f"api_key_env_var must be a valid env-var name, got: {v!r}")
        return v

    @field_validator("provider_priority")
    @classmethod
    def validate_provider_priority(cls, v: list) -> list:
        if not v:
            raise ValueError("provider_priority must not be empty")
        if len(v) != len(set(v)):
            raise ValueError("provider_priority must not have duplicates")
        return v

    @field_validator("api_key")
    @classmethod
    def warn_literal_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            import warnings
            warnings.warn(
                "claude.api_key is set as a literal value in config. "
                "Prefer setting the ANTHROPIC_API_KEY environment variable instead.",
                stacklevel=2,
            )
        return v


class StorageConfig(BaseModel):
    provider: Literal["sqlite"] = "sqlite"
    sqlite_path: str = "data/vbu_projects_agent.db"
    snapshots_path: str = "data/snapshots"
    artifacts_path: str = "artifacts"


class ProjectsConfig(BaseModel):
    root_path: str = "projects"
    input_folder_name: str = "input"
    archive_folder_name: str = "processed_input"

    @field_validator("input_folder_name", "archive_folder_name")
    @classmethod
    def no_path_separators(cls, v: str) -> str:
        if "/" in v or "\\" in v:
            raise ValueError(f"Folder name must not contain path separators: {v!r}")
        return v


class ChartsConfig(BaseModel):
    embed_mode: Literal["inline", "cdn"] = "inline"
    trailing_window_days: int = 30


class ReportsConfig(BaseModel):
    output_path: str = "reports"
    project_report_template: str = "templates/project_status_report.html.j2"
    executive_dashboard_template: str = "templates/executive_dashboard.html.j2"
    charts: ChartsConfig = ChartsConfig()


class SlackConfig(BaseModel):
    default_message_style: str = "executive_short"
    max_words: int = Field(default=180, ge=40, le=400)


class AdoGlobalConfig(BaseModel):
    default_api_version: str = "7.1"
    batch_size: int = Field(default=200, ge=1, le=200)
    cache_ttl_seconds: int = Field(default=900, ge=0)
    max_retries: int = Field(default=3, ge=0, le=10)


class GlobalConfig(BaseModel):
    app: AppConfig = AppConfig()
    claude: ClaudeConfig = ClaudeConfig()
    storage: StorageConfig = StorageConfig()
    projects: ProjectsConfig = ProjectsConfig()
    reports: ReportsConfig = ReportsConfig()
    slack: SlackConfig = SlackConfig()
    ado: AdoGlobalConfig = AdoGlobalConfig()

    # Resolved base directory (set by loader, not from YAML)
    _base_dir: Path = Path(".")

    def resolve_path(self, relative: str) -> Path:
        return self._base_dir / relative


# ---------------------------------------------------------------------------
# Project-level config models
# ---------------------------------------------------------------------------

class HealthThresholds(BaseModel):
    green: float = Field(default=0.85, ge=0.0, le=1.0)
    yellow: float = Field(default=0.65, ge=0.0, le=1.0)
    red: float = Field(default=0.0, ge=0.0, le=1.0)


class ProjectInfo(BaseModel):
    id: str
    name: str
    client: str = ""
    delivery_manager: str = ""
    account_executive: str = ""
    delivery_director: str = ""
    timezone: str = "America/Costa_Rica"
    health_thresholds: HealthThresholds = HealthThresholds()


class AzureDevOpsConfig(BaseModel):
    organization: str = ""
    project: str = ""
    base_url: str = ""
    pat_env_var: str = "ADO_PAT"
    pat_token: None = None  # never set here; always from env
    api_version: str = "7.1"


class FieldMappings(BaseModel):
    id: str = "System.Id"
    title: str = "System.Title"
    state: str = "System.State"
    tags: str = "System.Tags"
    story_points: str = "Microsoft.VSTS.Scheduling.StoryPoints"
    work_item_type: str = "System.WorkItemType"


class WorkItemsConfig(BaseModel):
    wiql: str = ""


class StageConfig(BaseModel):
    id: str
    name: str
    tag: str
    target_count: Optional[int] = None
    done_states: list[str] = ["Done", "Closed", "Passed"]


class MilestoneConfig(BaseModel):
    id: str
    name: str
    target_passing: int
    target_date: str


class ManualKpi(BaseModel):
    id: str
    name: str
    weight: float
    current: float
    target: float


class ProgressModelConfig(BaseModel):
    type: Literal["staged_tags", "test_case_milestones", "weighted_workload", "manual_kpi"]
    tag_field: str = "System.Tags"
    done_states: list[str] = ["Done", "Closed", "Passed"]
    stages: list[StageConfig] = []
    milestones: list[MilestoneConfig] = []
    kpis: list[ManualKpi] = []
    weight_field: str = "story_points"
    type_weights: dict[str, float] = {}


class RevenueConfig(BaseModel):
    currency: str = "USD"
    total_contract_value: float = 0.0
    monthly_revenue: float = 0.0
    revenue_recognition_model: str = "manual"


class ProjectReportingConfig(BaseModel):
    include_risks: bool = True
    include_financials: bool = True
    include_velocity: bool = True
    include_timeline: bool = True


class ProjectSlackConfig(BaseModel):
    channel_hint: str = ""
    tone: str = "concise_executive"
    include: list[str] = ["health", "progress", "next_milestone", "risks", "asks"]


class ProjectConfig(BaseModel):
    project: ProjectInfo
    azure_devops: AzureDevOpsConfig = AzureDevOpsConfig()
    field_mappings: FieldMappings = FieldMappings()
    work_items: WorkItemsConfig = WorkItemsConfig()
    progress_model: ProgressModelConfig
    revenue: RevenueConfig = RevenueConfig()
    reporting: ProjectReportingConfig = ProjectReportingConfig()
    slack: ProjectSlackConfig = ProjectSlackConfig()
