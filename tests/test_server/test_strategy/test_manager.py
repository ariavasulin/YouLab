"""Tests for StrategyManager."""

from unittest.mock import MagicMock


class TestStrategyManagerSingleton:
    """Tests for singleton strategy agent management."""

    def test_ensure_agent_creates_new(self, mock_letta_client):
        """Test ensure_agent creates agent when none exists."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        agent_id = manager.ensure_agent()

        assert agent_id == "strategy-agent-id"
        mock_letta_client.create_agent.assert_called_once()

    def test_ensure_agent_returns_existing(self, mock_letta_client):
        """Test ensure_agent returns existing agent when one exists."""
        from letta_starter.server.strategy import StrategyManager

        mock_agent = MagicMock()
        mock_agent.name = "YouLab-Support"
        mock_agent.id = "existing-strategy-id"
        mock_letta_client.list_agents.return_value = [mock_agent]

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        agent_id = manager.ensure_agent()

        assert agent_id == "existing-strategy-id"
        mock_letta_client.create_agent.assert_not_called()

    def test_ensure_agent_caches_result(self, mock_letta_client):
        """Test ensure_agent caches the agent_id."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        # First call creates
        agent_id1 = manager.ensure_agent()
        # Second call returns cached
        agent_id2 = manager.ensure_agent()

        assert agent_id1 == agent_id2
        # Should only call create once
        assert mock_letta_client.create_agent.call_count == 1


class TestStrategyManagerDocuments:
    """Tests for document upload functionality."""

    def test_upload_document_success(self, mock_letta_client):
        """Test successful document upload."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.upload_document("Test content", tags=["test"])

        mock_letta_client.insert_archival_memory.assert_called_once()
        call_kwargs = mock_letta_client.insert_archival_memory.call_args[1]
        assert call_kwargs["agent_id"] == "strategy-agent-id"
        assert "Test content" in call_kwargs["memory"]

    def test_upload_document_with_tags(self, mock_letta_client):
        """Test document upload includes tags in content."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.upload_document("Architecture doc", tags=["architecture", "phase1"])

        call_kwargs = mock_letta_client.insert_archival_memory.call_args[1]
        # Tags should be included in the memory content
        assert "architecture" in call_kwargs["memory"]
        assert "phase1" in call_kwargs["memory"]

    def test_upload_document_empty_tags(self, mock_letta_client):
        """Test document upload with no tags."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.upload_document("Simple content", tags=[])

        mock_letta_client.insert_archival_memory.assert_called_once()


class TestStrategyManagerAsk:
    """Tests for asking questions."""

    def test_ask_success(self, mock_letta_client):
        """Test successful question asking."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")
        mock_response = MagicMock()
        mock_msg = MagicMock()
        mock_msg.assistant_message = "YouLab uses a microservices architecture."
        mock_response.messages = [mock_msg]
        mock_letta_client.send_message.return_value = mock_response

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        response = manager.ask("What is the architecture?")

        assert response == "YouLab uses a microservices architecture."
        mock_letta_client.send_message.assert_called_once()

    def test_ask_empty_response(self, mock_letta_client):
        """Test handling empty response."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")
        mock_response = MagicMock()
        mock_response.messages = []
        mock_letta_client.send_message.return_value = mock_response

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        response = manager.ask("What is the architecture?")

        assert response == ""

    def test_ask_uses_correct_agent(self, mock_letta_client):
        """Test ask sends message to strategy agent."""
        from letta_starter.server.strategy import StrategyManager

        mock_agent = MagicMock()
        mock_agent.name = "YouLab-Support"
        mock_agent.id = "existing-strategy-id"
        mock_letta_client.list_agents.return_value = [mock_agent]
        mock_response = MagicMock()
        mock_response.messages = [MagicMock(assistant_message="Answer")]
        mock_letta_client.send_message.return_value = mock_response

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        manager.ask("Question?")

        call_kwargs = mock_letta_client.send_message.call_args[1]
        assert call_kwargs["agent_id"] == "existing-strategy-id"


class TestStrategyManagerSearch:
    """Tests for searching archival memory."""

    def test_search_documents_success(self, mock_letta_client):
        """Test successful document search."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")
        mock_letta_client.get_archival_memory.return_value = [
            MagicMock(text="[TAGS: architecture] Architecture overview"),
            MagicMock(text="[TAGS: architecture] More architecture info"),
        ]

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        results = manager.search_documents("architecture", limit=5)

        assert len(results) == 2
        mock_letta_client.get_archival_memory.assert_called_once()

    def test_search_documents_empty_results(self, mock_letta_client):
        """Test search with no results."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []
        mock_letta_client.create_agent.return_value = MagicMock(id="strategy-agent-id")
        mock_letta_client.get_archival_memory.return_value = []

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        results = manager.search_documents("nonexistent")

        assert results == []


class TestStrategyManagerHealthCheck:
    """Tests for strategy agent health check."""

    def test_check_agent_exists_true(self, mock_letta_client):
        """Test check returns true when agent exists."""
        from letta_starter.server.strategy import StrategyManager

        mock_agent = MagicMock()
        mock_agent.name = "YouLab-Support"
        mock_agent.id = "strategy-id"
        mock_letta_client.list_agents.return_value = [mock_agent]

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        assert manager.check_agent_exists() is True

    def test_check_agent_exists_false(self, mock_letta_client):
        """Test check returns false when agent doesn't exist."""
        from letta_starter.server.strategy import StrategyManager

        mock_letta_client.list_agents.return_value = []

        manager = StrategyManager("http://localhost:8283")
        manager._client = mock_letta_client

        assert manager.check_agent_exists() is False
