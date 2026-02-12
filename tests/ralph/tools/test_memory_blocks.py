"""Tests for MemoryBlockTools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ralph.dolt import MemoryBlock
from ralph.tools.memory_blocks import MemoryBlockTools


@pytest.fixture
def mock_run_context() -> MagicMock:
    """Create a mock RunContext with user_id."""
    ctx = MagicMock()
    ctx.user_id = "test-user-123"
    ctx.dependencies = {"user_id": "test-user-123"}
    return ctx


@pytest.fixture
def mock_dolt() -> MagicMock:
    """Create a mock DoltClient."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def tools() -> MemoryBlockTools:
    """Create MemoryBlockTools instance."""
    return MemoryBlockTools(agent_id="test-agent")


def make_run_async_mock(mock_dolt: MagicMock) -> Any:
    """Create a mock for _run_async_with_fresh_client that injects mock_dolt."""

    def _mock_run(async_fn: Any) -> Any:
        import asyncio

        async def _execute() -> Any:
            return await async_fn(mock_dolt)

        return asyncio.get_event_loop().run_until_complete(_execute())

    return _mock_run


class TestListMemoryBlocks:
    """Tests for list_memory_blocks tool."""

    def test_list_blocks_returns_formatted_list(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should return formatted list of blocks."""
        mock_dolt.list_blocks = AsyncMock(
            return_value=[
                MemoryBlock(
                    user_id="test-user-123",
                    label="student",
                    title="Student Profile",
                    body="content",
                    schema_ref=None,
                    updated_at=datetime.now(UTC),
                ),
                MemoryBlock(
                    user_id="test-user-123",
                    label="goals",
                    title="Learning Goals",
                    body="content",
                    schema_ref=None,
                    updated_at=datetime.now(UTC),
                ),
            ]
        )

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.list_memory_blocks(mock_run_context)

        assert "student: Student Profile" in result
        assert "goals: Learning Goals" in result

    def test_list_blocks_empty(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should handle no blocks gracefully."""
        mock_dolt.list_blocks = AsyncMock(return_value=[])

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.list_memory_blocks(mock_run_context)

        assert "No memory blocks exist" in result

    def test_list_blocks_no_user(self, tools: MemoryBlockTools) -> None:
        """Should fail gracefully when no user_id available."""
        ctx = MagicMock()
        ctx.user_id = None
        ctx.dependencies = {}

        result = tools.list_memory_blocks(ctx)

        assert "Unable to identify student" in result


class TestReadMemoryBlock:
    """Tests for read_memory_block tool."""

    def test_read_block_returns_content(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should return block content with title."""
        mock_dolt.get_block = AsyncMock(
            return_value=MemoryBlock(
                user_id="test-user-123",
                label="student",
                title="Student Profile",
                body="## About\n\nTest content here.",
                schema_ref=None,
                updated_at=datetime.now(UTC),
            )
        )

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.read_memory_block(mock_run_context, "student")

        assert "# Student Profile" in result
        assert "Test content here" in result

    def test_read_block_not_found(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should return error for missing block."""
        mock_dolt.get_block = AsyncMock(return_value=None)

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.read_memory_block(mock_run_context, "nonexistent")

        assert "not found" in result


class TestProposeMemoryEdit:
    """Tests for propose_memory_edit tool."""

    def test_propose_edit_success(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should create proposal when old_string is unique."""
        mock_dolt.get_block = AsyncMock(
            return_value=MemoryBlock(
                user_id="test-user-123",
                label="student",
                title="Student Profile",
                body="The student likes math.",
                schema_ref=None,
                updated_at=datetime.now(UTC),
            )
        )
        mock_dolt.create_proposal = AsyncMock(return_value="agent/test-user-123/student")

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.propose_memory_edit(
                mock_run_context,
                block_label="student",
                old_string="likes math",
                new_string="loves mathematics",
                reasoning="Student expressed stronger enthusiasm",
            )

        assert "proposal created" in result.lower()
        mock_dolt.create_proposal.assert_called_once()
        call_args = mock_dolt.create_proposal.call_args
        assert "loves mathematics" in call_args.kwargs["new_body"]

    def test_propose_edit_old_string_not_found(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should fail when old_string not in block."""
        mock_dolt.get_block = AsyncMock(
            return_value=MemoryBlock(
                user_id="test-user-123",
                label="student",
                title="Student Profile",
                body="The student likes math.",
                schema_ref=None,
                updated_at=datetime.now(UTC),
            )
        )

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.propose_memory_edit(
                mock_run_context,
                block_label="student",
                old_string="not in content",
                new_string="replacement",
                reasoning="test",
            )

        assert "not found" in result.lower()
        assert "read the block first" in result.lower()

    def test_propose_edit_non_unique_fails(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should fail when old_string appears multiple times."""
        mock_dolt.get_block = AsyncMock(
            return_value=MemoryBlock(
                user_id="test-user-123",
                label="student",
                title="Student Profile",
                body="The student likes math. The student also likes science.",
                schema_ref=None,
                updated_at=datetime.now(UTC),
            )
        )

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.propose_memory_edit(
                mock_run_context,
                block_label="student",
                old_string="The student",
                new_string="This student",
                reasoning="test",
            )

        assert "appears 2 times" in result
        assert "replace_all" in result.lower()

    def test_propose_edit_replace_all(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should replace all occurrences when replace_all=True."""
        mock_dolt.get_block = AsyncMock(
            return_value=MemoryBlock(
                user_id="test-user-123",
                label="student",
                title="Student Profile",
                body="The student likes math. The student also likes science.",
                schema_ref=None,
                updated_at=datetime.now(UTC),
            )
        )
        mock_dolt.create_proposal = AsyncMock(return_value="agent/test-user-123/student")

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.propose_memory_edit(
                mock_run_context,
                block_label="student",
                old_string="The student",
                new_string="This student",
                reasoning="test",
                replace_all=True,
            )

        assert "proposal created" in result.lower()
        call_args = mock_dolt.create_proposal.call_args
        new_body = call_args.kwargs["new_body"]
        assert new_body.count("This student") == 2
        assert "The student" not in new_body

    def test_propose_edit_same_string_fails(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock
    ) -> None:
        """Should fail when old_string equals new_string."""
        result = tools.propose_memory_edit(
            mock_run_context,
            block_label="student",
            old_string="same",
            new_string="same",
            reasoning="test",
        )

        assert "must be different" in result.lower()

    def test_propose_edit_empty_old_string_fails(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock
    ) -> None:
        """Should fail when old_string is empty."""
        result = tools.propose_memory_edit(
            mock_run_context,
            block_label="student",
            old_string="",
            new_string="something",
            reasoning="test",
        )

        assert "cannot be empty" in result.lower()

    def test_propose_edit_missing_reasoning_fails(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock
    ) -> None:
        """Should fail when reasoning is empty."""
        result = tools.propose_memory_edit(
            mock_run_context,
            block_label="student",
            old_string="old",
            new_string="new",
            reasoning="",
        )

        assert "reasoning is required" in result.lower()

    def test_propose_edit_block_not_found(
        self, tools: MemoryBlockTools, mock_run_context: MagicMock, mock_dolt: MagicMock
    ) -> None:
        """Should fail when block doesn't exist."""
        mock_dolt.get_block = AsyncMock(return_value=None)

        with patch(
            "ralph.tools.memory_blocks._run_async_with_fresh_client",
            make_run_async_mock(mock_dolt),
        ):
            result = tools.propose_memory_edit(
                mock_run_context,
                block_label="nonexistent",
                old_string="old",
                new_string="new",
                reasoning="test",
            )

        assert "not found" in result.lower()
