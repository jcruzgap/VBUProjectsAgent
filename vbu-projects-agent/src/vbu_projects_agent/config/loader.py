"""Config loading with CLI > env > YAML > defaults precedence."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import GlobalConfig, ProjectConfig

_DEFAULT_CONFIG_PATH = Path("config/vbu-agent.yaml")


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins on conflicts)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_global_config(
    config_path: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    overrides: Optional[dict] = None,
) -> GlobalConfig:
    """Load and validate global config from YAML + optional dict overrides."""
    path = config_path or _DEFAULT_CONFIG_PATH
    base = base_dir or path.parent.parent

    raw: dict[str, Any] = {}
    if path.exists():
        with path.open() as f:
            raw = yaml.safe_load(f) or {}

    if overrides:
        raw = _deep_merge(raw, overrides)

    cfg = GlobalConfig(**raw)
    # Store resolved base dir for path resolution
    object.__setattr__(cfg, "_base_dir", base)
    return cfg


def load_project_config(project_dir: Path) -> ProjectConfig:
    """Load and validate a project's project.yaml."""
    yaml_path = project_dir / "project.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"project.yaml not found at {yaml_path}")
    with yaml_path.open() as f:
        raw = yaml.safe_load(f) or {}
    return ProjectConfig(**raw)


def validate_global_config(cfg: GlobalConfig, base_dir: Path) -> list[str]:
    """Run extra cross-field validation. Returns list of error/warning strings."""
    issues: list[str] = []
    has_api_key = bool(
        (cfg.claude.api_key or "").strip()
        or os.environ.get(cfg.claude.api_key_env_var, "").strip()
    )
    has_local = cfg.claude.local_cli_enabled

    if "api_key" in cfg.claude.provider_priority and not has_api_key:
        if "local_cli" not in cfg.claude.provider_priority or not has_local:
            issues.append(
                "WARNING: api_key is in provider_priority but no API key found, "
                "and local_cli is not available. No Claude provider will resolve."
            )

    # Validate template paths exist
    for attr, label in [
        ("project_report_template", "project_report_template"),
        ("executive_dashboard_template", "executive_dashboard_template"),
    ]:
        tpl_path = base_dir / getattr(cfg.reports, attr)
        if not tpl_path.exists():
            issues.append(f"INFO: Template not found (will be needed for reports): {tpl_path}")

    return issues
