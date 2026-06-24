"""Local Claude CLI / SDK provider — uses user's existing credentials via subprocess."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Literal, Optional

from .provider import ClaudeResult

logger = logging.getLogger(__name__)

_CLI_CANDIDATES = ["claude"]


class LocalCliProvider:
    """Shells out to the local Claude CLI using the user's existing credentials."""

    mode: Literal["local_cli"] = "local_cli"

    def __init__(self, default_model: str = "claude-sonnet-4-6") -> None:
        self.default_model = default_model
        self._cli_path = self._find_cli()

    @staticmethod
    def _find_cli() -> Optional[str]:
        for name in _CLI_CANDIDATES:
            path = shutil.which(name)
            if path:
                return path
        return None

    @classmethod
    def is_available(cls) -> bool:
        """Check if the Claude CLI is on PATH and responds to --version."""
        cli = cls._find_cli()
        if not cli:
            return False
        try:
            result = subprocess.run(
                [cli, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: Optional[str] = None,
    ) -> ClaudeResult:
        if not self._cli_path:
            raise RuntimeError("Claude CLI not found on PATH.")

        effective_model = model or self.default_model
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        cmd = [
            self._cli_path,
            "--model", effective_model,
            "--max-tokens", str(max_tokens),
            "--print",
            full_prompt,
        ]

        logger.debug("LocalCliProvider.complete model=%s", effective_model)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Claude CLI timed out after 120s") from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI returned non-zero ({result.returncode}): {result.stderr[:500]}"
            )

        return ClaudeResult(
            content=result.stdout.strip(),
            model=effective_model,
        )
