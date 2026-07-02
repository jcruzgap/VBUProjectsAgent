#!/usr/bin/env bash
# One-command setup for VBU-Projects-Agent (macOS / Linux).
# Safe to re-run.
set -euo pipefail
# Ensure rich/console output (✓, →) encodes regardless of the terminal locale.
export PYTHONIOENCODING=utf-8
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$SCRIPT_DIR/vbu-projects-agent"

echo "==> Checking Python..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required but was not found. Install it and re-run." >&2
  exit 1
fi

cd "$PKG"

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi

echo "==> Installing the vbu-agent package..."
./.venv/bin/python -m pip install --upgrade pip >/dev/null
./.venv/bin/python -m pip install -e .

if [ ! -f ".env" ]; then
  echo "==> Creating .env from .env.example..."
  cp .env.example .env
fi

echo "==> Running diagnostics..."
./.venv/bin/vbu-agent doctor || true

cat <<'EOF'

Setup complete. Next steps:
  1. cd vbu-projects-agent
  2. Activate the venv:  source .venv/bin/activate
  3. Edit .env and set ANTHROPIC_API_KEY
  4. Add your project:  vbu-agent project new --project my-project --name "My Project"
EOF
