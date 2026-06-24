"""Parse, update, and write context/*.md files with YAML front-matter and SHA-256 hashing."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from ..security.scanner import SecretScanner

_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

_CONTEXT_FILES = [
    "overview.md",
    "current_status.md",
    "milestones.md",
    "risks.md",
    "decisions.md",
    "dependencies.md",
    "financials.md",
    "team.md",
    "delivery_notes.md",
    "conflicts.md",
]

_scanner = SecretScanner()


@dataclass
class ContextFile:
    name: str
    path: Path
    front_matter: dict
    body: str

    @property
    def last_updated(self) -> Optional[str]:
        return self.front_matter.get("last_updated")

    @property
    def content_hash(self) -> Optional[str]:
        return self.front_matter.get("content_sha256")

    def render(self) -> str:
        """Render the file back to its on-disk string representation."""
        fm = yaml.dump(self.front_matter, default_flow_style=False, allow_unicode=True).strip()
        return f"---\n{fm}\n---\n{self.body}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_file(path: Path) -> ContextFile:
    """Read a context file and split front-matter from body."""
    if not path.exists():
        return ContextFile(
            name=path.name,
            path=path,
            front_matter={},
            body="",
        )
    content = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(content)
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = content[m.end():]
    else:
        fm = {}
        body = content
    return ContextFile(name=path.name, path=path, front_matter=fm, body=body)


class ContextManager:
    """Reads, updates, and writes context/*.md files for a project."""

    def __init__(self, context_dir: Path) -> None:
        self.dir = context_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> dict[str, ContextFile]:
        """Load all context files (creates empty ContextFile if missing)."""
        result: dict[str, ContextFile] = {}
        for name in _CONTEXT_FILES:
            path = self.dir / name
            result[name] = _parse_file(path)
        return result

    def load_file(self, name: str) -> ContextFile:
        path = self.dir / name
        return _parse_file(path)

    def write_file(self, ctx_file: ContextFile, source: str = "manual") -> None:
        """Write a ContextFile back to disk, updating front-matter timestamps and hash."""
        now = datetime.now(timezone.utc).isoformat()
        new_hash = _sha256(ctx_file.body)

        ctx_file.front_matter.update({
            "last_updated": now,
            "last_update_source": source,
            "content_sha256": new_hash,
        })
        content = ctx_file.render()
        _scanner.safe_write(ctx_file.path, content)

    def update_body(
        self,
        name: str,
        new_body: str,
        source: str = "agent",
    ) -> ContextFile:
        """Surgically update a context file's body, preserve front-matter, update hash."""
        ctx_file = self.load_file(name)
        ctx_file = ContextFile(
            name=ctx_file.name,
            path=ctx_file.path,
            front_matter=dict(ctx_file.front_matter),
            body=new_body,
        )
        self.write_file(ctx_file, source=source)
        return ctx_file

    def get_hashes(self) -> dict[str, str]:
        """Return {filename: sha256} for all existing context files."""
        hashes: dict[str, str] = {}
        for name in _CONTEXT_FILES:
            path = self.dir / name
            if path.exists():
                hashes[name] = _sha256(path.read_text(encoding="utf-8"))
        return hashes

    def verify_integrity(self) -> list[str]:
        """Return list of files whose content hash doesn't match front-matter hash."""
        issues: list[str] = []
        for name in _CONTEXT_FILES:
            path = self.dir / name
            if not path.exists():
                continue
            ctx = _parse_file(path)
            actual = _sha256(ctx.body)
            declared = ctx.front_matter.get("content_sha256")
            if declared and declared != actual:
                issues.append(
                    f"{name}: declared hash {declared[:12]}... != actual {actual[:12]}..."
                )
        return issues

    def scaffold_empty_files(self, project_name: str) -> None:
        """Create all context/*.md files with empty bodies and initial front-matter."""
        for name in _CONTEXT_FILES:
            path = self.dir / name
            if path.exists():
                continue
            title = name.replace(".md", "").replace("_", " ").title()
            body = f"# {title}\n\n_No content yet._\n"
            ctx = ContextFile(
                name=name,
                path=path,
                front_matter={},
                body=body,
            )
            self.write_file(ctx, source="scaffold")
