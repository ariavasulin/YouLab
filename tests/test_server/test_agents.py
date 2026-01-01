"""Tests for AgentManager."""

import json
from unittest.mock import MagicMock

import pytest

from letta_starter.server.agents import AgentManager


class TestAgentManagerNaming:
    """Tests for agent naming conventions."""

    def test_agent_name_format(self):
        """Test agent name follows convention."""
        manager = AgentManager("http://localhost:8283")
        name = manager._agent_name("user123", "tutor")  # noqa: SLF001
        assert name == "youlab_user123_tutor"

    def test_agent_name_with_uuid(self):
        """Test agent name with UUID user_id."""
        manager = AgentManager("http://localhost:8283")
        name = manager._agent_name("550e8400-e29b-41d4-a716-446655440000", "tutor")  # noqa: SLF001
        assert name.startswith("youlab_")
        assert name.endswith("_tutor")

    def test_agent_metadata_format(self):
        """Test agent metadata structure."""
        manager = AgentManager("http://localhost:8283")
        metadata = manager._agent_metadata("user123", "tutor")  # noqa: SLF001

        assert metadata == {
            "youlab_user_id": "user123",
            "youlab_agent_type": "tutor",
        }


class TestAgentManagerCache:
    """Tests for agent cache functionality."""

    def test_cache_hit(self, mock_letta_client):
        """Test cache returns agent_id when present."""
        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001
        manager._cache[("user123", "tutor")] = "cached-agent-id"  # noqa: SLF001

        result = manager.get_agent_id("user123", "tutor")

        assert result == "cached-agent-id"
        # Should not call Letta
        mock_letta_client.agents.list.assert_not_called()

    def test_cache_miss_lookup(self, mock_letta_client):
        """Test Letta lookup on cache miss."""
        mock_agent = MagicMock()
        mock_agent.name = "youlab_user123_tutor"
        mock_agent.id = "letta-agent-id"
        mock_letta_client.agents.list.return_value = [mock_agent]

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.get_agent_id("user123", "tutor")

        assert result == "letta-agent-id"
        assert manager._cache[("user123", "tutor")] == "letta-agent-id"  # noqa: SLF001

    def test_cache_miss_not_found(self, mock_letta_client):
        """Test None returned when agent doesn't exist."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.get_agent_id("user123", "tutor")

        assert result is None


class TestAgentManagerCreate:
    """Tests for agent creation."""

    def test_create_agent_new(self, mock_letta_client):
        """Test creating a new agent."""
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.create_agent("user123", "tutor", "Alice")

        assert result == "new-agent-id"
        mock_letta_client.agents.create.assert_called_once()

    def test_create_agent_already_exists(self, mock_letta_client):
        """Test creating agent when one already exists."""
        mock_agent = MagicMock()
        mock_agent.name = "youlab_user123_tutor"
        mock_agent.id = "existing-agent-id"
        mock_letta_client.agents.list.return_value = [mock_agent]

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.create_agent("user123", "tutor")

        assert result == "existing-agent-id"
        mock_letta_client.agents.create.assert_not_called()

    def test_create_agent_unknown_type(self, mock_letta_client):
        """Test creating agent with unknown type raises error."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        with pytest.raises(ValueError, match="Unknown agent type"):
            manager.create_agent("user123", "nonexistent_type")

    def test_create_agent_with_user_name(self, mock_letta_client):
        """Test agent creation includes user name in human block."""
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        manager.create_agent("user123", "tutor", "Alice")

        # Verify agents.create was called with memory_blocks containing user name
        call_kwargs = mock_letta_client.agents.create.call_args[1]
        assert "memory_blocks" in call_kwargs
        # Find the human block and check it contains Alice
        human_block = next(b for b in call_kwargs["memory_blocks"] if b["label"] == "human")
        assert "Alice" in human_block["value"]


class TestAgentManagerRebuildCache:
    """Tests for cache rebuilding on startup."""

    @pytest.mark.asyncio
    async def test_rebuild_cache_empty(self, mock_letta_client):
        """Test rebuilding cache when no agents exist."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        count = await manager.rebuild_cache()

        assert count == 0
        assert len(manager._cache) == 0  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_rebuild_cache_with_agents(self, mock_letta_client):
        """Test rebuilding cache discovers existing agents."""
        mock_agents = [
            MagicMock(
                name="youlab_user1_tutor",
                id="agent-1",
                metadata={"youlab_user_id": "user1", "youlab_agent_type": "tutor"},
            ),
            MagicMock(
                name="youlab_user2_tutor",
                id="agent-2",
                metadata={"youlab_user_id": "user2", "youlab_agent_type": "tutor"},
            ),
        ]
        mock_letta_client.agents.list.return_value = mock_agents

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        count = await manager.rebuild_cache()

        assert count == 2
        assert manager._cache[("user1", "tutor")] == "agent-1"  # noqa: SLF001
        assert manager._cache[("user2", "tutor")] == "agent-2"  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_rebuild_cache_ignores_non_youlab(self, mock_letta_client):
        """Test cache rebuild ignores non-YouLab agents."""
        mock_agents = [
            MagicMock(name="some_other_agent", id="other-1", metadata={}),
            MagicMock(
                name="youlab_user1_tutor",
                id="agent-1",
                metadata={"youlab_user_id": "user1", "youlab_agent_type": "tutor"},
            ),
        ]
        mock_letta_client.agents.list.return_value = mock_agents

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        count = await manager.rebuild_cache()

        assert count == 1


class TestAgentManagerSendMessage:
    """Tests for sending messages to agents."""

    def test_send_message_success(self, mock_letta_client):
        """Test successful message sending."""
        mock_response = MagicMock()
        mock_msg = MagicMock()
        mock_msg.assistant_message = "Hello! I'm your coach."
        mock_response.messages = [mock_msg]
        mock_letta_client.agents.messages.create.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.send_message("agent-123", "Hello!")

        assert result == "Hello! I'm your coach."

    def test_send_message_extracts_text(self, mock_letta_client):
        """Test message extraction handles different response formats."""
        mock_response = MagicMock()
        mock_msg = MagicMock()
        mock_msg.assistant_message = None
        mock_msg.text = "Fallback text"
        mock_response.messages = [mock_msg]
        mock_letta_client.agents.messages.create.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.send_message("agent-123", "Hello!")

        assert result == "Fallback text"

    def test_send_message_empty_response(self, mock_letta_client):
        """Test handling empty response."""
        mock_response = MagicMock()
        mock_response.messages = []
        mock_letta_client.agents.messages.create.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.send_message("agent-123", "Hello!")

        assert result == ""


class TestAgentManagerHealthCheck:
    """Tests for Letta connection health check."""

    def test_check_connection_success(self, mock_letta_client):
        """Test successful connection check."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.check_letta_connection()

        assert result is True

    def test_check_connection_failure(self, mock_letta_client):
        """Test failed connection check."""
        mock_letta_client.agents.list.side_effect = Exception("Connection refused")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.check_letta_connection()

        assert result is False


class TestChunkToSSEEvent:
    """Tests for AgentManager._chunk_to_sse_event()."""

    def test_reasoning_message(self, mock_agent_manager):
        """reasoning_message produces status event with thinking indicator."""
        chunk = MagicMock()
        chunk.message_type = "reasoning_message"
        chunk.reasoning = "Let me think about this..."

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        assert result is not None
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        data = json.loads(result[6:-2])
        assert data["type"] == "status"
        assert data["content"] == "Thinking..."
        assert data["reasoning"] == "Let me think about this..."

    def test_tool_call_message(self, mock_agent_manager):
        """tool_call_message produces status event with tool name."""
        chunk = MagicMock()
        chunk.message_type = "tool_call_message"
        chunk.tool_call = MagicMock()
        chunk.tool_call.name = "search_memory"

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["type"] == "status"
        assert data["content"] == "Using search_memory..."

    def test_tool_call_message_no_tool_call(self, mock_agent_manager):
        """tool_call_message handles missing tool_call gracefully."""
        chunk = MagicMock()
        chunk.message_type = "tool_call_message"
        chunk.tool_call = None

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["content"] == "Using tool..."

    def test_assistant_message_string(self, mock_agent_manager):
        """assistant_message with string content produces message event."""
        chunk = MagicMock()
        chunk.message_type = "assistant_message"
        chunk.content = "Hello! I'm your tutor."

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["type"] == "message"
        assert data["content"] == "Hello! I'm your tutor."

    def test_assistant_message_non_string(self, mock_agent_manager):
        """assistant_message with non-string content converts to string."""
        chunk = MagicMock()
        chunk.message_type = "assistant_message"
        chunk.content = ["Part 1", "Part 2"]

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["type"] == "message"
        assert "Part 1" in data["content"]

    def test_stop_reason(self, mock_agent_manager):
        """stop_reason produces done event."""
        chunk = MagicMock()
        chunk.message_type = "stop_reason"

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["type"] == "done"

    def test_ping(self, mock_agent_manager):
        """ping produces SSE comment for keep-alive."""
        chunk = MagicMock()
        chunk.message_type = "ping"

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        assert result == ": keepalive\n\n"

    def test_error_message(self, mock_agent_manager):
        """error_message produces error event."""
        chunk = MagicMock()
        chunk.message_type = "error_message"
        chunk.message = "Something went wrong"

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001

        data = json.loads(result[6:-2])
        assert data["type"] == "error"
        assert data["message"] == "Something went wrong"

    def test_ignored_message_types(self, mock_agent_manager):
        """Internal message types return None (ignored)."""
        ignored_types = [
            "tool_return_message",
            "usage_statistics",
            "hidden_reasoning_message",
            "system_message",
            "user_message",
        ]

        for msg_type in ignored_types:
            chunk = MagicMock()
            chunk.message_type = msg_type

            result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001
            assert result is None, f"{msg_type} should return None"

    def test_unknown_message_type(self, mock_agent_manager):
        """Unknown message types return None."""
        chunk = MagicMock()
        chunk.message_type = "future_message_type"

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001
        assert result is None

    def test_missing_message_type(self, mock_agent_manager):
        """Chunk without message_type returns None."""
        chunk = MagicMock(spec=[])

        result = mock_agent_manager._chunk_to_sse_event(chunk)  # noqa: SLF001
        assert result is None


class TestStreamMessage:
    """Tests for AgentManager.stream_message()."""

    def test_stream_yields_events(self, mock_letta_client):
        """stream_message yields SSE events from Letta stream."""
        # Create mock chunks
        reasoning_chunk = MagicMock()
        reasoning_chunk.message_type = "reasoning_message"
        reasoning_chunk.reasoning = "Thinking..."

        message_chunk = MagicMock()
        message_chunk.message_type = "assistant_message"
        message_chunk.content = "Hello!"

        done_chunk = MagicMock()
        done_chunk.message_type = "stop_reason"

        # Mock the stream context manager
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(
            return_value=iter([reasoning_chunk, message_chunk, done_chunk])
        )
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        # Set up nested attribute access
        mock_letta_client.agents = MagicMock()
        mock_letta_client.agents.messages = MagicMock()
        mock_letta_client.agents.messages.stream = MagicMock(return_value=mock_stream)

        # Create manager
        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        # Collect events
        events = list(manager.stream_message("agent-123", "Hello"))

        # Verify we got expected events
        assert len(events) == 3
        assert '"type": "status"' in events[0]
        assert '"type": "message"' in events[1]
        assert '"type": "done"' in events[2]

    def test_stream_filters_ignored_chunks(self, mock_letta_client):
        """stream_message filters out internal message types."""
        # Mix of visible and internal chunks
        visible_chunk = MagicMock()
        visible_chunk.message_type = "assistant_message"
        visible_chunk.content = "Hello!"

        internal_chunk = MagicMock()
        internal_chunk.message_type = "tool_return_message"

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(
            return_value=iter([internal_chunk, visible_chunk, internal_chunk])
        )
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        mock_letta_client.agents = MagicMock()
        mock_letta_client.agents.messages = MagicMock()
        mock_letta_client.agents.messages.stream = MagicMock(return_value=mock_stream)

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        events = list(manager.stream_message("agent-123", "Hello"))

        # Only the visible chunk should produce an event
        assert len(events) == 1
        assert '"type": "message"' in events[0]

    def test_stream_handles_exception(self, mock_letta_client):
        """stream_message yields error event on exception."""
        mock_letta_client.agents = MagicMock()
        mock_letta_client.agents.messages = MagicMock()
        mock_letta_client.agents.messages.stream = MagicMock(
            side_effect=Exception("Connection failed")
        )

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        events = list(manager.stream_message("agent-123", "Hello"))

        assert len(events) == 1
        assert '"type": "error"' in events[0]
        assert "Connection failed" in events[0]

    def test_stream_passes_enable_thinking(self, mock_letta_client):
        """stream_message passes enable_thinking to SDK."""
        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        mock_letta_client.agents = MagicMock()
        mock_letta_client.agents.messages = MagicMock()
        mock_letta_client.agents.messages.stream = MagicMock(return_value=mock_stream)

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        # Test with thinking enabled
        list(manager.stream_message("agent-123", "Hello", enable_thinking=True))
        call_kwargs = mock_letta_client.agents.messages.stream.call_args.kwargs
        assert call_kwargs["enable_thinking"] == "true"

        # Test with thinking disabled
        list(manager.stream_message("agent-123", "Hello", enable_thinking=False))
        call_kwargs = mock_letta_client.agents.messages.stream.call_args.kwargs
        assert call_kwargs["enable_thinking"] == "false"
