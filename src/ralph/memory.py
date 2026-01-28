"""Memory block loading for agent instructions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ralph.dolt import DoltClient


async def build_memory_context(dolt: DoltClient, user_id: str) -> str:
    """
    Build memory context string for agent instructions.

    Args:
        dolt: DoltClient instance for database access
        user_id: The user ID to fetch memory blocks for

    Returns:
        A formatted markdown string with all memory blocks, or empty string if none.

    """
    blocks = await dolt.list_blocks(user_id)

    if not blocks:
        return ""

    sections = ["## Student Memory\n"]

    for block in blocks:
        title = block.title or block.label.replace("_", " ").title()
        body = block.body or "(empty)"
        sections.append(f"### {title}\n\n{body}\n")

    return "\n".join(sections)


async def get_block_for_agent(
    dolt: DoltClient,
    user_id: str,
    label: str,
) -> str | None:
    """
    Get a specific block's content for agent use.

    Args:
        dolt: DoltClient instance for database access
        user_id: The user ID to fetch the block for
        label: The block label (e.g., "student", "journey")

    Returns:
        The block body content, or None if not found.

    """
    block = await dolt.get_block(user_id, label)
    if not block:
        return None
    return block.body
