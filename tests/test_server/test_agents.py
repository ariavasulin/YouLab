"""Tests for AgentManager."""

import json
from unittest.mock import MagicMock, patch

import pytest

from youlab_server.server.agents import AgentManager


class TestAgentManagerNaming:
    """Tests for agent naming conventions."""

    def test_agent_name_format(self):
        """Test agent name follows convention."""
        manager = AgentManager("http://localhost:8283")
        name = manager._agent_name("user123", "tutor")
        assert name == "youlab_user123_tutor"

    def test_agent_name_with_uuid(self):
        """Test agent name with UUID user_id."""
        manager = AgentManager("http://localhost:8283")
        name = manager._agent_name("550e8400-e29b-41d4-a716-446655440000", "tutor")
        assert name.startswith("youlab_")
        assert name.endswith("_tutor")

    def test_agent_metadata_format(self):
        """Test agent metadata structure."""
        manager = AgentManager("http://localhost:8283")
        metadata = manager._agent_metadata("user123", "tutor")

        assert metadata == {
            "youlab_user_id": "user123",
            "youlab_agent_type": "tutor",
        }


class TestAgentManagerCache:
    """Tests for agent cache functionality."""

    def test_cache_hit(self, mock_letta_client):
        """Test cache returns agent_id when present."""
        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client
        manager._cache[("user123", "tutor")] = "cached-agent-id"

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
        manager._client = mock_letta_client

        result = manager.get_agent_id("user123", "tutor")

        assert result == "letta-agent-id"
        assert manager._cache[("user123", "tutor")] == "letta-agent-id"

    def test_cache_miss_not_found(self, mock_letta_client):
        """Test None returned when agent doesn't exist."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.get_agent_id("user123", "tutor")

        assert result is None


class TestAgentManagerCreate:
    """Tests for agent creation."""

    @patch("youlab_server.server.agents.curriculum")
    def test_create_agent_new(self, mock_curriculum, mock_letta_client):
        """Test creating a new agent uses curriculum path."""
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        # Mock curriculum to return default course
        mock_course = MagicMock()
        mock_course.agent.model = "anthropic/claude-sonnet-4-20250514"
        mock_course.agent.embedding = "openai/text-embedding-3-small"
        mock_course.agent.system = "You are helpful."
        mock_course.agent.tools = []
        mock_course.blocks = {}
        mock_course.version = "1.0.0"
        mock_curriculum.get.return_value = mock_course
        mock_curriculum.get_block_registry.return_value = MagicMock(get=lambda _: None)

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.create_agent("user123", "tutor", "Alice")

        assert result == "new-agent-id"
        mock_curriculum.get.assert_called_with("default")
        mock_letta_client.agents.create.assert_called_once()

    @patch("youlab_server.server.agents.curriculum")
    def test_create_agent_already_exists(self, mock_curriculum, mock_letta_client):
        """Test creating agent when one already exists."""
        mock_agent = MagicMock()
        # Note: cache key uses course_id ("default") as agent_type
        mock_agent.name = "youlab_user123_default"
        mock_agent.id = "existing-agent-id"
        mock_letta_client.agents.list.return_value = [mock_agent]

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.create_agent("user123", "tutor")

        assert result == "existing-agent-id"
        mock_letta_client.agents.create.assert_not_called()

    @patch("youlab_server.server.agents.curriculum")
    def test_create_agent_unknown_type(self, mock_curriculum, mock_letta_client):
        """Test creating agent with unknown type raises error."""
        mock_letta_client.agents.list.return_value = []
        mock_curriculum.get.return_value = None

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        with pytest.raises(ValueError, match="Unknown course"):
            manager.create_agent("user123", "nonexistent_type")

    @patch("youlab_server.server.agents.curriculum")
    def test_create_agent_with_user_name(self, mock_curriculum, mock_letta_client):
        """Test agent creation includes user name in human block."""
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        # Mock curriculum with a human block
        mock_course = MagicMock()
        mock_course.agent.model = "anthropic/claude-sonnet-4-20250514"
        mock_course.agent.embedding = "openai/text-embedding-3-small"
        mock_course.agent.system = "You are helpful."
        mock_course.agent.tools = []
        mock_course.version = "1.0.0"

        # Create a proper block schema with label "human"
        mock_block_schema = MagicMock()
        mock_block_schema.label = "human"
        mock_block_schema.shared = False  # Not a shared block
        mock_course.blocks = {"human": mock_block_schema}
        mock_curriculum.get.return_value = mock_course

        # Mock block registry with a model class that can be instantiated
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.to_memory_string.return_value = "[NAME]\nAlice\n[ROLE]\nUser"
        mock_model_class.return_value = mock_instance

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_model_class
        mock_curriculum.get_block_registry.return_value = mock_registry

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.create_agent("user123", "tutor", "Alice")

        # Verify agents.create was called with memory_blocks containing user name
        call_kwargs = mock_letta_client.agents.create.call_args[1]
        assert "memory_blocks" in call_kwargs
        # Find the human block and check it contains Alice
        human_block = next(b for b in call_kwargs["memory_blocks"] if b["label"] == "human")
        assert "Alice" in human_block["value"]


class TestAgentManagerSharedBlocks:
    """Tests for shared block functionality."""

    @patch("youlab_server.server.agents.curriculum")
    def test_shared_block_created_and_reused(self, mock_curriculum, mock_letta_client):
        """Test that shared blocks are created once and reused across agents."""
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.blocks.list.return_value = []  # No existing blocks
        mock_letta_client.blocks.create.return_value = MagicMock(id="shared-block-id")
        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        # Mock course with a shared block
        mock_course = MagicMock()
        mock_course.agent.model = "anthropic/claude-sonnet-4-20250514"
        mock_course.agent.embedding = "openai/text-embedding-3-small"
        mock_course.agent.system = "You are helpful."
        mock_course.agent.tools = []
        mock_course.version = "1.0.0"

        # Create shared team block and regular human block
        mock_team_schema = MagicMock()
        mock_team_schema.label = "team"
        mock_team_schema.shared = True
        mock_team_schema.description = "Shared team context"

        mock_human_schema = MagicMock()
        mock_human_schema.label = "human"
        mock_human_schema.shared = False

        mock_course.blocks = {"team": mock_team_schema, "human": mock_human_schema}
        mock_curriculum.get.return_value = mock_course

        # Mock block registry
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.to_memory_string.return_value = "[BLOCK]\ntest"
        mock_model_class.return_value = mock_instance

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_model_class
        mock_curriculum.get_block_registry.return_value = mock_registry

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        # Create first agent
        manager.create_agent_from_curriculum("user1", "test-course")

        # Verify shared block was created
        mock_letta_client.blocks.create.assert_called_once()
        create_call = mock_letta_client.blocks.create.call_args
        assert create_call.kwargs["label"] == "team"
        assert "youlab_shared" in create_call.kwargs["name"]

        # Verify agent was created with block_ids for shared block
        agent_create_call = mock_letta_client.agents.create.call_args.kwargs
        assert agent_create_call["block_ids"] == ["shared-block-id"]

        # Reset create calls
        mock_letta_client.blocks.create.reset_mock()
        mock_letta_client.agents.create.reset_mock()
        mock_letta_client.agents.create.return_value = MagicMock(id="agent-2-id")

        # Create second agent - should reuse existing shared block
        manager.create_agent_from_curriculum("user2", "test-course")

        # Shared block should NOT be created again
        mock_letta_client.blocks.create.assert_not_called()

        # But agent should still be created with the same block_id
        agent_create_call = mock_letta_client.agents.create.call_args.kwargs
        assert agent_create_call["block_ids"] == ["shared-block-id"]

    @patch("youlab_server.server.agents.curriculum")
    def test_shared_block_found_in_letta(self, mock_curriculum, mock_letta_client):
        """Test that existing shared blocks in Letta are discovered."""
        mock_letta_client.agents.list.return_value = []

        # Mock existing block in Letta
        existing_block = MagicMock()
        existing_block.id = "existing-shared-block-id"
        existing_block.name = "youlab_shared_test-course_team"
        mock_letta_client.blocks.list.return_value = [existing_block]

        mock_letta_client.agents.create.return_value = MagicMock(id="new-agent-id")

        # Mock course with shared block
        mock_course = MagicMock()
        mock_course.agent.model = "anthropic/claude-sonnet-4-20250514"
        mock_course.agent.embedding = "openai/text-embedding-3-small"
        mock_course.agent.system = ""
        mock_course.agent.tools = []
        mock_course.version = "1.0.0"

        mock_team_schema = MagicMock()
        mock_team_schema.label = "team"
        mock_team_schema.shared = True
        mock_team_schema.description = ""

        mock_course.blocks = {"team": mock_team_schema}
        mock_curriculum.get.return_value = mock_course

        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.to_memory_string.return_value = "test"
        mock_model_class.return_value = mock_instance

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_model_class
        mock_curriculum.get_block_registry.return_value = mock_registry

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.create_agent_from_curriculum("user1", "test-course")

        # Should NOT create a new block since one already exists
        mock_letta_client.blocks.create.assert_not_called()

        # Should use the existing block ID
        agent_create_call = mock_letta_client.agents.create.call_args.kwargs
        assert agent_create_call["block_ids"] == ["existing-shared-block-id"]


class TestAgentManagerRebuildCache:
    """Tests for cache rebuilding on startup."""

    @pytest.mark.asyncio
    async def test_rebuild_cache_empty(self, mock_letta_client):
        """Test rebuilding cache when no agents exist."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        count = await manager.rebuild_cache()

        assert count == 0
        assert len(manager._cache) == 0

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
        manager._client = mock_letta_client

        count = await manager.rebuild_cache()

        assert count == 2
        assert manager._cache[("user1", "tutor")] == "agent-1"
        assert manager._cache[("user2", "tutor")] == "agent-2"

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
        manager._client = mock_letta_client

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
        manager._client = mock_letta_client

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
        manager._client = mock_letta_client

        result = manager.send_message("agent-123", "Hello!")

        assert result == "Fallback text"

    def test_send_message_empty_response(self, mock_letta_client):
        """Test handling empty response."""
        mock_response = MagicMock()
        mock_response.messages = []
        mock_letta_client.agents.messages.create.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.send_message("agent-123", "Hello!")

        assert result == ""


class TestAgentManagerHealthCheck:
    """Tests for Letta connection health check."""

    def test_check_connection_success(self, mock_letta_client):
        """Test successful connection check."""
        mock_letta_client.agents.list.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.check_letta_connection()

        assert result is True

    def test_check_connection_failure(self, mock_letta_client):
        """Test failed connection check."""
        mock_letta_client.agents.list.side_effect = Exception("Connection refused")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client

        result = manager.check_letta_connection()

        assert result is False


class TestChunkToSSEEvent:
    """Tests for AgentManager._chunk_to_sse_event()."""

    def test_reasoning_message(self, mock_agent_manager):
        """reasoning_message produces status event with thinking indicator."""
        chunk = MagicMock()
        chunk.message_type = "reasoning_message"
        chunk.reasoning = "Let me think about this..."

        result = mock_agent_manager._chunk_to_sse_event(chunk)

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

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        data = json.loads(result[6:-2])
        assert data["type"] == "status"
        assert data["content"] == "Using search_memory..."

    def test_tool_call_message_no_tool_call(self, mock_agent_manager):
        """tool_call_message handles missing tool_call gracefully."""
        chunk = MagicMock()
        chunk.message_type = "tool_call_message"
        chunk.tool_call = None

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        data = json.loads(result[6:-2])
        assert data["content"] == "Using tool..."

    def test_assistant_message_string(self, mock_agent_manager):
        """assistant_message with string content produces message event."""
        chunk = MagicMock()
        chunk.message_type = "assistant_message"
        chunk.content = "Hello! I'm your tutor."

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        data = json.loads(result[6:-2])
        assert data["type"] == "message"
        assert data["content"] == "Hello! I'm your tutor."

    def test_assistant_message_non_string(self, mock_agent_manager):
        """assistant_message with non-string content converts to string."""
        chunk = MagicMock()
        chunk.message_type = "assistant_message"
        chunk.content = ["Part 1", "Part 2"]

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        data = json.loads(result[6:-2])
        assert data["type"] == "message"
        assert "Part 1" in data["content"]

    def test_stop_reason(self, mock_agent_manager):
        """stop_reason produces done event."""
        chunk = MagicMock()
        chunk.message_type = "stop_reason"

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        data = json.loads(result[6:-2])
        assert data["type"] == "done"

    def test_ping(self, mock_agent_manager):
        """ping produces SSE comment for keep-alive."""
        chunk = MagicMock()
        chunk.message_type = "ping"

        result = mock_agent_manager._chunk_to_sse_event(chunk)

        assert result == ": keepalive\n\n"

    def test_error_message(self, mock_agent_manager):
        """error_message produces error event."""
        chunk = MagicMock()
        chunk.message_type = "error_message"
        chunk.message = "Something went wrong"

        result = mock_agent_manager._chunk_to_sse_event(chunk)

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

            result = mock_agent_manager._chunk_to_sse_event(chunk)
            assert result is None, f"{msg_type} should return None"

    def test_unknown_message_type(self, mock_agent_manager):
        """Unknown message types return None."""
        chunk = MagicMock()
        chunk.message_type = "future_message_type"

        result = mock_agent_manager._chunk_to_sse_event(chunk)
        assert result is None

    def test_missing_message_type(self, mock_agent_manager):
        """Chunk without message_type returns None."""
        chunk = MagicMock(spec=[])

        result = mock_agent_manager._chunk_to_sse_event(chunk)
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
        manager._client = mock_letta_client

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
        manager._client = mock_letta_client

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
        manager._client = mock_letta_client

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
        manager._client = mock_letta_client

        # Test with thinking enabled
        list(manager.stream_message("agent-123", "Hello", enable_thinking=True))
        call_kwargs = mock_letta_client.agents.messages.stream.call_args.kwargs
        assert call_kwargs["enable_thinking"] == "true"

        # Test with thinking disabled
        list(manager.stream_message("agent-123", "Hello", enable_thinking=False))
        call_kwargs = mock_letta_client.agents.messages.stream.call_args.kwargs
        assert call_kwargs["enable_thinking"] == "false"
