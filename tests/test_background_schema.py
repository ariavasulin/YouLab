"""Tests for background agent TOML schema."""

from pathlib import Path

import pytest

from letta_starter.background.schema import (
    BackgroundAgentConfig,
    CourseConfig,
    DialecticQuery,
    IdleTrigger,
    MergeStrategy,
    SessionScope,
    Triggers,
    load_all_course_configs,
    load_course_config,
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
        """Test BackgroundAgentConfig with minimal fields."""
        config = BackgroundAgentConfig(id="test-agent", name="Test Agent")
        assert config.id == "test-agent"
        assert config.name == "Test Agent"
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
            id="harvester",
            name="Harvester",
            queries=[query],
        )
        assert len(config.queries) == 1
        assert config.queries[0].id == "q1"


class TestCourseConfig:
    """Tests for CourseConfig model."""

    def test_minimal_config(self):
        """Test CourseConfig with minimal fields."""
        config = CourseConfig(id="test-course", name="Test Course")
        assert config.id == "test-course"
        assert config.name == "Test Course"
        assert config.background_agents == []

    def test_with_agents(self):
        """Test CourseConfig with background agents."""
        agent = BackgroundAgentConfig(id="agent1", name="Agent 1")
        config = CourseConfig(
            id="course1",
            name="Course 1",
            background_agents=[agent],
        )
        assert len(config.background_agents) == 1


class TestLoadCourseConfig:
    """Tests for TOML loading functions."""

    def test_load_valid_toml(self, tmp_path):
        """Test loading a valid TOML file."""
        toml_content = """
id = "test-course"
name = "Test Course"

[[background_agents]]
id = "test-agent"
name = "Test Agent"
enabled = true

[[background_agents.queries]]
id = "q1"
question = "What is the learning style?"
target_block = "human"
target_field = "context_notes"
"""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(toml_content)

        config = load_course_config(toml_file)

        assert config.id == "test-course"
        assert config.name == "Test Course"
        assert len(config.background_agents) == 1
        assert config.background_agents[0].id == "test-agent"
        assert len(config.background_agents[0].queries) == 1

    def test_load_minimal_toml(self, tmp_path):
        """Test loading minimal TOML file."""
        toml_content = """
id = "minimal"
name = "Minimal Course"
"""
        toml_file = tmp_path / "minimal.toml"
        toml_file.write_text(toml_content)

        config = load_course_config(toml_file)
        assert config.id == "minimal"
        assert config.background_agents == []

    def test_load_missing_file(self, tmp_path):
        """Test loading non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_course_config(tmp_path / "nonexistent.toml")

    def test_load_all_configs(self, tmp_path):
        """Test loading all configs from directory."""
        # Create two TOML files
        (tmp_path / "course1.toml").write_text('id = "course1"\nname = "Course 1"')
        (tmp_path / "course2.toml").write_text('id = "course2"\nname = "Course 2"')

        configs = load_all_course_configs(tmp_path)

        assert len(configs) == 2
        assert "course1" in configs
        assert "course2" in configs

    def test_load_all_configs_empty_dir(self, tmp_path):
        """Test loading from empty directory."""
        configs = load_all_course_configs(tmp_path)
        assert configs == {}

    def test_load_all_configs_nonexistent_dir(self, tmp_path):
        """Test loading from non-existent directory."""
        configs = load_all_course_configs(tmp_path / "nonexistent")
        assert configs == {}

    def test_load_all_configs_skips_invalid(self, tmp_path):
        """Test that invalid TOML files are skipped."""
        # Valid file
        (tmp_path / "valid.toml").write_text('id = "valid"\nname = "Valid"')
        # Invalid file (missing required fields)
        (tmp_path / "invalid.toml").write_text("not_valid = true")

        configs = load_all_course_configs(tmp_path)

        assert len(configs) == 1
        assert "valid" in configs


class TestCollegeEssayConfig:
    """Tests for the actual college-essay.toml config."""

    def test_load_college_essay_config(self):
        """Test loading the example college-essay.toml."""
        config_path = Path("config/courses/college-essay.toml")

        if not config_path.exists():
            pytest.skip("college-essay.toml not found")

        config = load_course_config(config_path)

        assert config.id == "college-essay"
        assert config.name == "College Essay Coaching"
        assert len(config.background_agents) == 1

        agent = config.background_agents[0]
        assert agent.id == "insight-harvester"
        assert agent.enabled is True
        assert len(agent.queries) == 3

        # Verify query structure
        query_ids = [q.id for q in agent.queries]
        assert "learning_style" in query_ids
        assert "engagement_patterns" in query_ids
        assert "communication_style" in query_ids
