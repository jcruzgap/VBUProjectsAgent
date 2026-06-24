"""Tests for Slack Status Writer skill — validators, numeric guard, fallback."""
import pytest

from ..skills.slack_status import generate_slack_status, SlackStatusInputs, _deterministic_fallback
from ..skills.validators import (
    validate_slack_output, numeric_guard, word_count_check, section_check
)


@pytest.fixture()
def sample_inputs() -> SlackStatusInputs:
    return SlackStatusInputs(
        project_name="Project Alpha",
        health="yellow",
        health_reasons=["78% progress below 85% green threshold"],
        progress_summary="Alpha Ready is 78% complete, with 22 test cases remaining",
        milestone_name="Alpha Ready",
        target_or_forecast_date="July 12",
        top_risk_text="UAT environment readiness may impact validation velocity",
        ask_text="Need client confirmation on UAT data availability by Friday",
        max_words=180,
        tone="concise_executive",
    )


class TestDeterministicFallback:
    def test_always_produces_output(self, sample_inputs):
        msg = _deterministic_fallback(sample_inputs)
        assert "Project Alpha" in msg
        assert "Yellow" in msg or "yellow" in msg
        assert "[Generated without narrative model" in msg

    def test_contains_key_sections(self, sample_inputs):
        msg = _deterministic_fallback(sample_inputs)
        assert "Progress:" in msg
        assert "Next milestone:" in msg


class TestGenerateWithFakeProvider:
    def test_uses_provider_when_available(self, sample_inputs, fake_provider):
        # The fake provider returns structured JSON — not a slack message, so
        # validation will fail and fallback kicks in
        fake_provider.response = (
            "Project Alpha — Status: Yellow\n"
            "Progress: Alpha Ready is 78% complete, with 22 test cases remaining.\n"
            "Next milestone: Alpha Ready targeted for July 12.\n"
            "Key risk: UAT environment readiness may impact validation velocity.\n"
            "Ask: Need client confirmation on UAT data availability by Friday."
        )
        msg = generate_slack_status(sample_inputs, fake_provider)
        assert "Project Alpha" in msg

    def test_fallback_on_none_provider(self, sample_inputs):
        msg = generate_slack_status(sample_inputs, provider=None)
        assert "Project Alpha" in msg
        assert "[Generated without narrative model" in msg

    def test_numeric_guard_rejects_fabricated_numbers(self, sample_inputs, bad_number_provider):
        """Provider returns 99% which is not in the allowed context (78%); should fallback."""
        msg = generate_slack_status(sample_inputs, bad_number_provider, max_retries=0)
        # Should have fallen back to deterministic template
        assert "[Generated without narrative model" in msg or "78" in msg


class TestValidators:
    def test_word_count_passes(self):
        text = " ".join(["word"] * 100)
        assert word_count_check(text, 200) is None

    def test_word_count_fails(self):
        text = " ".join(["word"] * 300)
        assert word_count_check(text, 200) is not None

    def test_section_check_passes(self):
        text = "Project Alpha — Status: Yellow\nProgress: 78%"
        assert section_check(text, ["Status:"]) is None

    def test_section_check_fails(self):
        text = "Progress: 78%"
        result = section_check(text, ["Status:"])
        assert result is not None

    def test_numeric_guard_passes_matching_numbers(self):
        context = "78% complete with 22 remaining"
        output = "Progress is 78% with 22 test cases left."
        assert numeric_guard(output, context) is None

    def test_numeric_guard_fails_on_unknown_number(self):
        context = "78% complete"
        output = "Progress is 99% complete."
        result = numeric_guard(output, context)
        assert result is not None


class TestValidateSlackOutput:
    def test_valid_output_no_errors(self, sample_inputs):
        text = (
            "Project Alpha — Status: Yellow\n"
            "Progress: Alpha Ready is 78% complete, with 22 test cases remaining.\n"
            "Next milestone: Alpha Ready targeted for July 12.\n"
        )
        allowed = (
            "Project Alpha yellow 78% 22 July 12 Alpha Ready UAT environment"
        )
        errors = validate_slack_output(text, allowed, max_words=100)
        assert errors == []

    def test_word_cap_violation(self):
        text = " ".join(["word"] * 200)
        errors = validate_slack_output(text, text, max_words=50)
        assert any("word count" in e.lower() for e in errors)
