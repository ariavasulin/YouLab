"""Tests for background agent HTTP endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from letta_starter.background.runner import RunResult
from letta_starter.background.schema import (
    BackgroundAgentConfig,
    CourseConfig,
    DialecticQuery,
    Triggers,
)


@pytest.fixture
def sample_course_config():
    """Create a sample course config for testing."""
    return CourseConfig(
        id="test-course",
        name="Test Course",
        background_agents=[
            BackgroundAgentConfig(
                id="test-harvester",
                name="Test Harvester",
                enabled=True,
                triggers=Triggers(schedule="0 3 * * *", manual=True),
                queries=[
                    DialecticQuery(
                        id="q1",
                        question="Test question?",
                        target_block="human",
                        target_field="facts",
                    )
                ],
            ),
            BackgroundAgentConfig(
                id="disabled-agent",
                name="Disabled Agent",
                enabled=False,
            ),
        ],
    )


@pytest.fixture
def mock_background_runner():
    """Create a mock BackgroundAgentRunner."""
    runner = MagicMock()
    now = datetime.now()
    runner.run_agent = AsyncMock(
        return_value=RunResult(
            agent_id="test-harvester",
            started_at=now,
            completed_at=now,
            users_processed=5,
            queries_executed=5,
            enrichments_applied=4,
            errors=["One error"],
        )
    )
    return runner


@pytest.fixture
def background_test_client(mock_agent_manager, sample_course_config, mock_background_runner):
    """Test client with background system initialized."""
    from letta_starter.server import background as bg_module
    from letta_starter.server.main import app
    from letta_starter.server.strategy import StrategyManager
    from letta_starter.server.strategy.router import get_strategy_manager

    # Set up agent manager
    app.state.agent_manager = mock_agent_manager
    app.state.honcho_client = None

    # Set up mock strategy manager
    mock_strategy = StrategyManager.__new__(StrategyManager)
    mock_strategy._client = MagicMock()
    mock_strategy._agent_id = "strategy-agent-id"
    mock_strategy.letta_base_url = "http://localhost:8283"
    app.dependency_overrides[get_strategy_manager] = lambda: mock_strategy

    # Initialize background module state
    bg_module._configs = {"test-course": sample_course_config}
    bg_module._runner = mock_background_runner

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()
    bg_module._configs = {}
    bg_module._runner = None


class TestListBackgroundAgents:
    """Tests for GET /background/agents endpoint."""

    def test_list_agents_returns_configured_agents(self, background_test_client):
        """Test listing all configured background agents."""
        response = background_test_client.get("/background/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 2

        # Check first agent
        harvester = next(a for a in agents if a["id"] == "test-harvester")
        assert harvester["name"] == "Test Harvester"
        assert harvester["course_id"] == "test-course"
        assert harvester["enabled"] is True
        assert harvester["triggers"]["schedule"] == "0 3 * * *"
        assert harvester["triggers"]["manual"] is True
        assert harvester["query_count"] == 1

        # Check disabled agent
        disabled = next(a for a in agents if a["id"] == "disabled-agent")
        assert disabled["enabled"] is False

    def test_list_agents_empty_when_no_config(self, mock_agent_manager):
        """Test listing agents when no configs loaded."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.main import app
        from letta_starter.server.strategy import StrategyManager
        from letta_starter.server.strategy.router import get_strategy_manager

        app.state.agent_manager = mock_agent_manager

        mock_strategy = StrategyManager.__new__(StrategyManager)
        mock_strategy._client = MagicMock()
        mock_strategy._agent_id = "strategy-agent-id"
        mock_strategy.letta_base_url = "http://localhost:8283"
        app.dependency_overrides[get_strategy_manager] = lambda: mock_strategy

        bg_module._configs = {}
        bg_module._runner = MagicMock()

        client = TestClient(app)
        response = client.get("/background/agents")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()


class TestRunBackgroundAgent:
    """Tests for POST /background/{agent_id}/run endpoint."""

    def test_run_agent_success(self, background_test_client, mock_background_runner):
        """Test running a background agent successfully."""
        response = background_test_client.post("/background/test-harvester/run")

        assert response.status_code == 200
        result = response.json()
        assert result["agent_id"] == "test-harvester"
        assert result["users_processed"] == 5
        assert result["queries_executed"] == 5
        assert result["enrichments_applied"] == 4
        assert result["error_count"] == 1
        assert result["errors"] == ["One error"]
        assert result["started_at"] is not None
        assert result["completed_at"] is not None

        mock_background_runner.run_agent.assert_called_once()

    def test_run_agent_with_user_filter(self, background_test_client, mock_background_runner):
        """Test running agent with specific users."""
        response = background_test_client.post(
            "/background/test-harvester/run",
            json={"user_ids": ["user1", "user2"]},
        )

        assert response.status_code == 200

        # run_agent is called as (config, user_ids) - positional args
        call_args = mock_background_runner.run_agent.call_args
        assert call_args[0][1] == ["user1", "user2"]  # user_ids is second positional arg

    def test_run_agent_not_found(self, background_test_client):
        """Test running non-existent agent returns 404."""
        response = background_test_client.post("/background/nonexistent/run")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_run_agent_runner_not_initialized(self, mock_agent_manager):
        """Test running agent when runner not initialized returns 500."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.main import app
        from letta_starter.server.strategy import StrategyManager
        from letta_starter.server.strategy.router import get_strategy_manager

        app.state.agent_manager = mock_agent_manager

        mock_strategy = StrategyManager.__new__(StrategyManager)
        mock_strategy._client = MagicMock()
        mock_strategy._agent_id = "strategy-agent-id"
        mock_strategy.letta_base_url = "http://localhost:8283"
        app.dependency_overrides[get_strategy_manager] = lambda: mock_strategy

        bg_module._configs = {}
        bg_module._runner = None  # Not initialized

        client = TestClient(app)
        response = client.post("/background/test-harvester/run")

        assert response.status_code == 500
        assert "not initialized" in response.json()["detail"].lower()

        app.dependency_overrides.clear()


class TestReloadConfig:
    """Tests for POST /background/config/reload endpoint."""

    def test_reload_config_success(self, background_test_client, tmp_path):
        """Test reloading config successfully."""
        # Create temp config file
        config_dir = tmp_path / "courses"
        config_dir.mkdir()
        (config_dir / "test.toml").write_text('id = "reloaded"\nname = "Reloaded Course"')

        response = background_test_client.post(
            "/background/config/reload",
            params={"config_dir": str(config_dir)},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["courses_loaded"] == 1
        assert "reloaded" in result["course_ids"]

    def test_reload_config_empty_dir(self, background_test_client, tmp_path):
        """Test reloading from empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        response = background_test_client.post(
            "/background/config/reload",
            params={"config_dir": str(empty_dir)},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["courses_loaded"] == 0

    def test_reload_config_default_path(self, background_test_client):
        """Test reloading with default path."""
        response = background_test_client.post("/background/config/reload")

        assert response.status_code == 200
        result = response.json()
        # May or may not have configs depending on whether config/courses exists
        assert "success" in result


class TestInitializeBackground:
    """Tests for initialize_background function."""

    def test_initialize_loads_configs(self, tmp_path):
        """Test that initialize_background loads course configs."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.background import initialize_background

        # Create temp config
        config_dir = tmp_path / "courses"
        config_dir.mkdir()
        (config_dir / "test.toml").write_text('id = "init-test"\nname = "Init Test"')

        mock_letta = MagicMock()
        mock_honcho = MagicMock()

        initialize_background(mock_letta, mock_honcho, config_dir)

        assert bg_module._runner is not None
        assert "init-test" in bg_module._configs

        # Cleanup
        bg_module._configs = {}
        bg_module._runner = None

    def test_initialize_with_no_configs(self, tmp_path):
        """Test initialization with empty config directory."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.background import initialize_background

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        mock_letta = MagicMock()

        initialize_background(mock_letta, None, empty_dir)

        assert bg_module._runner is not None
        assert bg_module._configs == {}

        # Cleanup
        bg_module._configs = {}
        bg_module._runner = None
