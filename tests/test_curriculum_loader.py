"""Tests for curriculum loader and v2 schema parsing."""

from letta_starter.curriculum.loader import CurriculumLoader
from letta_starter.curriculum.schema import (
    MergeStrategy,
    SessionScope,
    ToolRuleType,
)


class TestV2SchemaLoading:
    """Tests for loading v2 schema configs."""

    def test_load_college_essay_v2_config(self):
        """Test that the college-essay v2 config loads correctly."""
        loader = CurriculumLoader()
        course = loader.load_course("college-essay")

        # Verify agent config
        assert course.id == "college-essay"
        assert course.name == "College Essay Coaching"
        assert course.version == "1.0.0"
        assert course.agent.model == "anthropic/claude-sonnet-4-20250514"
        assert len(course.agent.modules) == 3

        # Verify tools with default rules from registry
        assert len(course.agent.tools) == 3
        tool_ids = [t.id for t in course.agent.tools]
        assert "send_message" in tool_ids
        assert "query_honcho" in tool_ids
        assert "edit_memory_block" in tool_ids

        # Verify tool rules are applied from registry
        send_msg_tool = next(t for t in course.agent.tools if t.id == "send_message")
        assert send_msg_tool.rules.type == ToolRuleType.EXIT_LOOP

    def test_load_v2_blocks(self):
        """Test that v2 block schema with field.* syntax loads correctly."""
        loader = CurriculumLoader()
        course = loader.load_course("college-essay")

        # Verify blocks loaded
        assert "persona" in course.blocks
        assert "human" in course.blocks

        # Check persona block
        persona = course.blocks["persona"]
        assert persona.label == "persona"
        assert persona.shared is False
        assert "name" in persona.fields
        assert persona.fields["name"].default == "YouLab Essay Coach"
        assert persona.fields["tone"].options == ["warm", "professional", "friendly", "formal"]

        # Check human block
        human = course.blocks["human"]
        assert human.label == "human"
        assert human.shared is False
        assert human.fields["facts"].max == 20

    def test_load_v2_tasks(self):
        """Test that v2 [[task]] array loads correctly."""
        loader = CurriculumLoader()
        course = loader.load_course("college-essay")

        # Verify tasks loaded
        assert len(course.tasks) == 1

        task = course.tasks[0]
        assert task.schedule == "0 3 * * *"
        assert task.manual is True
        assert task.agent_types == ["tutor", "college-essay"]
        assert task.batch_size == 50

        # Verify queries
        assert len(task.queries) == 3

        # Check first query
        q1 = task.queries[0]
        assert q1.target == "human.context_notes"
        assert q1.target_block == "human"
        assert q1.target_field == "context_notes"
        assert q1.scope == SessionScope.ALL
        assert q1.merge == MergeStrategy.APPEND

        # Check second query with recent scope
        q2 = task.queries[1]
        assert q2.scope == SessionScope.RECENT
        assert q2.recent_limit == 5

        # Check third query with llm_diff merge
        q3 = task.queries[2]
        assert q3.merge == MergeStrategy.LLM_DIFF


class TestV1Compatibility:
    """Tests for v1 schema backwards compatibility."""

    def test_v1_course_agent_separate_loads(self, tmp_path):
        """Test that v1 [course] + [agent] format still loads."""
        config_dir = tmp_path / "courses" / "v1-test"
        config_dir.mkdir(parents=True)

        v1_config = """
[course]
id = "v1-test"
name = "V1 Test Course"
version = "0.9.0"
modules = []

[agent]
model = "anthropic/claude-sonnet-4-20250514"
system = "Test system prompt"

[[agent.tools]]
id = "send_message"
rules = { type = "exit_loop" }

[blocks.persona]
label = "persona"
[blocks.persona.fields]
name = { type = "string", default = "Test Agent" }

[messages]
welcome_first = "Hello!"
"""
        (config_dir / "course.toml").write_text(v1_config)

        loader = CurriculumLoader(tmp_path / "courses")
        course = loader.load_course("v1-test")

        assert course.id == "v1-test"
        assert course.name == "V1 Test Course"
        assert course.version == "0.9.0"
        assert course.agent.system == "Test system prompt"
        assert len(course.agent.tools) == 1
        assert "persona" in course.blocks
        assert course.blocks["persona"].fields["name"].default == "Test Agent"

    def test_v1_blocks_format_loads(self, tmp_path):
        """Test that v1 [blocks.x.fields] format loads."""
        config_dir = tmp_path / "courses" / "v1-blocks"
        config_dir.mkdir(parents=True)

        v1_config = """
[agent]
id = "v1-blocks"
name = "V1 Blocks Test"

[blocks.human]
label = "human"
[blocks.human.fields]
name = { type = "string", default = "" }
facts = { type = "list", default = [], max = 10 }
"""
        (config_dir / "course.toml").write_text(v1_config)

        loader = CurriculumLoader(tmp_path / "courses")
        course = loader.load_course("v1-blocks")

        assert "human" in course.blocks
        human = course.blocks["human"]
        assert human.label == "human"
        assert "name" in human.fields
        assert human.fields["facts"].max == 10


class TestCurriculumLoaderMethods:
    """Tests for CurriculumLoader utility methods."""

    def test_list_courses(self):
        """Test listing available courses."""
        loader = CurriculumLoader()
        courses = loader.list_courses()

        assert "college-essay" in courses

    def test_get_nonexistent_course(self):
        """Test getting a course that doesn't exist."""
        loader = CurriculumLoader()
        result = loader.get("nonexistent-course")

        assert result is None

    def test_cache_hit(self):
        """Test that subsequent loads hit the cache."""
        loader = CurriculumLoader()

        # First load
        course1 = loader.load_course("college-essay")

        # Second load - should be cached
        course2 = loader.load_course("college-essay")

        assert course1 is course2

    def test_force_reload(self):
        """Test that force=True bypasses cache."""
        loader = CurriculumLoader()

        # First load
        course1 = loader.load_course("college-essay")

        # Force reload
        course2 = loader.load_course("college-essay", force=True)

        # Should be different instances
        assert course1 is not course2
        # But same content
        assert course1.id == course2.id
