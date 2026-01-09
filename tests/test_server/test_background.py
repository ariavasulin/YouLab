"""Tests for background agent HTTP endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from letta_starter.background.runner import RunResult
from letta_starter.curriculum.schema import (
    BackgroundAgentConfig,
    CourseConfig,
    DialecticQuery,
    Triggers,
)


@pytest.fixture
def sample_background_configs():
    """Create sample background agent configs for testing."""
    return {
        "test-harvester": BackgroundAgentConfig(
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
        "disabled-agent": BackgroundAgentConfig(
            enabled=False,
        ),
    }


@pytest.fixture
def sample_course_config(sample_background_configs):
    """Create a sample course config for testing."""
    return CourseConfig(
        id="test-course",
        name="Test Course",
        background=sample_background_configs,
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
def mock_curriculum(sample_course_config):
    """Create a mock curriculum registry."""
    mock = MagicMock()
    mock.list_courses.return_value = ["test-course"]
    mock.get.return_value = sample_course_config
    mock.reload.return_value = 1
    return mock


@pytest.fixture
def background_test_client(mock_agent_manager, mock_background_runner, mock_curriculum):
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
    bg_module._runner = mock_background_runner
    bg_module._initialized = True

    # Patch curriculum at module level
    with patch.object(bg_module, "curriculum", mock_curriculum):
        yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()
    bg_module._runner = None
    bg_module._initialized = False


class TestListBackgroundAgents:
    """Tests for GET /background/agents endpoint."""

    def test_list_agents_returns_configured_agents(
        self, mock_agent_manager, mock_background_runner, mock_curriculum
    ):
        """Test listing all configured background agents."""
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

        bg_module._runner = mock_background_runner
        bg_module._initialized = True

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.get("/background/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 2

        # Check first agent
        harvester = next(a for a in agents if a["id"] == "test-harvester")
        assert harvester["name"] == "test-harvester"  # name now comes from dict key
        assert harvester["course_id"] == "test-course"
        assert harvester["enabled"] is True
        assert harvester["triggers"]["schedule"] == "0 3 * * *"
        assert harvester["triggers"]["manual"] is True
        assert harvester["query_count"] == 1

        # Check disabled agent
        disabled = next(a for a in agents if a["id"] == "disabled-agent")
        assert disabled["enabled"] is False

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False

    def test_list_agents_empty_when_no_courses(self, mock_agent_manager):
        """Test listing agents when no courses loaded."""
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

        bg_module._runner = MagicMock()
        bg_module._initialized = True

        mock_curriculum = MagicMock()
        mock_curriculum.list_courses.return_value = []

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.get("/background/agents")

        assert response.status_code == 200
        assert response.json() == []

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False


class TestRunBackgroundAgent:
    """Tests for POST /background/{agent_id}/run endpoint."""

    def test_run_agent_success(self, mock_agent_manager, mock_background_runner, mock_curriculum):
        """Test running a background agent successfully."""
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

        bg_module._runner = mock_background_runner
        bg_module._initialized = True

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.post("/background/test-harvester/run")

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

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False

    def test_run_agent_with_user_filter(
        self, mock_agent_manager, mock_background_runner, mock_curriculum
    ):
        """Test running agent with specific users."""
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

        bg_module._runner = mock_background_runner
        bg_module._initialized = True

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.post(
                "/background/test-harvester/run",
                json={"user_ids": ["user1", "user2"]},
            )

        assert response.status_code == 200

        # run_agent is called as (config, user_ids, agent_id=) - check kwargs
        call_args = mock_background_runner.run_agent.call_args
        assert call_args[0][1] == ["user1", "user2"]  # user_ids is second positional arg
        assert call_args[1]["agent_id"] == "test-harvester"

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False

    def test_run_agent_not_found(self, mock_agent_manager, mock_background_runner):
        """Test running non-existent agent returns 404."""
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

        bg_module._runner = mock_background_runner
        bg_module._initialized = True

        # Mock curriculum with empty background
        mock_curriculum = MagicMock()
        mock_curriculum.list_courses.return_value = ["test-course"]
        mock_course = MagicMock()
        mock_course.background = {}
        mock_curriculum.get.return_value = mock_course

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.post("/background/nonexistent/run")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False

    def test_run_agent_runner_not_initialized(self, mock_agent_manager):
        """Test running agent when runner not initialized returns 503."""
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

        bg_module._runner = None  # Not initialized
        bg_module._initialized = False

        client = TestClient(app)
        response = client.post("/background/test-harvester/run")

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"].lower()

        app.dependency_overrides.clear()


class TestReloadConfig:
    """Tests for POST /background/config/reload endpoint."""

    def test_reload_config_success(self, mock_agent_manager, mock_background_runner):
        """Test reloading config successfully."""
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

        bg_module._runner = mock_background_runner
        bg_module._initialized = True

        mock_curriculum = MagicMock()
        mock_curriculum.reload.return_value = 2
        mock_curriculum.list_courses.return_value = ["course1", "course2"]

        with patch.object(bg_module, "curriculum", mock_curriculum):
            client = TestClient(app)
            response = client.post("/background/config/reload")

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["courses_loaded"] == 2
        assert "course1" in result["course_ids"]
        assert "course2" in result["course_ids"]

        mock_curriculum.reload.assert_called_once()

        app.dependency_overrides.clear()
        bg_module._runner = None
        bg_module._initialized = False


class TestInitializeBackground:
    """Tests for initialize_background function."""

    def test_initialize_creates_runner(self, tmp_path):
        """Test that initialize_background creates runner."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.background import initialize_background

        mock_letta = MagicMock()
        mock_honcho = MagicMock()

        initialize_background(mock_letta, mock_honcho, tmp_path)

        assert bg_module._runner is not None
        assert bg_module._initialized is True

        # Cleanup
        bg_module._runner = None
        bg_module._initialized = False

    def test_initialize_without_honcho(self, tmp_path):
        """Test initialization without Honcho client."""
        from letta_starter.server import background as bg_module
        from letta_starter.server.background import initialize_background

        mock_letta = MagicMock()

        initialize_background(mock_letta, None, tmp_path)

        assert bg_module._runner is not None
        assert bg_module._initialized is True

        # Cleanup
        bg_module._runner = None
        bg_module._initialized = False
