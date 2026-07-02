"""Load secrets from a .env file into the environment at startup.

Existing environment variables always win over .env values, so a value
exported in the shell is never clobbered by the file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv


def load_env_file(base_dir: Optional[Path] = None) -> Optional[Path]:
    """Load `.env` into os.environ (without overriding existing vars).

    If `base_dir` is given and `base_dir/.env` exists, that file is used.
    Otherwise the nearest `.env` walking up from the current directory is used.
    Returns the path loaded, or None if no `.env` was found.
    """
    if base_dir is not None:
        candidate = Path(base_dir) / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return candidate

    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
        return Path(found)
    return None
