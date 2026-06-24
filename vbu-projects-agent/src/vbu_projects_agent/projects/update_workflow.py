"""§8 Project Update Workflow — full pipeline from input/ to context/ + snapshot."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..config.models import ProjectConfig, GlobalConfig
    from ..claude.provider import ClaudeProvider

from .context_manager import ContextManager
from .conflicts import ConflictManager, Conflict
from ..storage.snapshots import SnapshotManager
from ..storage.repositories import SnapshotRepository, MetricsRepository, ArtifactRepository
from ..storage.db import Database

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    run_id: str
    mode: str                           # "default" | "dry-run" | "review-required"
    dry_run: bool
    input_files: list[str]
    changes_applied: list[str]          # human-readable list of changes
    conflicts_detected: list[Conflict]
    snapshot_path: Optional[Path]
    change_summary: str
    skipped: bool = False
    skipped_reason: str = ""


class UpdateWorkflow:
    """
    Orchestrates the §8 update workflow:
    1. Validate + inventory input
    2. Summarize + extract (Claude)
    3. Load context
    4. Reconcile (Claude)
    5. Detect conflicts
    6. Snapshot (always before write)
    7. Apply / dry-run / review-gate
    8. Persist history
    9. Archive input
    10. Emit change summary
    """

    def __init__(
        self,
        project_dir: Path,
        project_config: "ProjectConfig",
        global_config: "GlobalConfig",
        db: Database,
        claude_provider: "ClaudeProvider",
        snapshot_manager: SnapshotManager,
    ) -> None:
        self.project_dir = project_dir
        self.pcfg = project_config
        self.gcfg = global_config
        self.db = db
        self.claude = claude_provider
        self.snap_mgr = snapshot_manager

        self.project_id = project_config.project.id
        self.input_dir = project_dir / global_config.projects.input_folder_name
        self.archive_dir = project_dir / global_config.projects.archive_folder_name
        self.context_dir = project_dir / "context"
        self.generated_dir = project_dir / "generated"

    def run(
        self,
        dry_run: bool = False,
        review_required: bool = False,
    ) -> UpdateResult:
        mode = "dry-run" if dry_run else ("review-required" if review_required else "default")
        logger.info("Starting update workflow for %s (mode=%s)", self.project_id, mode)

        # 1. Inventory input
        input_files = self._list_input_files()
        if not input_files:
            return UpdateResult(
                run_id="no-input",
                mode=mode,
                dry_run=dry_run,
                input_files=[],
                changes_applied=[],
                conflicts_detected=[],
                snapshot_path=None,
                change_summary="No input files found. Nothing to do.",
                skipped=True,
                skipped_reason="No files in input/ directory.",
            )

        source_file_names = [f.name for f in input_files]
        run_id = self.snap_mgr.make_run_id(source_file_names)
        logger.info("Run ID: %s, input files: %s", run_id, source_file_names)

        # 2. Read + classify input files
        input_contents = self._read_inputs(input_files)

        # 3. Extract facts via Claude
        extracted = self._extract_facts(input_contents, source_file_names)

        # 4. Load current context
        ctx_mgr = ContextManager(self.context_dir)
        context = ctx_mgr.load_all()

        # 5. Reconcile
        change_set = self._reconcile(extracted, context, source_file_names)

        # 6. Detect conflicts
        conflict_mgr = ConflictManager(ctx_mgr)
        conflicts = self._detect_conflicts(change_set, context, conflict_mgr, source_file_names)

        # 7. Snapshot (always, before any write)
        snap_path = self.snap_mgr.create_snapshot(
            project_id=self.project_id,
            context_dir=self.context_dir,
            run_id=run_id,
            mode=mode,
            source_files=source_file_names,
        )

        if dry_run:
            # Render proposed changes; write nothing to context/
            summary = self._build_change_summary(change_set, conflicts, run_id, dry_run=True)
            self._write_preview(summary, run_id)
            return UpdateResult(
                run_id=run_id,
                mode=mode,
                dry_run=True,
                input_files=source_file_names,
                changes_applied=[],
                conflicts_detected=conflicts,
                snapshot_path=snap_path,
                change_summary=summary,
            )

        if review_required:
            summary = self._build_change_summary(change_set, conflicts, run_id, dry_run=False)
            self._write_preview(summary, run_id)
            approved = self._prompt_for_approval(summary)
            if not approved:
                return UpdateResult(
                    run_id=run_id,
                    mode=mode,
                    dry_run=False,
                    input_files=source_file_names,
                    changes_applied=[],
                    conflicts_detected=conflicts,
                    snapshot_path=snap_path,
                    change_summary="Changes rejected by user during review.",
                    skipped=True,
                    skipped_reason="User rejected changes during --review-required gate.",
                )

        # 8. Apply changes
        applied = self._apply_changes(change_set, ctx_mgr, source_file_names)

        # Record conflicts in conflicts.md
        for c in conflicts:
            pass  # already written in _detect_conflicts

        # 9. Persist snapshot row
        snap_repo = SnapshotRepository(self.db)
        snap_repo.insert(
            run_id=run_id,
            project_id=self.project_id,
            mode=mode,
            claude_provider=self.claude.mode if self.claude else None,
            source_files=source_file_names,
            snapshot_path=str(snap_path),
            context_hashes=ctx_mgr.get_hashes(),
            change_summary=None,
        )

        # 10. Archive input
        self._archive_inputs(input_files, run_id)

        # 11. Change summary
        summary = self._build_change_summary(applied, conflicts, run_id, dry_run=False)
        snap_repo_update = SnapshotRepository(self.db)
        # Update change_summary in row
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE project_snapshots SET change_summary=? WHERE run_id=?",
                (summary, run_id),
            )

        self._write_change_summary(summary, run_id)
        logger.info("Update complete. run_id=%s, changes=%d", run_id, len(applied))

        return UpdateResult(
            run_id=run_id,
            mode=mode,
            dry_run=False,
            input_files=source_file_names,
            changes_applied=applied,
            conflicts_detected=conflicts,
            snapshot_path=snap_path,
            change_summary=summary,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _list_input_files(self) -> list[Path]:
        self.input_dir.mkdir(parents=True, exist_ok=True)
        return sorted(
            f for f in self.input_dir.iterdir()
            if f.is_file() and f.suffix in (".md", ".txt", ".csv", ".json")
        )

    def _read_inputs(self, files: list[Path]) -> dict[str, str]:
        contents: dict[str, str] = {}
        for f in files:
            try:
                contents[f.name] = f.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not read %s: %s", f.name, e)
        return contents

    def _extract_facts(
        self, input_contents: dict[str, str], source_files: list[str]
    ) -> dict:
        """Use Claude to extract structured facts from input files."""
        if not self.claude:
            return {"raw_inputs": input_contents, "facts": []}

        combined = "\n\n---\n\n".join(
            f"[FILE: {name}]\n{content}"
            for name, content in input_contents.items()
        )

        system = (
            "You are a delivery-context extraction assistant. "
            "Extract structured facts from the provided input files. "
            "Return a JSON object with keys: "
            "'status_updates' (list of strings), "
            "'new_risks' (list of {id, description, severity, owner}), "
            "'closed_risks' (list of risk IDs), "
            "'decisions' (list of {id, date, decision, rationale}), "
            "'milestone_updates' (list of {id, name, update}), "
            "'blockers' (list of strings), "
            "'asks' (list of strings). "
            "Be conservative — only extract clearly stated facts."
        )

        prompt = f"Input files:\n\n{combined}\n\nExtract the structured facts as JSON."

        try:
            result = self.claude.complete(
                system=system,
                prompt=prompt,
                max_tokens=2000,
                temperature=0.1,
                model=self.gcfg.claude.task_models.classify_input,
            )
            import json
            # Try to parse JSON from response
            text = result.content.strip()
            # Find JSON block
            import re
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.warning("Claude extraction failed: %s — using raw inputs", e)

        return {"raw_inputs": input_contents, "facts": []}

    def _reconcile(
        self, extracted: dict, context: dict, source_files: list[str]
    ) -> list[dict]:
        """Reconcile extracted facts against current context. Returns change set."""
        if not self.claude:
            return self._simple_reconcile(extracted)

        import json
        context_summary = {
            name: f.body[:500] for name, f in context.items() if f.body.strip()
        }

        system = (
            "You are a delivery context reconciliation assistant. "
            "Given extracted facts from new input and the current context, "
            "determine what should change. "
            "Return a JSON array of change objects, each with: "
            "{ 'file': str, 'action': 'append|replace_section|no_change', "
            "'section': str, 'new_content': str, 'reason': str }. "
            "Be surgical — only change what the new input actually updates. "
            "Never invent or embellish content."
        )

        prompt = (
            f"Extracted facts:\n{json.dumps(extracted, indent=2)}\n\n"
            f"Current context (excerpts):\n{json.dumps(context_summary, indent=2)}\n\n"
            "Produce the change set as JSON."
        )

        try:
            result = self.claude.complete(
                system=system,
                prompt=prompt,
                max_tokens=3000,
                temperature=0.1,
                model=self.gcfg.claude.task_models.reconcile_context,
            )
            text = result.content.strip()
            import re
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.warning("Claude reconciliation failed: %s", e)

        return self._simple_reconcile(extracted)

    def _simple_reconcile(self, extracted: dict) -> list[dict]:
        """Deterministic fallback: append raw input summary to delivery_notes.md."""
        raw = extracted.get("raw_inputs", {})
        if not raw:
            return []
        summary = "\n\n".join(
            f"### {name}\n{content[:1000]}" for name, content in raw.items()
        )
        return [{
            "file": "delivery_notes.md",
            "action": "append",
            "section": "Daily Notes",
            "new_content": f"\n## Update\n{summary}\n",
            "reason": "Appended raw input (Claude unavailable).",
        }]

    def _detect_conflicts(
        self,
        change_set: list[dict],
        context: dict,
        conflict_mgr: ConflictManager,
        source_files: list[str],
    ) -> list[Conflict]:
        """Detect contradictions between change_set and existing context."""
        conflicts: list[Conflict] = []
        import re
        for change in change_set:
            field = change.get("section", change.get("file", "unknown"))
            new_val = change.get("new_content", "")
            # Simple date conflict detection
            existing_dates = re.findall(r"\d{4}-\d{2}-\d{2}", context.get(change.get("file", ""), ContextFilePlaceholder()).body if hasattr(context.get(change.get("file", ""), None), 'body') else "")
            new_dates = re.findall(r"\d{4}-\d{2}-\d{2}", new_val)
            for nd in new_dates:
                for ed in existing_dates:
                    if nd != ed and "target" in field.lower():
                        c = conflict_mgr.record_conflict(
                            field=field,
                            existing_value=ed,
                            existing_source=change.get("file", "context"),
                            incoming_value=nd,
                            incoming_source=", ".join(source_files),
                            note="Date discrepancy detected — verify with team.",
                        )
                        conflicts.append(c)
        return conflicts

    def _apply_changes(
        self,
        change_set: list[dict],
        ctx_mgr: ContextManager,
        source_files: list[str],
    ) -> list[str]:
        """Apply the change set to context files. Returns human-readable change list."""
        applied: list[str] = []
        source_str = ", ".join(source_files)

        for change in change_set:
            target_file = change.get("file", "delivery_notes.md")
            action = change.get("action", "append")
            new_content = change.get("new_content", "")
            reason = change.get("reason", "")

            if action == "no_change":
                continue

            try:
                ctx = ctx_mgr.load_file(target_file)
                if action == "append":
                    new_body = ctx.body + new_content
                elif action == "replace_section":
                    new_body = new_content
                else:
                    new_body = ctx.body + new_content

                ctx_mgr.update_body(target_file, new_body, source=source_str)
                applied.append(f"{target_file}: {action} — {reason}")
                logger.debug("Applied change to %s (%s)", target_file, action)
            except Exception as e:
                logger.error("Failed to apply change to %s: %s", target_file, e)

        return applied

    def _archive_inputs(self, files: list[Path], run_id: str) -> None:
        archive = self.archive_dir / run_id
        archive.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.move(str(f), str(archive / f.name))
        logger.info("Archived %d input files to %s", len(files), archive)

    def _build_change_summary(
        self,
        changes: list,
        conflicts: list[Conflict],
        run_id: str,
        dry_run: bool,
    ) -> str:
        mode_label = "[DRY RUN — no changes written]" if dry_run else "[Changes applied]"
        lines = [
            f"# Update Change Summary",
            f"run_id: {run_id}",
            f"mode: {mode_label}",
            "",
            f"## Changes ({len(changes)})",
        ]
        for c in changes:
            if isinstance(c, dict):
                lines.append(f"- {c.get('file', '?')}: {c.get('action', '?')} — {c.get('reason', '')}")
            else:
                lines.append(f"- {c}")

        if conflicts:
            lines += ["", f"## Conflicts Detected ({len(conflicts)}) — DM Review Required"]
            for c in conflicts:
                lines.append(
                    f"- {c.id}: field={c.field}, "
                    f"existing={c.existing_value!r} vs incoming={c.incoming_value!r}"
                )
        else:
            lines += ["", "## Conflicts: None"]

        return "\n".join(lines)

    def _write_preview(self, summary: str, run_id: str) -> None:
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        preview = self.generated_dir / "update_preview.md"
        from ..security.scanner import SecretScanner
        SecretScanner().safe_write(preview, summary)

    def _write_change_summary(self, summary: str, run_id: str) -> None:
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        out = self.generated_dir / f"change_summary_{run_id}.md"
        from ..security.scanner import SecretScanner
        SecretScanner().safe_write(out, summary)

    def _prompt_for_approval(self, summary: str) -> bool:
        from rich.console import Console
        from rich.prompt import Confirm
        console = Console()
        console.print("\n[bold yellow]Proposed changes:[/bold yellow]")
        console.print(summary)
        return Confirm.ask("\nApply these changes?", default=False)


class ContextFilePlaceholder:
    body = ""
