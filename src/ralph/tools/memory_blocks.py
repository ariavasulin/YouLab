"""Memory block tools for Ralph agent - Claude Code inspired editing."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from agno.run import RunContext  # noqa: TC002 - must be available at runtime for Agno
from agno.tools import Toolkit

from ralph.dolt import DoltClient, MemoryBlock

logger = logging.getLogger(__name__)


def _run_async_with_fresh_client(async_fn: Any) -> Any:
    """
    Run an async function that needs DoltClient from sync context.

    Creates a fresh DoltClient for thread-pool executions to avoid
    event loop attachment issues with the global singleton.

    Args:
        async_fn: A callable that takes a DoltClient and returns a coroutine.

    """

    async def _execute() -> Any:
        client = DoltClient()
        await client.connect()
        try:
            return await async_fn(client)
        finally:
            await client.disconnect()

    try:
        asyncio.get_running_loop()
        # In async context, use thread pool with fresh client
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _execute()).result(timeout=30)
    except RuntimeError:
        # No running loop, can use asyncio.run directly
        return asyncio.run(_execute())


def _get_user_id(run_context: RunContext) -> str | None:
    """Extract user_id from RunContext (via user_id or dependencies)."""
    user_id = run_context.user_id
    if not user_id:
        deps = run_context.dependencies or {}
        user_id = deps.get("user_id")
    return user_id


class MemoryBlockTools(Toolkit):
    """
    Tools for reading and proposing edits to student memory blocks.

    Memory blocks contain persistent information about the student that helps
    personalize tutoring. Agents can read blocks and propose edits, but edits
    require user approval before being applied.

    Inspired by Claude Code's Edit tool - uses surgical string replacement.

    Uses Agno's RunContext dependency injection for user_id (same as HonchoTools).
    """

    def __init__(self, agent_id: str = "ralph", **kwargs: Any) -> None:
        """
        Initialize memory block tools.

        Args:
            agent_id: Identifier for this agent (used in proposals).
            **kwargs: Additional arguments passed to Toolkit base class.

        """
        self.agent_id = agent_id

        tools = [
            self.list_memory_blocks,
            self.read_memory_block,
            self.propose_memory_edit,
        ]

        super().__init__(name="memory_block_tools", tools=tools, **kwargs)

    def list_memory_blocks(self, run_context: RunContext) -> str:
        """
        List all available memory blocks for the current student.

        Args:
            run_context: Agno run context with user_id (auto-injected).

        Returns:
            A formatted list of memory blocks with their labels and titles,
            or a message if no blocks exist.

        """
        user_id = _get_user_id(run_context)
        if not user_id:
            return "Unable to identify student. No user context available."

        try:

            async def _list(dolt: DoltClient) -> list[MemoryBlock]:
                return await dolt.list_blocks(user_id)

            blocks = _run_async_with_fresh_client(_list)

            if not blocks:
                return "No memory blocks exist for this student yet."

            lines = ["Available memory blocks:", ""]
            for block in blocks:
                title = block.title or block.label.replace("_", " ").title()
                lines.append(f"- {block.label}: {title}")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("list_memory_blocks failed: %s", e)
            return f"Error listing memory blocks: {e}"

    def read_memory_block(self, run_context: RunContext, block_label: str) -> str:
        """
        Read the current content of a memory block.

        Use this before proposing edits to see the exact current content.

        Args:
            run_context: Agno run context with user_id (auto-injected).
            block_label: The label/identifier of the block to read (e.g., "student", "goals")

        Returns:
            The block's current content, or an error message if not found.

        """
        user_id = _get_user_id(run_context)
        if not user_id:
            return "Unable to identify student. No user context available."

        try:

            async def _read(dolt: DoltClient) -> MemoryBlock | None:
                return await dolt.get_block(user_id, block_label)

            block = _run_async_with_fresh_client(_read)

            if not block:
                return f"Memory block '{block_label}' not found."

            title = block.title or block_label.replace("_", " ").title()
            body = block.body or "(empty)"

            return f"# {title}\n\n{body}"

        except Exception as e:
            logger.warning("read_memory_block failed for %s: %s", block_label, e)
            return f"Error reading memory block: {e}"

    def propose_memory_edit(  # noqa: PLR0911
        self,
        run_context: RunContext,
        block_label: str,
        old_string: str,
        new_string: str,
        reasoning: str,
        replace_all: bool = False,
    ) -> str:
        """
        Propose an edit to a memory block using string replacement.

        The edit will be submitted as a proposal that requires user approval.
        The old_string must match exactly (including whitespace) and must be
        unique in the block unless replace_all is True.

        IMPORTANT: You must read the memory block first to see its exact content.
        The edit will FAIL if old_string is not found or is not unique.

        Args:
            run_context: Agno run context with user_id (auto-injected).
            block_label: The label of the block to edit (e.g., "student", "goals")
            old_string: The exact text to find and replace. Must be unique unless replace_all=True.
            new_string: The text to replace it with. Must be different from old_string.
            reasoning: Brief explanation of why this edit is needed (shown to user for approval).
            replace_all: If True, replace all occurrences. If False (default), old_string must be unique.

        Returns:
            Success message if proposal created, or error message explaining what went wrong.

        """
        user_id = _get_user_id(run_context)
        if not user_id:
            return "Unable to identify student. No user context available."

        # Validate inputs
        if old_string == new_string:
            return "Error: old_string and new_string must be different."

        if not old_string:
            return "Error: old_string cannot be empty."

        if not reasoning:
            return "Error: reasoning is required to explain the edit to the user."

        try:

            async def _propose(dolt: DoltClient) -> tuple[str | None, str | None]:
                # Get current block content
                block = await dolt.get_block(user_id, block_label)
                if not block:
                    return None, f"Error: Memory block '{block_label}' not found."

                current_body = block.body or ""

                # Check if old_string exists
                if old_string not in current_body:
                    return None, (
                        f"Error: old_string not found in block '{block_label}'. "
                        "Make sure you've read the block first and the text matches exactly "
                        "(including whitespace and newlines)."
                    )

                # Check uniqueness unless replace_all
                occurrence_count = current_body.count(old_string)
                if occurrence_count > 1 and not replace_all:
                    return None, (
                        f"Error: old_string appears {occurrence_count} times in block '{block_label}'. "
                        "Provide a larger unique string with more surrounding context, "
                        "or set replace_all=True to replace all occurrences."
                    )

                # Apply the replacement
                if replace_all:
                    new_body = current_body.replace(old_string, new_string)
                else:
                    new_body = current_body.replace(old_string, new_string, 1)

                # Create the proposal via Dolt
                branch_name = await dolt.create_proposal(
                    user_id=user_id,
                    block_label=block_label,
                    new_body=new_body,
                    agent_id=self.agent_id,
                    reasoning=reasoning,
                    confidence="medium",
                )

                return branch_name, None

            branch_name, error = _run_async_with_fresh_client(_propose)

            if error:
                return error

            logger.info(
                "Memory edit proposed: user=%s block=%s branch=%s",
                user_id,
                block_label,
                branch_name,
            )

            return (
                f"Edit proposal created for block '{block_label}'. "
                f"The user will be asked to approve this change. "
                f"Reasoning provided: {reasoning}"
            )

        except Exception as e:
            logger.warning("propose_memory_edit failed for %s: %s", block_label, e)
            return f"Error creating edit proposal: {e}"
