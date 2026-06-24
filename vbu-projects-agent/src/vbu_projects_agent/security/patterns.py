"""Secret detection regexes for Anthropic keys, Azure DevOps PATs, and generic auth headers."""
import re

# Anthropic API key: sk-ant-api03-... or sk-ant-...
_ANTHROPIC_KEY = re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")

# Azure DevOps PAT: 52-char base32-ish token
_ADO_PAT = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{52}(?![A-Za-z0-9])")

# Authorization headers
_BEARER_TOKEN = re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]{20,}={0,2}", re.IGNORECASE)
_BASIC_AUTH = re.compile(r"Basic\s+[A-Za-z0-9+/]{20,}={0,2}", re.IGNORECASE)

# Generic high-entropy strings that look like secrets (≥32 hex chars)
_HEX_SECRET = re.compile(r"(?<![A-Fa-f0-9])[A-Fa-f0-9]{32,}(?![A-Fa-f0-9])")

SECRET_PATTERNS: list[re.Pattern] = [
    _ANTHROPIC_KEY,
    _ADO_PAT,
    _BEARER_TOKEN,
    _BASIC_AUTH,
]

# Used for conservative pre-write scanning (strict set only)
STRICT_PATTERNS: list[re.Pattern] = [
    _ANTHROPIC_KEY,
    _BEARER_TOKEN,
    _BASIC_AUTH,
]

REDACTION_PLACEHOLDER = "[REDACTED]"
