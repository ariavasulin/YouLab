"""Strategy test fixtures."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_letta_client():
    """Mock Letta client for testing."""
    client = MagicMock()
    client.list_agents.return_value = []
    client.create_agent.return_value = MagicMock(id="agent-123", name="YouLab-Support")
    client.get_agent.return_value = MagicMock(
        id="agent-123",
        name="YouLab-Support",
        metadata={},
    )
    client.send_message.return_value = MagicMock(
        messages=[MagicMock(assistant_message="Hello! I'm your strategy advisor.")]
    )
    return client


@pytest.fixture
def mock_strategy_manager(mock_letta_client):
    """Mock StrategyManager for endpoint testing."""
    from letta_starter.server.strategy import StrategyManager

    manager = StrategyManager.__new__(StrategyManager)
    manager._client = mock_letta_client  # noqa: SLF001
    manager._agent_id = "strategy-agent-id"  # noqa: SLF001
    manager.letta_base_url = "http://localhost:8283"
    return manager


@pytest.fixture
def strategy_test_client(mock_strategy_manager):
    """Test client with mocked strategy manager using dependency override."""
    from letta_starter.server.agents import AgentManager
    from letta_starter.server.main import app
    from letta_starter.server.strategy.router import get_strategy_manager

    # Set up agent_manager for the app
    mock_agent_manager = AgentManager.__new__(AgentManager)
    mock_agent_manager._client = MagicMock()  # noqa: SLF001
    mock_agent_manager._cache = {}  # noqa: SLF001
    mock_agent_manager.letta_base_url = "http://localhost:8283"
    app.state.agent_manager = mock_agent_manager

    # Override the dependency to return our mock
    app.dependency_overrides[get_strategy_manager] = lambda: mock_strategy_manager

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()
