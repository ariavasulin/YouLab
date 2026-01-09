"""Tests for background agent runner."""

from datetime import datetime

import pytest

from letta_starter.background.runner import BackgroundAgentRunner, RunResult
from letta_starter.curriculum.schema import (
    BackgroundAgentConfig,
    DialecticQuery,
    MergeStrategy,
    SessionScope,
    Triggers,
)
from letta_starter.honcho.client import DialecticResponse


class MockAgent:
    """Mock Letta agent for testing."""

    def __init__(self, agent_id: str, name: str):
        self.id = agent_id
        self.name = name


class MockLettaClient:
    """Mock Letta client for testing."""

    def __init__(self, agents: list[MockAgent] | None = None):
        self.agents = agents or []
        self.agent_memory: dict[str, dict[str, str]] = {}
        self.archival_entries: list[dict[str, str]] = []

    def list_agents(self) -> list[MockAgent]:
        return self.agents

    def get_agent_memory(self, agent_id: str) -> dict[str, str]:
        return self.agent_memory.get(agent_id, {"persona": "", "human": ""})

    def update_agent_core_memory(self, agent_id: str, **kwargs) -> None:
        if agent_id not in self.agent_memory:
            self.agent_memory[agent_id] = {"persona": "", "human": ""}
        if "persona" in kwargs:
            self.agent_memory[agent_id]["persona"] = kwargs["persona"]
        if "human" in kwargs:
            self.agent_memory[agent_id]["human"] = kwargs["human"]

    def insert_archival_memory(self, agent_id: str, memory: str) -> None:
        self.archival_entries.append({"agent_id": agent_id, "memory": memory})


class MockHonchoClient:
    """Mock Honcho client for testing."""

    def __init__(self, insight: str = "Test insight from Honcho"):
        self.insight = insight
        self.queries: list[dict[str, object]] = []

    async def query_dialectic(
        self,
        user_id: str,
        question: str,
        session_scope: SessionScope = SessionScope.ALL,
        session_id: str | None = None,
        recent_limit: int = 5,
    ) -> DialecticResponse | None:
        self.queries.append(
            {
                "user_id": user_id,
                "question": question,
                "session_scope": session_scope,
            }
        )
        return DialecticResponse(
            insight=self.insight,
            session_scope=session_scope,
            query=question,
        )


@pytest.fixture
def mock_letta_client():
    """Create a mock Letta client with test agents."""
    return MockLettaClient(
        agents=[
            MockAgent("agent-1", "youlab_user1_tutor"),
            MockAgent("agent-2", "youlab_user2_tutor"),
        ]
    )


@pytest.fixture
def mock_honcho_client():
    """Create a mock Honcho client."""
    return MockHonchoClient()


@pytest.fixture
def runner(mock_letta_client, mock_honcho_client):
    """Create a BackgroundAgentRunner with mock clients."""
    return BackgroundAgentRunner(mock_letta_client, mock_honcho_client)


@pytest.fixture
def sample_config():
    """Create a sample background agent config."""
    return BackgroundAgentConfig(
        enabled=True,
        triggers=Triggers(manual=True),
        agent_types=["tutor"],
        batch_size=10,
        queries=[
            DialecticQuery(
                id="learning_style",
                question="What is the learning style?",
                target_block="human",
                target_field="context_notes",
                merge_strategy=MergeStrategy.APPEND,
            ),
        ],
    )


# Default agent_id for testing (config no longer has id field)
TEST_AGENT_ID = "test-harvester"


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_run_result_defaults(self):
        """Test RunResult default values."""
        result = RunResult(
            agent_id="test",
            started_at=datetime.now(),
        )
        assert result.completed_at is None
        assert result.users_processed == 0
        assert result.queries_executed == 0
        assert result.enrichments_applied == 0
        assert result.errors == []


class TestBackgroundAgentRunner:
    """Tests for BackgroundAgentRunner."""

    @pytest.mark.asyncio
    async def test_run_disabled_agent(self, runner, sample_config):
        """Test running a disabled agent returns early."""
        sample_config.enabled = False

        result = await runner.run_agent(sample_config, agent_id=TEST_AGENT_ID)

        assert result.agent_id == TEST_AGENT_ID
        assert "disabled" in result.errors[0].lower()
        assert result.users_processed == 0

    @pytest.mark.asyncio
    async def test_run_without_honcho(self, mock_letta_client, sample_config):
        """Test running without Honcho client returns early."""
        runner = BackgroundAgentRunner(mock_letta_client, None)

        result = await runner.run_agent(sample_config, agent_id=TEST_AGENT_ID)

        assert "Honcho" in result.errors[0]
        assert result.users_processed == 0

    @pytest.mark.asyncio
    async def test_run_processes_users(self, runner, sample_config, mock_honcho_client):
        """Test running agent processes all users."""
        result = await runner.run_agent(sample_config, agent_id=TEST_AGENT_ID)

        assert result.users_processed == 2
        assert result.queries_executed == 2  # 1 query * 2 users
        assert len(mock_honcho_client.queries) == 2

    @pytest.mark.asyncio
    async def test_run_applies_enrichments(self, runner, sample_config, mock_letta_client):
        """Test running agent applies enrichments."""
        result = await runner.run_agent(sample_config, agent_id=TEST_AGENT_ID)

        assert result.enrichments_applied == 2
        # Check that memory was updated
        assert len(mock_letta_client.archival_entries) == 2

    @pytest.mark.asyncio
    async def test_run_with_specific_users(self, runner, sample_config):
        """Test running agent for specific users."""
        result = await runner.run_agent(sample_config, user_ids=["user1"], agent_id=TEST_AGENT_ID)

        assert result.users_processed == 1
        assert result.queries_executed == 1

    @pytest.mark.asyncio
    async def test_run_handles_missing_agent(self, runner, sample_config):
        """Test handling when agent for user is not found."""
        # Run for user that doesn't have an agent
        result = await runner.run_agent(
            sample_config, user_ids=["unknown_user"], agent_id=TEST_AGENT_ID
        )

        assert result.users_processed == 1
        assert result.enrichments_applied == 0
        assert any("No agent found" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_handles_dialectic_failure(self, mock_letta_client, sample_config):
        """Test handling dialectic query failure."""

        class FailingHonchoClient:
            async def query_dialectic(self, **kwargs) -> None:
                return None

        runner = BackgroundAgentRunner(mock_letta_client, FailingHonchoClient())

        result = await runner.run_agent(sample_config, user_ids=["user1"], agent_id=TEST_AGENT_ID)

        assert result.queries_executed == 1
        assert result.enrichments_applied == 0
        assert any("Dialectic query failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_run_multiple_queries(self, runner, mock_honcho_client):
        """Test running agent with multiple queries."""
        config = BackgroundAgentConfig(
            queries=[
                DialecticQuery(
                    id="q1",
                    question="Question 1?",
                    target_block="human",
                    target_field="facts",
                ),
                DialecticQuery(
                    id="q2",
                    question="Question 2?",
                    target_block="persona",
                    target_field="constraints",
                ),
            ],
        )

        result = await runner.run_agent(config, user_ids=["user1"], agent_id="multi-query")

        assert result.queries_executed == 2
        assert len(mock_honcho_client.queries) == 2

    @pytest.mark.asyncio
    async def test_run_respects_batch_size(self, runner, mock_letta_client):
        """Test that runner respects batch size."""
        # Add more agents
        mock_letta_client.agents = [
            MockAgent(f"agent-{i}", f"youlab_user{i}_tutor") for i in range(5)
        ]

        config = BackgroundAgentConfig(
            batch_size=2,
            queries=[
                DialecticQuery(
                    id="q1",
                    question="Test?",
                    target_block="human",
                    target_field="facts",
                )
            ],
        )

        result = await runner.run_agent(config, agent_id="batched")

        # Should process all 5 users in batches of 2
        assert result.users_processed == 5

    @pytest.mark.asyncio
    async def test_run_records_timing(self, runner, sample_config):
        """Test that run records timing information."""
        result = await runner.run_agent(sample_config, user_ids=["user1"], agent_id=TEST_AGENT_ID)

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at


class TestGetTargetUsers:
    """Tests for _get_target_users method."""

    @pytest.mark.asyncio
    async def test_get_target_users_from_agents(self, runner, sample_config):
        """Test extracting users from agent names."""
        users = await runner._get_target_users(sample_config)

        assert "user1" in users
        assert "user2" in users

    @pytest.mark.asyncio
    async def test_get_target_users_no_duplicates(self, runner, mock_letta_client):
        """Test that duplicate users are not returned."""
        # Add duplicate agent for same user
        mock_letta_client.agents.append(MockAgent("agent-3", "youlab_user1_assistant"))

        config = BackgroundAgentConfig(
            agent_types=["tutor", "assistant"],
        )

        users = await runner._get_target_users(config)

        assert users.count("user1") == 1


class TestGetAgentId:
    """Tests for _get_agent_id method."""

    def test_get_agent_id_found(self, runner):
        """Test finding agent ID for user."""
        agent_id = runner._get_agent_id("user1", "tutor")
        assert agent_id == "agent-1"

    def test_get_agent_id_not_found(self, runner):
        """Test agent ID not found."""
        agent_id = runner._get_agent_id("nonexistent", "tutor")
        assert agent_id is None
