"""Shared fixtures for the VBU-Projects-Agent test suite."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from ..config.models import (
    GlobalConfig, ProjectConfig, ProjectInfo, ProgressModelConfig,
    MilestoneConfig, StageConfig, ManualKpi, AzureDevOpsConfig,
    FieldMappings, WorkItemsConfig, RevenueConfig, ProjectReportingConfig,
    ProjectSlackConfig, HealthThresholds,
)
from ..storage.db import Database, init_db
from ..storage.snapshots import SnapshotManager
from ..ado.work_items import WorkItem


# ---------------------------------------------------------------------------
# Temp directory
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def global_config(tmp_dir: Path) -> GlobalConfig:
    cfg = GlobalConfig()
    object.__setattr__(cfg, "_base_dir", tmp_dir)
    return cfg


@pytest.fixture()
def health_thresholds() -> HealthThresholds:
    return HealthThresholds(green=0.85, yellow=0.65, red=0.0)


@pytest.fixture()
def test_case_project_config(health_thresholds) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectInfo(
            id="project-alpha",
            name="Project Alpha",
            client="Test Client",
            delivery_manager="Joseph",
            health_thresholds=health_thresholds,
        ),
        azure_devops=AzureDevOpsConfig(
            organization="test-org",
            project="TestProject",
            base_url="https://dev.azure.com/test-org",
            pat_env_var="TEST_ADO_PAT",
        ),
        field_mappings=FieldMappings(),
        work_items=WorkItemsConfig(wiql="SELECT [System.Id] FROM WorkItems WHERE [System.State] != 'Removed'"),
        progress_model=ProgressModelConfig(
            type="test_case_milestones",
            done_states=["Done", "Closed", "Passed"],
            milestones=[
                MilestoneConfig(id="alpha", name="Alpha Ready", target_passing=100, target_date="2026-07-12"),
                MilestoneConfig(id="beta", name="Beta Ready", target_passing=200, target_date="2026-08-30"),
            ],
        ),
        revenue=RevenueConfig(monthly_revenue=50000, total_contract_value=600000),
    )


@pytest.fixture()
def staged_tags_project_config(health_thresholds) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectInfo(id="project-beta", name="Project Beta",
                            health_thresholds=health_thresholds),
        azure_devops=AzureDevOpsConfig(pat_env_var="TEST_ADO_PAT"),
        field_mappings=FieldMappings(),
        work_items=WorkItemsConfig(),
        progress_model=ProgressModelConfig(
            type="staged_tags",
            done_states=["Done", "Closed"],
            stages=[
                StageConfig(id="alpha", name="Alpha", tag="AlphaReady", target_count=50),
                StageConfig(id="beta", name="Beta", tag="BetaReady", target_count=100),
            ],
        ),
    )


@pytest.fixture()
def manual_kpi_project_config(health_thresholds) -> ProjectConfig:
    return ProjectConfig(
        project=ProjectInfo(id="project-kpi", name="KPI Project",
                            health_thresholds=health_thresholds),
        azure_devops=AzureDevOpsConfig(pat_env_var="TEST_ADO_PAT"),
        field_mappings=FieldMappings(),
        work_items=WorkItemsConfig(),
        progress_model=ProgressModelConfig(
            type="manual_kpi",
            kpis=[
                ManualKpi(id="migration", name="Data Migration", weight=0.5, current=60, target=100),
                ManualKpi(id="signoff", name="Integration Sign-offs", weight=0.5, current=3, target=5),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Work item fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_case_items() -> list[WorkItem]:
    """78 passing test cases out of 100 target."""
    done = [WorkItem(id=i, title=f"TC-{i}", state="Passed", tags=(), story_points=None, work_item_type="Test Case")
            for i in range(1, 79)]
    pending = [WorkItem(id=i, title=f"TC-{i}", state="Active", tags=(), story_points=None, work_item_type="Test Case")
               for i in range(79, 101)]
    return done + pending


@pytest.fixture()
def staged_tag_items() -> list[WorkItem]:
    """30 AlphaReady done, 20 AlphaReady active; 0 BetaReady done."""
    alpha_done = [WorkItem(id=i, title=f"PBI-{i}", state="Done", tags=("AlphaReady",),
                           story_points=3.0, work_item_type="Product Backlog Item")
                  for i in range(1, 31)]
    alpha_active = [WorkItem(id=i, title=f"PBI-{i}", state="Active", tags=("AlphaReady",),
                             story_points=3.0, work_item_type="Product Backlog Item")
                    for i in range(31, 51)]
    return alpha_done + alpha_active


@pytest.fixture()
def story_point_items() -> list[WorkItem]:
    """10 done (3sp each) + 10 active (3sp each) = 50% complete."""
    done = [WorkItem(id=i, title=f"PBI-{i}", state="Done", tags=(),
                     story_points=3.0, work_item_type="Product Backlog Item")
            for i in range(1, 11)]
    active = [WorkItem(id=i, title=f"PBI-{i}", state="Active", tags=(),
                       story_points=3.0, work_item_type="Product Backlog Item")
              for i in range(11, 21)]
    return done + active


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_dir: Path) -> Database:
    return init_db(tmp_dir / "test.db")


@pytest.fixture()
def snap_mgr(tmp_dir: Path) -> SnapshotManager:
    return SnapshotManager(tmp_dir / "snapshots")


# ---------------------------------------------------------------------------
# Fake Claude provider
# ---------------------------------------------------------------------------

class FakeClaudeProvider:
    mode = "api_key"
    response: str = '{"status_updates": [], "new_risks": [], "decisions": [], "milestone_updates": [], "blockers": [], "asks": []}'

    def complete(self, *, system, prompt, max_tokens, temperature, model=None):
        from ..claude.provider import ClaudeResult
        return ClaudeResult(content=self.response, model="fake", input_tokens=10, output_tokens=20)


class BadNumberFakeProvider:
    """Returns output containing fabricated numbers."""
    mode = "api_key"

    def complete(self, *, system, prompt, max_tokens, temperature, model=None):
        from ..claude.provider import ClaudeResult
        return ClaudeResult(
            content="Project Alpha — Status: Yellow\nProgress: 99% complete with 1 remaining.\nNext milestone: Alpha Ready — 2099-01-01.\n",
            model="fake",
        )


@pytest.fixture()
def fake_provider() -> FakeClaudeProvider:
    return FakeClaudeProvider()


@pytest.fixture()
def bad_number_provider() -> BadNumberFakeProvider:
    return BadNumberFakeProvider()
