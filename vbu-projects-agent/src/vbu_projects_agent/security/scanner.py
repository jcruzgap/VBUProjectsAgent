"""Pre-write secret scanner — blocks any file write that contains a secret-shaped string."""
from pathlib import Path
from .patterns import STRICT_PATTERNS, REDACTION_PLACEHOLDER
from .redaction import _RUNTIME_SECRETS


class SecretDetected(Exception):
    """Raised when a secret pattern is found in content about to be written."""


def scan_text(text: str, label: str = "content") -> None:
    """Raise SecretDetected if any secret pattern is found in text."""
    for secret in _RUNTIME_SECRETS:
        if secret and secret in text:
            raise SecretDetected(
                f"Secret detected in {label}: registered runtime secret found. "
                "Aborting write to prevent leakage."
            )
    for pattern in STRICT_PATTERNS:
        match = pattern.search(text)
        if match:
            raise SecretDetected(
                f"Secret detected in {label}: pattern '{pattern.pattern[:30]}...' matched. "
                "Aborting write."
            )


def scan_file_content(content: str, path: str | Path) -> None:
    """Scan content before writing it to path. Raises SecretDetected on hit."""
    scan_text(content, label=str(path))


class SecretScanner:
    """Callable wrapper for scanning strings or files."""

    def scan(self, text: str, label: str = "content") -> None:
        scan_text(text, label)

    def scan_file(self, content: str, path: str | Path) -> None:
        scan_file_content(content, path)

    def safe_write(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Scan then write atomically; raises SecretDetected before touching disk."""
        scan_file_content(content, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding=encoding)
        tmp.replace(path)
