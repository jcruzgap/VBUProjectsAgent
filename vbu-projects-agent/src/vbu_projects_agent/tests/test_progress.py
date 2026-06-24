"""Tests for the Progress Engine — all 4 strategies + velocity + forecast + health."""
import pytest
from datetime import date, timedelta

from ..progress.engine import ProgressEngine
from ..progress.staged_tags import compute_staged_tags
from ..progress.test_case_milestones import compute_test_case_milestones
from ..progress.weighted_workload import compute_weighted_workload
from ..progress.manual_kpi import compute_manual_kpi
from ..progress.velocity import compute_velocity
from ..progress.forecast import compute_forecast
from ..progress.health import compute_health


class TestStagedTagsStrategy:
    def test_basic_completion(self, staged_tags_project_config, staged_tag_items):
        cfg = staged_tags_project_config.progress_model
        stages, overall, active = compute_staged_tags(staged_tag_items, cfg)
        assert len(stages) == 2
        alpha = stages[0]
        assert alpha.completed == 30
        assert alpha.total == 50
        assert abs(alpha.percent - 0.6) < 0.01
        assert active == "alpha"

    def test_empty_items_zero_progress(self, staged_tags_project_config):
        stages, overall, active = compute_staged_tags([], staged_tags_project_config.progress_model)
        assert overall == 0.0

    def test_all_done_gives_full_progress(self, staged_tags_project_config, staged_tag_items):
        # Mark all as done
        from ..ado.work_items import WorkItem
        all_done = [
            WorkItem(id=i, title=f"PBI-{i}", state="Done", tags=("AlphaReady",),
                     story_points=1.0, work_item_type="Product Backlog Item")
            for i in range(1, 51)
        ]
        cfg = staged_tags_project_config.progress_model
        stages, overall, active = compute_staged_tags(all_done, cfg)
        alpha = stages[0]
        assert alpha.percent == 1.0
        assert alpha.status == "done"

    def test_via_engine(self, staged_tags_project_config, staged_tag_items, health_thresholds):
        engine = ProgressEngine()
        result = engine.compute(
            items=staged_tag_items,
            config=staged_tags_project_config.progress_model,
            health_thresholds=health_thresholds,
            history=[],
        )
        assert result.health in ("green", "yellow", "red")
        assert 0.0 <= result.overall_percent <= 1.0
        assert result.active_stage == "alpha"


class TestTestCaseMilestonesStrategy:
    def test_78_of_100_passing(self, test_case_project_config, test_case_items):
        cfg = test_case_project_config.progress_model
        milestones, overall, active, forecast = compute_test_case_milestones(
            test_case_items, cfg, []
        )
        assert len(milestones) == 2
        alpha = milestones[0]
        assert alpha.passing == 78
        assert alpha.remaining == 22
        assert abs(alpha.percent - 0.78) < 0.01
        assert active == "alpha"

    def test_zero_items_zero_progress(self, test_case_project_config):
        milestones, overall, active, forecast = compute_test_case_milestones(
            [], test_case_project_config.progress_model, []
        )
        assert overall == 0.0

    def test_all_passing_milestone_done(self, test_case_project_config):
        from ..ado.work_items import WorkItem
        all_passing = [
            WorkItem(id=i, title=f"TC-{i}", state="Passed", tags=(),
                     story_points=None, work_item_type="Test Case")
            for i in range(1, 201)
        ]
        cfg = test_case_project_config.progress_model
        milestones, overall, active, forecast = compute_test_case_milestones(
            all_passing, cfg, []
        )
        alpha = milestones[0]
        assert alpha.state == "done"
        assert alpha.percent == 1.0

    def test_forecast_suppressed_no_history(self, test_case_project_config, test_case_items):
        milestones, overall, active, forecast = compute_test_case_milestones(
            test_case_items, test_case_project_config.progress_model, []
        )
        # With no history, forecast may be None or suppressed
        if forecast is not None:
            assert forecast.forecast_date is None or forecast.confidence == "low"


class TestWeightedWorkload:
    def test_50_percent(self, story_point_items):
        from ..config.models import ProgressModelConfig
        cfg = ProgressModelConfig(type="weighted_workload", done_states=["Done"])
        overall, done_w, total_w = compute_weighted_workload(story_point_items, cfg)
        assert abs(overall - 0.5) < 0.01
        assert done_w == 30.0  # 10 items × 3sp
        assert total_w == 60.0  # 20 items × 3sp

    def test_empty_is_zero(self):
        from ..config.models import ProgressModelConfig
        cfg = ProgressModelConfig(type="weighted_workload", done_states=["Done"])
        overall, _, _ = compute_weighted_workload([], cfg)
        assert overall == 0.0


class TestManualKpi:
    def test_weighted_average(self, manual_kpi_project_config):
        cfg = manual_kpi_project_config.progress_model
        kpis, overall = compute_manual_kpi(cfg)
        assert len(kpis) == 2
        # migration: 60/100 = 60%, weight 0.5 → 0.30
        # signoff: 3/5 = 60%, weight 0.5 → 0.30
        assert abs(overall - 0.6) < 0.01

    def test_empty_kpis_zero(self):
        from ..config.models import ProgressModelConfig
        cfg = ProgressModelConfig(type="manual_kpi", kpis=[])
        _, overall = compute_manual_kpi(cfg)
        assert overall == 0.0


class TestVelocity:
    def test_returns_none_on_single_point(self):
        history = [{"measured_at": "2026-06-01T00:00:00+00:00", "overall_percent": 0.5}]
        result = compute_velocity(history)
        assert result is None

    def test_positive_slope(self):
        from datetime import datetime, timezone, timedelta
        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        history = [
            {"measured_at": (base + timedelta(days=i)).isoformat(),
             "overall_percent": 0.0 + i * 0.05}
            for i in range(10)
        ]
        result = compute_velocity(history)
        assert result is not None
        assert result.per_day > 0

    def test_zero_velocity_on_flat_trend(self):
        from datetime import datetime, timezone, timedelta
        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        history = [
            {"measured_at": (base + timedelta(days=i)).isoformat(),
             "overall_percent": 0.5}
            for i in range(5)
        ]
        result = compute_velocity(history)
        # Flat → velocity is 0 or None
        if result:
            assert result.per_day == 0.0


class TestForecast:
    def test_basic_forecast(self):
        from ..progress.velocity import VelocityResult
        vel = VelocityResult(per_day=5.0, window_days=30, data_points=10, confidence="high")
        result = compute_forecast(remaining=50.0, velocity=vel)
        assert result.forecast_date is not None
        assert result.days_remaining == 10

    def test_suppressed_no_velocity(self):
        result = compute_forecast(remaining=50.0, velocity=None)
        assert result.forecast_date is None
        assert result.confidence == "low"

    def test_suppressed_thin_history(self):
        from ..progress.velocity import VelocityResult
        vel = VelocityResult(per_day=5.0, window_days=30, data_points=2, confidence="low")
        result = compute_forecast(remaining=50.0, velocity=vel)
        assert result.forecast_date is None

    def test_at_risk_when_past_target(self):
        from ..progress.velocity import VelocityResult
        vel = VelocityResult(per_day=1.0, window_days=30, data_points=10, confidence="medium")
        yesterday = date.today() - timedelta(days=1)
        result = compute_forecast(remaining=100.0, velocity=vel, target_date=yesterday)
        assert "at risk" in (result.note or "").lower() or result.forecast_date > yesterday


class TestHealth:
    def test_green_high_progress(self, health_thresholds):
        color, reasons = compute_health(0.90, health_thresholds)
        assert color == "green"

    def test_yellow_mid_progress(self, health_thresholds):
        color, reasons = compute_health(0.70, health_thresholds)
        assert color == "yellow"

    def test_red_low_progress(self, health_thresholds):
        color, reasons = compute_health(0.40, health_thresholds)
        assert color == "red"

    def test_risk_downgrades_green(self, health_thresholds):
        color, reasons = compute_health(0.90, health_thresholds, open_high_risks=2)
        assert color in ("yellow", "red")
        assert any("risk" in r.lower() for r in reasons)

    def test_blocker_downgrades(self, health_thresholds):
        color, reasons = compute_health(0.90, health_thresholds, has_blockers=True)
        assert color in ("yellow", "red")
