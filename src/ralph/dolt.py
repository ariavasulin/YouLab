"""Dolt database client for memory block storage."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from ralph.config import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class MemoryBlock:
    """A memory block record."""

    user_id: str
    label: str
    title: str | None
    body: str | None
    schema_ref: str | None
    updated_at: datetime


@dataclass
class VersionInfo:
    """Version history entry."""

    commit_hash: str
    message: str
    author: str
    timestamp: datetime
    is_current: bool = False


@dataclass
class PendingProposal:
    """A pending agent proposal (represented as a branch)."""

    branch_name: str
    user_id: str
    block_label: str
    agent_id: str
    reasoning: str
    confidence: str
    created_at: datetime


class DoltClient:
    """Async client for Dolt database operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Initialize connection pool."""
        self._engine = create_async_engine(
            self._settings.dolt_url,
            pool_size=20,
            max_overflow=10,
            pool_recycle=1800,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("DoltClient not connected. Call connect() first.")
        async with self._session_factory() as sess:
            yield sess

    # -------------------------------------------------------------------------
    # Memory Block Operations (on main branch)
    # -------------------------------------------------------------------------

    async def list_blocks(self, user_id: str) -> list[MemoryBlock]:
        """List all memory blocks for a user."""
        async with self.session() as session:
            result = await session.execute(
                text(
                    "SELECT user_id, label, title, body, schema_ref, updated_at "
                    "FROM memory_blocks WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
            return [
                MemoryBlock(
                    user_id=row.user_id,
                    label=row.label,
                    title=row.title,
                    body=row.body,
                    schema_ref=row.schema_ref,
                    updated_at=row.updated_at,
                )
                for row in result.fetchall()
            ]

    async def get_block(self, user_id: str, label: str) -> MemoryBlock | None:
        """Get a specific memory block."""
        async with self.session() as session:
            result = await session.execute(
                text(
                    "SELECT user_id, label, title, body, schema_ref, updated_at "
                    "FROM memory_blocks WHERE user_id = :user_id AND label = :label"
                ),
                {"user_id": user_id, "label": label},
            )
            row = result.fetchone()
            if not row:
                return None
            return MemoryBlock(
                user_id=row.user_id,
                label=row.label,
                title=row.title,
                body=row.body,
                schema_ref=row.schema_ref,
                updated_at=row.updated_at,
            )

    async def update_block(
        self,
        user_id: str,
        label: str,
        body: str,
        title: str | None = None,
        schema_ref: str | None = None,
        author: str = "user",
        message: str | None = None,
    ) -> str:
        """Update a memory block and commit. Returns commit hash."""
        async with self.session() as session:
            # Upsert the block
            await session.execute(
                text("""
                    INSERT INTO memory_blocks (user_id, label, title, body, schema_ref)
                    VALUES (:user_id, :label, :title, :body, :schema_ref)
                    ON DUPLICATE KEY UPDATE
                        title = COALESCE(:title, title),
                        body = :body,
                        schema_ref = COALESCE(:schema_ref, schema_ref)
                """),
                {
                    "user_id": user_id,
                    "label": label,
                    "title": title,
                    "body": body,
                    "schema_ref": schema_ref,
                },
            )
            await session.commit()

            # Dolt commit with author attribution
            commit_msg = message or f"Update {label}"
            author_str = f"{author} <{author}@youlab>"

            await session.execute(text("CALL DOLT_ADD('-A')"))
            result = await session.execute(
                text("CALL DOLT_COMMIT('--skip-empty', '--author', :author, '-m', :message)"),
                {"author": author_str, "message": commit_msg},
            )
            row = result.fetchone()
            return row[0] if row else ""

    async def delete_block(self, user_id: str, label: str, author: str = "user") -> str | None:
        """Delete a memory block. Returns commit hash or None if not found."""
        async with self.session() as session:
            result = await session.execute(
                text("DELETE FROM memory_blocks WHERE user_id = :user_id AND label = :label"),
                {"user_id": user_id, "label": label},
            )
            if result.rowcount == 0:
                return None

            await session.commit()

            await session.execute(text("CALL DOLT_ADD('-A')"))
            result = await session.execute(
                text("CALL DOLT_COMMIT('--skip-empty', '--author', :author, '-m', :message)"),
                {"author": f"{author} <{author}@youlab>", "message": f"Delete {label}"},
            )
            row = result.fetchone()
            return row[0] if row else None

    # -------------------------------------------------------------------------
    # Version History Operations
    # -------------------------------------------------------------------------

    async def get_block_history(
        self,
        user_id: str,
        label: str,
        limit: int = 20,
    ) -> list[VersionInfo]:
        """Get version history for a block."""
        async with self.session() as session:
            # Query dolt_history_memory_blocks for this specific block
            result = await session.execute(
                text("""
                    SELECT DISTINCT
                        commit_hash,
                        commit_date,
                        committer
                    FROM dolt_history_memory_blocks
                    WHERE user_id = :user_id AND label = :label
                    ORDER BY commit_date DESC
                    LIMIT :limit
                """),
                {"user_id": user_id, "label": label, "limit": limit},
            )

            versions = []
            for i, row in enumerate(result.fetchall()):
                # Get commit message from dolt_log
                log_result = await session.execute(
                    text("SELECT message FROM dolt_log WHERE commit_hash = :hash LIMIT 1"),
                    {"hash": row.commit_hash},
                )
                log_row = log_result.fetchone()
                message = log_row.message if log_row else "No message"

                versions.append(
                    VersionInfo(
                        commit_hash=row.commit_hash,
                        message=message,
                        author=row.committer,
                        timestamp=row.commit_date,
                        is_current=(i == 0),
                    )
                )

            return versions

    async def get_block_at_version(
        self,
        user_id: str,
        label: str,
        commit_hash: str,
    ) -> MemoryBlock | None:
        """Get a block's state at a specific commit."""
        async with self.session() as session:
            result = await session.execute(
                text("""
                    SELECT user_id, label, title, body, schema_ref, commit_date as updated_at
                    FROM dolt_history_memory_blocks
                    WHERE user_id = :user_id
                      AND label = :label
                      AND commit_hash = :commit_hash
                """),
                {"user_id": user_id, "label": label, "commit_hash": commit_hash},
            )
            row = result.fetchone()
            if not row:
                return None
            return MemoryBlock(
                user_id=row.user_id,
                label=row.label,
                title=row.title,
                body=row.body,
                schema_ref=row.schema_ref,
                updated_at=row.updated_at,
            )

    async def restore_block(
        self,
        user_id: str,
        label: str,
        commit_hash: str,
        author: str = "user",
    ) -> str:
        """Restore a block to a previous version. Returns new commit hash."""
        old_block = await self.get_block_at_version(user_id, label, commit_hash)
        if not old_block:
            raise ValueError(f"Block {label} not found at commit {commit_hash}")

        return await self.update_block(
            user_id=user_id,
            label=label,
            body=old_block.body or "",
            title=old_block.title,
            schema_ref=old_block.schema_ref,
            author=author,
            message=f"Restore {label} to {commit_hash[:8]}",
        )

    # -------------------------------------------------------------------------
    # Proposal Operations (Branch-based approval workflow)
    # -------------------------------------------------------------------------

    def _proposal_branch_name(self, user_id: str, block_label: str) -> str:
        """Generate branch name for a proposal."""
        return f"agent/{user_id}/{block_label}"

    def _parse_proposal_metadata(self, commit_message: str) -> dict[str, str]:
        """Parse proposal metadata from commit message JSON."""
        try:
            return json.loads(commit_message)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def create_proposal(
        self,
        user_id: str,
        block_label: str,
        new_body: str,
        agent_id: str,
        reasoning: str,
        confidence: str = "medium",
    ) -> str:
        """
        Create or append to a proposal branch, returning branch name.

        Agents can only propose body changes, not title or schema changes.
        """
        branch_name = self._proposal_branch_name(user_id, block_label)

        async with self.session() as session:
            # Check if branch already exists
            result = await session.execute(
                text("SELECT name FROM dolt_branches WHERE name = :name"),
                {"name": branch_name},
            )
            branch_exists = result.fetchone() is not None

            if branch_exists:
                # Switch to existing proposal branch (append to it)
                await session.execute(
                    text("CALL DOLT_CHECKOUT(:branch)"),
                    {"branch": branch_name},
                )
            else:
                # Create new branch from main
                await session.execute(
                    text("CALL DOLT_CHECKOUT('-b', :branch)"),
                    {"branch": branch_name},
                )

            try:
                # Make the proposed edit (body only, preserve other fields)
                await session.execute(
                    text("""
                        UPDATE memory_blocks
                        SET body = :body
                        WHERE user_id = :user_id AND label = :label
                    """),
                    {
                        "user_id": user_id,
                        "label": block_label,
                        "body": new_body,
                    },
                )
                await session.commit()

                # Commit with metadata in message
                metadata = json.dumps(
                    {
                        "agent_id": agent_id,
                        "reasoning": reasoning,
                        "confidence": confidence,
                        "block_label": block_label,
                        "user_id": user_id,
                    }
                )

                await session.execute(text("CALL DOLT_ADD('-A')"))
                await session.execute(
                    text("CALL DOLT_COMMIT('-m', :message, '--author', :author)"),
                    {
                        "message": metadata,
                        "author": f"agent:{agent_id} <agent@youlab>",
                    },
                )
            finally:
                # Always switch back to main
                await session.execute(text("CALL DOLT_CHECKOUT('main')"))

        return branch_name

    async def list_proposals(self, user_id: str) -> list[PendingProposal]:
        """List all pending proposals for a user."""
        prefix = f"agent/{user_id}/"

        async with self.session() as session:
            result = await session.execute(
                text("SELECT name FROM dolt_branches WHERE name LIKE :prefix"),
                {"prefix": f"{prefix}%"},
            )

            proposals = []
            for row in result.fetchall():
                branch_name = row.name
                block_label = branch_name.replace(prefix, "")

                # Get commit info from the branch using dolt_log table function
                log_result = await session.execute(
                    text(
                        "SELECT message, committer, date FROM dolt_log(:branch, '--parents') LIMIT 1"
                    ),
                    {"branch": branch_name},
                )
                log_row = log_result.fetchone()

                if log_row:
                    metadata = self._parse_proposal_metadata(log_row.message)
                    proposals.append(
                        PendingProposal(
                            branch_name=branch_name,
                            user_id=user_id,
                            block_label=block_label,
                            agent_id=metadata.get("agent_id", "unknown"),
                            reasoning=metadata.get("reasoning", ""),
                            confidence=metadata.get("confidence", "medium"),
                            created_at=log_row.date,
                        )
                    )

            return proposals

    async def get_proposal_diff(
        self,
        user_id: str,
        block_label: str,
    ) -> dict[str, str | datetime | None] | None:
        """Get the diff for a pending proposal."""
        branch_name = self._proposal_branch_name(user_id, block_label)

        async with self.session() as session:
            # Check branch exists
            result = await session.execute(
                text("SELECT name FROM dolt_branches WHERE name = :name"),
                {"name": branch_name},
            )
            if not result.fetchone():
                return None

            # Get diff between main and proposal branch
            result = await session.execute(
                text("""
                    SELECT * FROM dolt_diff('main', :branch, 'memory_blocks')
                    WHERE to_user_id = :user_id AND to_label = :label
                """),
                {"branch": branch_name, "user_id": user_id, "label": block_label},
            )
            row = result.fetchone()
            if not row:
                return None

            # Get proposal metadata from the latest commit on the branch
            log_result = await session.execute(
                text("SELECT message, date FROM dolt_log(:branch, '--parents') LIMIT 1"),
                {"branch": branch_name},
            )
            log_row = log_result.fetchone()
            metadata = self._parse_proposal_metadata(log_row.message) if log_row else {}

            return {
                "branch_name": branch_name,
                "block_label": block_label,
                "current_body": row.from_body,
                "proposed_body": row.to_body,
                "agent_id": metadata.get("agent_id"),
                "reasoning": metadata.get("reasoning"),
                "confidence": metadata.get("confidence"),
                "created_at": log_row.date if log_row else None,
            }

    async def approve_proposal(self, user_id: str, block_label: str) -> str:
        """Approve and merge a proposal. Returns merge commit hash."""
        branch_name = self._proposal_branch_name(user_id, block_label)

        async with self.session() as session:
            # Get proposal metadata for commit message
            log_result = await session.execute(
                text("SELECT message FROM dolt_log(:branch, '--parents') LIMIT 1"),
                {"branch": branch_name},
            )
            log_row = log_result.fetchone()
            metadata = self._parse_proposal_metadata(log_row.message) if log_row else {}
            reasoning = metadata.get("reasoning", "No reasoning provided")

            # Merge the branch
            result = await session.execute(
                text("CALL DOLT_MERGE(:branch, '-m', :message)"),
                {
                    "branch": branch_name,
                    "message": f"Approve agent proposal: {reasoning[:50]}",
                },
            )
            merge_result = result.fetchone()
            commit_hash = merge_result[0] if merge_result else "unknown"

            # Delete the branch
            await session.execute(
                text("CALL DOLT_BRANCH('-d', :branch)"),
                {"branch": branch_name},
            )

            return commit_hash

    async def reject_proposal(self, user_id: str, block_label: str) -> bool:
        """Reject a proposal by deleting its branch. Returns True if deleted."""
        branch_name = self._proposal_branch_name(user_id, block_label)

        async with self.session() as session:
            result = await session.execute(
                text("SELECT name FROM dolt_branches WHERE name = :name"),
                {"name": branch_name},
            )
            if not result.fetchone():
                return False

            await session.execute(
                text("CALL DOLT_BRANCH('-D', :branch)"),
                {"branch": branch_name},
            )
            return True

    async def count_pending_proposals(self, user_id: str) -> int:
        """Count pending proposals for a user."""
        prefix = f"agent/{user_id}/"
        async with self.session() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM dolt_branches WHERE name LIKE :prefix"),
                {"prefix": f"{prefix}%"},
            )
            return result.scalar() or 0


# Module-level singleton
_client: DoltClient | None = None


async def get_dolt_client() -> DoltClient:
    """Get the shared DoltClient instance."""
    global _client
    if _client is None:
        _client = DoltClient()
        await _client.connect()
    return _client


async def close_dolt_client() -> None:
    """Close the shared DoltClient instance."""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
