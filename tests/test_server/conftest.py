"""Server test fixtures."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_letta_client():
    """Mock Letta client for testing."""
    client = MagicMock()
    client.list_agents.return_value = []
    client.create_agent.return_value = MagicMock(id="agent-123", name="youlab_user1_tutor")
    client.get_agent.return_value = MagicMock(
        id="agent-123",
        name="youlab_user1_tutor",
        metadata={"youlab_user_id": "user1", "youlab_agent_type": "tutor"},
    )
    client.send_message.return_value = MagicMock(
        messages=[MagicMock(assistant_message="Hello! I'm your essay coach.")]
    )
    return client


@pytest.fixture
def mock_agent_manager(mock_letta_client):
    """Mock AgentManager for endpoint testing."""
    from letta_starter.server.agents import AgentManager

    manager = AgentManager.__new__(AgentManager)
    manager._client = mock_letta_client  # noqa: SLF001
    manager._cache = {}  # noqa: SLF001
    manager.letta_base_url = "http://localhost:8283"
    return manager


@pytest.fixture
def test_client(mock_agent_manager):
    """Test client with mocked dependencies."""
    from letta_starter.server.main import app

    app.state.agent_manager = mock_agent_manager
    return TestClient(app)
