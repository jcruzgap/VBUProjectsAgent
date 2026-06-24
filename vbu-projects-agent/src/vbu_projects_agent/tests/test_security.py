"""Tests for secret redaction and pre-write scanner."""
import pytest

from ..security.redaction import redact, register_secret, RedactionFilter
from ..security.scanner import SecretScanner, SecretDetected
from ..security.patterns import REDACTION_PLACEHOLDER


class TestRedaction:
    def test_redacts_anthropic_key(self):
        text = "API key is sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX123456789012345678"
        result = redact(text)
        assert "sk-ant" not in result
        assert REDACTION_PLACEHOLDER in result

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9XXXXXXXXXXXXXXXXXXXXXXXXXX"
        result = redact(text)
        assert "Bearer eyJ" not in result

    def test_redacts_runtime_secret(self):
        register_secret("super-secret-runtime-value")
        result = redact("The PAT is super-secret-runtime-value and it must be hidden")
        assert "super-secret-runtime-value" not in result
        assert REDACTION_PLACEHOLDER in result

    def test_clean_text_unchanged(self):
        text = "Progress is 78% with 22 test cases remaining."
        assert redact(text) == text

    def test_empty_string(self):
        assert redact("") == ""

    def test_logging_filter(self):
        import logging
        filter_ = RedactionFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="API key sk-ant-api03-TESTTESTTESTTEST1234567890123456789",
            args=(), exc_info=None,
        )
        filter_.filter(record)
        assert "sk-ant" not in str(record.msg)


class TestScanner:
    def test_blocks_anthropic_key(self, tmp_dir):
        scanner = SecretScanner()
        path = tmp_dir / "output.md"
        content = "API key: sk-ant-api03-REALKEY1234567890ABCDEFGHIJKLMNOPQRSTUVW"
        with pytest.raises(SecretDetected):
            scanner.safe_write(path, content)
        assert not path.exists()

    def test_allows_clean_content(self, tmp_dir):
        scanner = SecretScanner()
        path = tmp_dir / "output.md"
        content = "Progress: 78% complete. No secrets here."
        scanner.safe_write(path, content)
        assert path.exists()
        assert path.read_text() == content

    def test_blocks_bearer_token(self, tmp_dir):
        scanner = SecretScanner()
        path = tmp_dir / "report.html"
        content = "<p>Token: Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890==</p>"
        with pytest.raises(SecretDetected):
            scanner.safe_write(path, content)

    def test_write_is_atomic(self, tmp_dir):
        """On failure, no partial file should be left."""
        scanner = SecretScanner()
        path = tmp_dir / "output.md"
        path.write_text("original")
        with pytest.raises(SecretDetected):
            scanner.safe_write(path, "Bearer XXXXXXXXXXXXXXXXXXXXXXXXXXX malicious")
        # Original file should be unchanged
        assert path.read_text() == "original"
