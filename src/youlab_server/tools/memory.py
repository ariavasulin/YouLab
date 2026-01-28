"""
Memory block editing tool for Letta agents.

This module provides the edit_memory_block tool that agents use to propose
changes to user memory blocks. Changes create pending diffs that require
user approval before being applied.

Note (ARI-85): This tool fails when used by background agents in Letta sandbox.
The sandbox doesn't have access to youlab_server imports.
"""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger()

# Global references
_letta_client: Any = None


def set_letta_client(client: Any) -> None:
    """Set the global Letta client for tool use."""
    global _letta_client
    _letta_client = client


def edit_memory_block(
    block: str,
    field: str,
    content: str,
    strategy: str = "append",
    reasoning: str = "",
    agent_state: dict[str, Any] | None = None,
) -> str:
    """
    Propose an update to a memory block.

    This creates a pending diff that the user must approve.
    The change is NOT applied immediately.

    Args:
        block: Which memory block to edit (e.g., "student", "journey")
        field: Which field to update
        content: The content to add or replace
        strategy: How to merge: "append", "replace", or "llm_diff"
        reasoning: Explain WHY you're proposing this change
        agent_state: Agent state injected by Letta

    Returns:
        Confirmation that the proposal was created

    """
    from youlab_server.server.users import get_storage_manager
    from youlab_server.storage.blocks import UserBlockManager

    agent_id = agent_state.get("agent_id") if agent_state else None
    user_id = agent_state.get("user_id") if agent_state else None

    if not agent_id or not user_id:
        return "Unable to identify agent or user. Proposal not created."

    try:
        storage_manager = get_storage_manager()
        user_storage = storage_manager.get(user_id)

        # Check if user storage exists
        if not user_storage.exists:
            log.warning(
                "user_storage_not_found",
                user_id=user_id,
                agent_id=agent_id,
            )
            return f"User storage not initialized for {user_id}. Proposal not created."

        manager = UserBlockManager(user_id, user_storage, letta_client=_letta_client)

        diff = manager.propose_edit(
            agent_id=agent_id,
            block_label=block,
            field=field,
            operation=strategy,
            proposed_value=content,
            reasoning=reasoning or "No reasoning provided",
        )

        log.info(
            "memory_edit_proposed",
            agent_id=agent_id,
            user_id=user_id,
            block=block,
            field=field,
            diff_id=diff.id[:8],
        )

        return (
            f"Proposed change to {block}.{field} (ID: {diff.id[:8]}). "
            f"The user will review and approve/reject this suggestion."
        )

    except Exception as e:
        log.error(
            "propose_edit_failed",
            agent_id=agent_id,
            user_id=user_id,
            block=block,
            error=str(e),
        )
        return f"Failed to create proposal: {e}"
