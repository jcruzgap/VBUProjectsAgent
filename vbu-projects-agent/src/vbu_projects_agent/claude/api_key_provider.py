"""Anthropic Python SDK–based Claude provider."""
from __future__ import annotations

import logging
from typing import Literal, Optional

from .provider import ClaudeResult

logger = logging.getLogger(__name__)


class ApiKeyProvider:
    """Uses the anthropic Python SDK with an API key."""

    mode: Literal["api_key"] = "api_key"

    def __init__(self, key: str, default_model: str = "claude-sonnet-4-6") -> None:
        self._key = key
        self.default_model = default_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._key)
        return self._client

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        model: Optional[str] = None,
    ) -> ClaudeResult:
        client = self._get_client()
        effective_model = model or self.default_model
        logger.debug("ApiKeyProvider.complete model=%s max_tokens=%d", effective_model, max_tokens)

        message = client.messages.create(
            model=effective_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        content = ""
        for block in message.content:
            if hasattr(block, "text"):
                content += block.text

        return ClaudeResult(
            content=content,
            model=effective_model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
