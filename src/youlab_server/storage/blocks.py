"""User-scoped block management with Letta sync."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

import structlog

from youlab_server.storage.convert import markdown_to_toml, toml_to_markdown
from youlab_server.storage.diffs import PendingDiff, PendingDiffStore

if TYPE_CHECKING:
    from letta_client import Letta

    from youlab_server.storage.git import GitUserStorage

log = structlog.get_logger()


class UserBlockManager:
    """
    Manages memory blocks for a single user.

    Responsibilities:
    - Read/write blocks from git storage
    - Convert between TOML and Markdown
    - Sync blocks to Letta agents
    - Manage pending diffs for agent edits
    """

    def __init__(
        self,
        user_id: str,
        storage: GitUserStorage,
        letta_client: Letta | None = None,
    ) -> None:
        self.user_id = user_id
        self.storage = storage
        self.letta = letta_client
        self.diffs = PendingDiffStore(storage.diffs_dir)
        self.logger = log.bind(user_id=user_id, component="user_block_manager")

    def _letta_block_name(self, label: str) -> str:
        """Generate Letta block name for user-scoped block."""
        return f"youlab_user_{self.user_id}_{label}"

    # =========================================================================
    # Block CRUD Operations
    # =========================================================================

    def list_blocks(self) -> list[str]:
        """List all block labels for this user."""
        return self.storage.list_blocks()

    def get_block_toml(self, label: str) -> str | None:
        """Get block content as TOML."""
        return self.storage.read_block(label)

    def get_block_markdown(self, label: str) -> str | None:
        """Get block content as Markdown for editing."""
        toml_content = self.storage.read_block(label)
        if toml_content is None:
            return None
        return toml_to_markdown(toml_content, label)

    def update_block_from_markdown(
        self,
        label: str,
        markdown: str,
        message: str | None = None,
        sync_to_letta: bool = True,
    ) -> str:
        """
        Update block from Markdown content (user edit).

        Args:
            label: Block label
            markdown: Markdown content
            message: Commit message
            sync_to_letta: Whether to sync to Letta immediately

        Returns:
            Commit SHA

        """
        toml_content, _ = markdown_to_toml(markdown)
        commit_sha = self.storage.write_block(
            label=label,
            content=toml_content,
            message=message or f"Update {label}",
            author="user",
        )

        if sync_to_letta and self.letta:
            self._sync_block_to_letta(label, toml_content)

        return commit_sha

    def update_block_from_toml(
        self,
        label: str,
        toml_content: str,
        message: str | None = None,
        author: str = "user",
        sync_to_letta: bool = True,
    ) -> str:
        """Update block from TOML content."""
        commit_sha = self.storage.write_block(
            label=label,
            content=toml_content,
            message=message or f"Update {label}",
            author=author,
        )

        if sync_to_letta and self.letta:
            self._sync_block_to_letta(label, toml_content)

        return commit_sha

    # =========================================================================
    # Version History
    # =========================================================================

    def get_history(self, label: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get version history for a block."""
        versions = self.storage.get_block_history(label, limit)
        return [
            {
                "sha": v.commit_sha,
                "message": v.message,
                "author": v.author,
                "timestamp": v.timestamp.isoformat(),
                "is_current": v.is_current,
            }
            for v in versions
        ]

    def get_version(self, label: str, commit_sha: str) -> str | None:
        """Get block content at a specific version."""
        return self.storage.get_block_at_version(label, commit_sha)

    def restore_version(
        self,
        label: str,
        commit_sha: str,
        sync_to_letta: bool = True,
    ) -> str:
        """Restore block to a previous version."""
        new_sha = self.storage.restore_block(label, commit_sha)

        if sync_to_letta and self.letta:
            content = self.storage.read_block(label)
            if content:
                self._sync_block_to_letta(label, content)

        return new_sha

    # =========================================================================
    # Letta Sync
    # =========================================================================

    def _sync_block_to_letta(self, label: str, toml_content: str) -> None:
        """Sync block content to Letta."""
        if not self.letta:
            return

        block_name = self._letta_block_name(label)

        # Parse TOML and convert to Letta memory string format
        try:
            data = tomllib.loads(toml_content)
            memory_str = self._toml_to_memory_string(data)
        except Exception as e:
            self.logger.warning(
                "toml_parse_failed",
                label=label,
                error=str(e),
            )
            memory_str = toml_content

        # Find or create block in Letta
        try:
            blocks = self.letta.blocks.list()
            existing = next(
                (b for b in blocks if getattr(b, "name", None) == block_name),
                None,
            )

            if existing:
                # Update existing block
                self.letta.blocks.update(
                    block_id=existing.id,
                    value=memory_str,
                )
                self.logger.debug("letta_block_updated", label=label)
            else:
                # Create new block
                self.letta.blocks.create(
                    label=label,
                    name=block_name,
                    value=memory_str,
                )
                self.logger.info("letta_block_created", label=label)

        except Exception as e:
            self.logger.error(
                "letta_sync_failed",
                label=label,
                error=str(e),
            )

    def _toml_to_memory_string(self, data: dict[str, Any]) -> str:
        """Convert TOML data to Letta memory string format."""
        lines = []
        for key, value in data.items():
            if isinstance(value, list):
                items = "\n".join(f"- {item}" for item in value)
                lines.append(f"{key}:\n{items}")
            elif value:
                lines.append(f"{key}: {value}")
        return "\n\n".join(lines)

    def get_or_create_letta_block_id(self, label: str) -> str | None:
        """Get or create a Letta block for this user/label."""
        if not self.letta:
            return None

        block_name = self._letta_block_name(label)

        # Check if exists
        blocks = self.letta.blocks.list()
        existing = next(
            (b for b in blocks if getattr(b, "name", None) == block_name),
            None,
        )

        if existing:
            return existing.id

        # Create from current content
        content = self.storage.read_block(label)
        if content is None:
            return None

        try:
            data = tomllib.loads(content)
            memory_str = self._toml_to_memory_string(data)
        except Exception:
            memory_str = content

        block = self.letta.blocks.create(
            label=label,
            name=block_name,
            value=memory_str,
        )
        return block.id

    # =========================================================================
    # Pending Diffs (Agent Edits)
    # =========================================================================

    def propose_edit(
        self,
        agent_id: str,
        block_label: str,
        field: str | None,
        operation: str,
        proposed_value: str,
        reasoning: str,
        confidence: str = "medium",
        source_query: str | None = None,
    ) -> PendingDiff:
        """
        Create a pending diff for an agent-proposed edit.

        This does NOT apply the edit - it creates a diff for user approval.
        """
        current = self.storage.read_block(block_label) or ""

        diff = PendingDiff.create(
            user_id=self.user_id,
            agent_id=agent_id,
            block_label=block_label,
            field=field,
            operation=operation,
            current_value=current,
            proposed_value=proposed_value,
            reasoning=reasoning,
            confidence=confidence,
            source_query=source_query,
        )

        self.diffs.save(diff)
        self.logger.info(
            "diff_proposed",
            diff_id=diff.id,
            block=block_label,
            agent=agent_id,
        )

        return diff

    def approve_diff(self, diff_id: str) -> str:
        """
        Approve and apply a pending diff.

        Returns commit SHA.
        """
        diff = self.diffs.get(diff_id)
        if diff is None:
            msg = f"Diff {diff_id} not found"
            raise ValueError(msg)
        if diff.status != "pending":
            msg = f"Diff {diff_id} is not pending (status: {diff.status})"
            raise ValueError(msg)

        # Apply the edit
        # For now, simple replace. TODO: handle append/llm_diff
        commit_sha = self.update_block_from_toml(
            label=diff.block_label,
            toml_content=diff.proposed_value,
            message=f"Apply agent suggestion: {diff.reasoning[:50]}",
            author=f"agent:{diff.agent_id}",
            sync_to_letta=True,
        )

        # Update diff status
        self.diffs.update_status(diff_id, "approved", commit_sha)

        # Supersede older diffs for same block
        superseded = self.diffs.supersede_older(diff.block_label, diff_id)

        self.logger.info(
            "diff_approved",
            diff_id=diff_id,
            commit=commit_sha[:8],
            superseded=superseded,
        )

        return commit_sha

    def reject_diff(self, diff_id: str, reason: str | None = None) -> None:
        """Reject a pending diff."""
        self.diffs.update_status(diff_id, "rejected")
        self.logger.info("diff_rejected", diff_id=diff_id, reason=reason)

    def list_pending_diffs(self, block_label: str | None = None) -> list[dict[str, Any]]:
        """List pending diffs as dicts."""
        diffs = self.diffs.list_pending(block_label)
        return [
            {
                "id": d.id,
                "block": d.block_label,
                "field": d.field,
                "operation": d.operation,
                "reasoning": d.reasoning,
                "confidence": d.confidence,
                "created_at": d.created_at,
                "agent_id": d.agent_id,
            }
            for d in diffs
        ]

    def count_pending_diffs(self) -> dict[str, int]:
        """Count pending diffs per block."""
        return self.diffs.count_pending()
