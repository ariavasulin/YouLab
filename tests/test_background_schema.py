"""Tests for background agent schema (now in curriculum.schema)."""

from letta_starter.curriculum.schema import (
    BackgroundAgentConfig,
    DialecticQuery,
    IdleTrigger,
    MergeStrategy,
    SessionScope,
    Triggers,
)


class TestSessionScope:
    """Tests for SessionScope enum."""

    def test_session_scope_values(self):
        """Test SessionScope enum values."""
        assert SessionScope.ALL.value == "all"
        assert SessionScope.RECENT.value == "recent"
        assert SessionScope.CURRENT.value == "current"
        assert SessionScope.SPECIFIC.value == "specific"


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_merge_strategy_values(self):
        """Test MergeStrategy enum values."""
        assert MergeStrategy.APPEND.value == "append"
        assert MergeStrategy.REPLACE.value == "replace"
        assert MergeStrategy.LLM_DIFF.value == "llm_diff"


class TestIdleTrigger:
    """Tests for IdleTrigger model."""

    def test_default_values(self):
        """Test IdleTrigger default values."""
        trigger = IdleTrigger()
        assert trigger.enabled is False
        assert trigger.threshold_minutes == 30
        assert trigger.cooldown_minutes == 60

    def test_custom_values(self):
        """Test IdleTrigger with custom values."""
        trigger = IdleTrigger(enabled=True, threshold_minutes=15, cooldown_minutes=120)
        assert trigger.enabled is True
        assert trigger.threshold_minutes == 15
        assert trigger.cooldown_minutes == 120


class TestTriggers:
    """Tests for Triggers model."""

    def test_default_values(self):
        """Test Triggers default values."""
        triggers = Triggers()
        assert triggers.schedule is None
        assert triggers.manual is True
        assert triggers.idle.enabled is False

    def test_with_schedule(self):
        """Test Triggers with cron schedule."""
        triggers = Triggers(schedule="0 3 * * *")
        assert triggers.schedule == "0 3 * * *"


class TestDialecticQuery:
    """Tests for DialecticQuery model."""

    def test_minimal_query(self):
        """Test DialecticQuery with minimal fields."""
        query = DialecticQuery(
            id="test_query",
            question="What is the student's learning style?",
            target_block="human",
            target_field="context_notes",
        )
        assert query.id == "test_query"
        assert query.session_scope == SessionScope.ALL
        assert query.merge_strategy == MergeStrategy.APPEND
        assert query.recent_limit == 5

    def test_full_query(self):
        """Test DialecticQuery with all fields."""
        query = DialecticQuery(
            id="engagement",
            question="How engaged is the student?",
            session_scope=SessionScope.RECENT,
            recent_limit=10,
            target_block="human",
            target_field="facts",
            merge_strategy=MergeStrategy.REPLACE,
        )
        assert query.session_scope == SessionScope.RECENT
        assert query.recent_limit == 10
        assert query.merge_strategy == MergeStrategy.REPLACE


class TestBackgroundAgentConfig:
    """Tests for BackgroundAgentConfig model."""

    def test_minimal_config(self):
        """Test BackgroundAgentConfig with minimal fields.

        Note: In curriculum schema, agent configs don't have id/name fields.
        The id comes from the dict key in course.background.
        """
        config = BackgroundAgentConfig()
        assert config.enabled is True
        assert config.agent_types == ["tutor"]
        assert config.user_filter == "all"
        assert config.batch_size == 50
        assert config.queries == []

    def test_with_queries(self):
        """Test BackgroundAgentConfig with queries."""
        query = DialecticQuery(
            id="q1",
            question="Test?",
            target_block="human",
            target_field="facts",
        )
        config = BackgroundAgentConfig(
            queries=[query],
        )
        assert len(config.queries) == 1
        assert config.queries[0].id == "q1"

    def test_disabled_config(self):
        """Test BackgroundAgentConfig when disabled."""
        config = BackgroundAgentConfig(enabled=False)
        assert config.enabled is False

    def test_custom_triggers(self):
        """Test BackgroundAgentConfig with custom triggers."""
        config = BackgroundAgentConfig(
            triggers=Triggers(schedule="0 */6 * * *", manual=False),
        )
        assert config.triggers.schedule == "0 */6 * * *"
        assert config.triggers.manual is False
