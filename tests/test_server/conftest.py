"""Server test fixtures."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_letta_client():
    """Mock Letta client for testing.

    Uses the letta_client SDK resource-based API:
    - client.agents.list() / create() / retrieve()
    - client.agents.messages.create() / stream()
    """
    client = MagicMock()

    # Resource-based API: client.agents.*
    client.agents = MagicMock()
    client.agents.list.return_value = []
    client.agents.create.return_value = MagicMock(id="agent-123", name="youlab_user1_tutor")
    client.agents.retrieve.return_value = MagicMock(
        id="agent-123",
        name="youlab_user1_tutor",
        metadata={"youlab_user_id": "user1", "youlab_agent_type": "tutor"},
    )

    # Resource-based API: client.agents.messages.*
    client.agents.messages = MagicMock()
    client.agents.messages.create.return_value = MagicMock(
        messages=[MagicMock(assistant_message="Hello! I'm your essay coach.")]
    )
    client.agents.messages.stream = MagicMock()

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
    from letta_starter.server.strategy import StrategyManager
    from letta_starter.server.strategy.router import get_strategy_manager

    # Set up agent manager
    app.state.agent_manager = mock_agent_manager

    # Set up a mock strategy manager using dependency override
    mock_strategy = StrategyManager.__new__(StrategyManager)
    mock_strategy._client = MagicMock()  # noqa: SLF001
    mock_strategy._agent_id = "strategy-agent-id"  # noqa: SLF001
    mock_strategy.letta_base_url = "http://localhost:8283"

    app.dependency_overrides[get_strategy_manager] = lambda: mock_strategy

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()
