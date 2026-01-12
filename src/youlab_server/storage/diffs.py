"""Pending diff storage for agent-proposed changes."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

import structlog

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger()


@dataclass
class PendingDiff:
    """A proposed change from an agent awaiting user approval."""

    id: str
    user_id: str
    agent_id: str
    block_label: str
    field: str | None
    operation: Literal["append", "replace", "llm_diff"]
    current_value: str
    proposed_value: str
    reasoning: str
    confidence: Literal["low", "medium", "high"]
    source_query: str | None
    status: Literal["pending", "approved", "rejected", "superseded", "expired"]
    created_at: str
    reviewed_at: str | None = None
    applied_commit: str | None = None

    @classmethod
    def create(
        cls,
        user_id: str,
        agent_id: str,
        block_label: str,
        field: str | None,
        operation: str,
        current_value: str,
        proposed_value: str,
        reasoning: str,
        confidence: str = "medium",
        source_query: str | None = None,
    ) -> PendingDiff:
        """Create a new pending diff."""
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            agent_id=agent_id,
            block_label=block_label,
            field=field,
            operation=operation,  # type: ignore[arg-type]
            current_value=current_value,
            proposed_value=proposed_value,
            reasoning=reasoning,
            confidence=confidence,  # type: ignore[arg-type]
            source_query=source_query,
            status="pending",
            created_at=datetime.now().isoformat(),
        )


class PendingDiffStore:
    """
    JSON file storage for pending diffs.

    Storage: {user_storage}/pending_diffs/{diff_id}.json
    """

    def __init__(self, diffs_dir: Path) -> None:
        self.diffs_dir = diffs_dir
        self.diffs_dir.mkdir(parents=True, exist_ok=True)

    def _diff_path(self, diff_id: str) -> Path:
        return self.diffs_dir / f"{diff_id}.json"

    def save(self, diff: PendingDiff) -> None:
        """Save a diff to storage."""
        path = self._diff_path(diff.id)
        path.write_text(json.dumps(asdict(diff), indent=2))

    def get(self, diff_id: str) -> PendingDiff | None:
        """Get a diff by ID."""
        path = self._diff_path(diff_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return PendingDiff(**data)

    def list_pending(self, block_label: str | None = None) -> list[PendingDiff]:
        """List all pending diffs, optionally filtered by block."""
        diffs = []
        for path in self.diffs_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                diff = PendingDiff(**data)
                if diff.status == "pending" and (
                    block_label is None or diff.block_label == block_label
                ):
                    diffs.append(diff)
            except Exception:
                log.debug("diff_parse_failed", path=str(path))
                continue
        return sorted(diffs, key=lambda d: d.created_at, reverse=True)

    def count_pending(self) -> dict[str, int]:
        """Count pending diffs per block."""
        counts: dict[str, int] = {}
        for diff in self.list_pending():
            counts[diff.block_label] = counts.get(diff.block_label, 0) + 1
        return counts

    def update_status(
        self,
        diff_id: str,
        status: str,
        applied_commit: str | None = None,
    ) -> None:
        """Update diff status."""
        diff = self.get(diff_id)
        if diff:
            diff.status = status  # type: ignore[assignment]
            diff.reviewed_at = datetime.now().isoformat()
            if applied_commit:
                diff.applied_commit = applied_commit
            self.save(diff)

    def supersede_older(self, block_label: str, keep_id: str) -> int:
        """Mark older pending diffs for a block as superseded."""
        count = 0
        for diff in self.list_pending(block_label):
            if diff.id != keep_id:
                self.update_status(diff.id, "superseded")
                count += 1
        return count
