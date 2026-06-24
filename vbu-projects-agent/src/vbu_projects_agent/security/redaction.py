"""Central secret redaction — installed as a logging.Filter and applied to exception messages."""
import logging
import re
from typing import Sequence

from .patterns import SECRET_PATTERNS, REDACTION_PLACEHOLDER

_RUNTIME_SECRETS: list[str] = []


def register_secret(value: str) -> None:
    """Register a runtime secret (e.g. PAT value) for redaction everywhere."""
    if value and value not in _RUNTIME_SECRETS:
        _RUNTIME_SECRETS.append(value)


def redact(text: str) -> str:
    """Redact all known secret patterns and registered runtime secrets from text."""
    if not text:
        return text
    for secret in _RUNTIME_SECRETS:
        if secret in text:
            text = text.replace(secret, REDACTION_PLACEHOLDER)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(REDACTION_PLACEHOLDER, text)
    return text


class RedactionFilter(logging.Filter):
    """Logging filter that redacts secrets from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(redact(str(a)) for a in record.args)
        if record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def install_redaction_filter(logger: logging.Logger | None = None) -> None:
    """Install RedactionFilter on the root logger (or a specific logger)."""
    target = logger or logging.getLogger()
    filt = RedactionFilter()
    if not any(isinstance(f, RedactionFilter) for f in target.filters):
        target.addFilter(filt)
