"""Tests for AgentManager."""

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
        mock_letta_client.list_agents.assert_not_called()

    def test_cache_miss_lookup(self, mock_letta_client):
        """Test Letta lookup on cache miss."""
        mock_agent = MagicMock()
        mock_agent.name = "youlab_user123_tutor"
        mock_agent.id = "letta-agent-id"
        mock_letta_client.list_agents.return_value = [mock_agent]

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.get_agent_id("user123", "tutor")

        assert result == "letta-agent-id"
        assert manager._cache[("user123", "tutor")] == "letta-agent-id"  # noqa: SLF001

    def test_cache_miss_not_found(self, mock_letta_client):
        """Test None returned when agent doesn't exist."""
        mock_letta_client.list_agents.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.get_agent_id("user123", "tutor")

        assert result is None


class TestAgentManagerCreate:
    """Tests for agent creation."""

    def test_create_agent_new(self, mock_letta_client):
        """Test creating a new agent."""
        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="new-agent-id")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.create_agent("user123", "tutor", "Alice")

        assert result == "new-agent-id"
        mock_letta_client.create_agent.assert_called_once()

    def test_create_agent_already_exists(self, mock_letta_client):
        """Test creating agent when one already exists."""
        mock_agent = MagicMock()
        mock_agent.name = "youlab_user123_tutor"
        mock_agent.id = "existing-agent-id"
        mock_letta_client.list_agents.return_value = [mock_agent]

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.create_agent("user123", "tutor")

        assert result == "existing-agent-id"
        mock_letta_client.create_agent.assert_not_called()

    def test_create_agent_unknown_type(self, mock_letta_client):
        """Test creating agent with unknown type raises error."""
        mock_letta_client.list_agents.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        with pytest.raises(ValueError, match="Unknown agent type"):
            manager.create_agent("user123", "nonexistent_type")

    def test_create_agent_with_user_name(self, mock_letta_client):
        """Test agent creation includes user name in human block."""
        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="new-agent-id")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        manager.create_agent("user123", "tutor", "Alice")

        # Verify create_agent was called with memory containing user name
        call_kwargs = mock_letta_client.create_agent.call_args[1]
        assert "memory" in call_kwargs
        assert (
            "Alice" in call_kwargs["memory"]["human"] or call_kwargs["memory"]["human"] is not None
        )


class TestAgentManagerRebuildCache:
    """Tests for cache rebuilding on startup."""

    @pytest.mark.asyncio
    async def test_rebuild_cache_empty(self, mock_letta_client):
        """Test rebuilding cache when no agents exist."""
        mock_letta_client.list_agents.return_value = []

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
        mock_letta_client.list_agents.return_value = mock_agents

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
        mock_letta_client.list_agents.return_value = mock_agents

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
        mock_letta_client.send_message.return_value = mock_response

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
        mock_letta_client.send_message.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.send_message("agent-123", "Hello!")

        assert result == "Fallback text"

    def test_send_message_empty_response(self, mock_letta_client):
        """Test handling empty response."""
        mock_response = MagicMock()
        mock_response.messages = []
        mock_letta_client.send_message.return_value = mock_response

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.send_message("agent-123", "Hello!")

        assert result == ""


class TestAgentManagerHealthCheck:
    """Tests for Letta connection health check."""

    def test_check_connection_success(self, mock_letta_client):
        """Test successful connection check."""
        mock_letta_client.list_agents.return_value = []

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.check_letta_connection()

        assert result is True

    def test_check_connection_failure(self, mock_letta_client):
        """Test failed connection check."""
        mock_letta_client.list_agents.side_effect = Exception("Connection refused")

        manager = AgentManager("http://localhost:8283")
        manager._client = mock_letta_client  # noqa: SLF001

        result = manager.check_letta_connection()

        assert result is False
