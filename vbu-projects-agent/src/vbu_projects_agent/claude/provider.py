"""ClaudeProvider protocol + factory that resolves the active provider."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class ClaudeResult:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@runtime_checkable
class ClaudeProvider(Protocol):
    @property
    def mode(self) -> Literal["api_key", "local_cli"]:
        ...

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: Optional[str] = None,
    ) -> ClaudeResult:
        ...


class ClaudeProviderUnavailable(Exception):
    """Raised when no Claude provider can be resolved."""

    def __init__(self, tried: list[str]) -> None:
        super().__init__(
            f"No Claude provider resolved. Tried: {tried}. "
            "Set ANTHROPIC_API_KEY env var, or enable local_cli in config and ensure "
            "the Claude CLI is installed and authenticated."
        )
        self.tried = tried


def resolve_provider(
    config,  # GlobalConfig — avoid circular import
    force_mode: Optional[Literal["api_key", "local_cli"]] = None,
) -> ClaudeProvider:
    """
    Resolve the active ClaudeProvider using provider_priority from config.
    Raises ClaudeProviderUnavailable if none resolve.
    """
    from .api_key_provider import ApiKeyProvider
    from .local_cli_provider import LocalCliProvider

    priority = [force_mode] if force_mode else config.claude.provider_priority
    tried: list[str] = []

    for p in priority:
        if p == "api_key":
            key = (config.claude.api_key or "").strip() or os.environ.get(
                config.claude.api_key_env_var, ""
            ).strip()
            if key and _well_formed_key(key):
                logger.info("Claude provider: api_key")
                return ApiKeyProvider(key=key, default_model=config.claude.model)
            tried.append("api_key (no valid key found)")

        elif p == "local_cli":
            if config.claude.local_cli_enabled and LocalCliProvider.is_available():
                logger.info("Claude provider: local_cli")
                return LocalCliProvider(default_model=config.claude.model)
            tried.append("local_cli (not available or disabled)")

    raise ClaudeProviderUnavailable(tried)


def _well_formed_key(key: str) -> bool:
    """Validate shape only — non-empty, expected prefix."""
    return bool(key) and (
        key.startswith("sk-ant-") or key.startswith("sk-")
    )
