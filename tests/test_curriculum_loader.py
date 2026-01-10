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
        assert course.version == "2.0.0"
        assert course.agent.model == "openai/gpt-4o"
        assert len(course.agent.modules) == 3

        # Verify tools with default rules from registry
        assert len(course.agent.tools) == 4
        tool_ids = [t.id for t in course.agent.tools]
        assert "send_message" in tool_ids
        assert "query_honcho" in tool_ids
        assert "edit_memory_block" in tool_ids
        assert "advance_lesson" in tool_ids

        # Verify tool rules are applied from registry
        send_msg_tool = next(t for t in course.agent.tools if t.id == "send_message")
        assert send_msg_tool.rules.type == ToolRuleType.EXIT_LOOP

    def test_load_v2_blocks(self):
        """Test that v2 block schema with field.* syntax loads correctly."""
        loader = CurriculumLoader()
        course = loader.load_course("college-essay")

        # Verify blocks loaded
        assert "student" in course.blocks
        assert "engagement_strategy" in course.blocks
        assert "journey" in course.blocks

        # Check student block (maps to human label)
        student = course.blocks["student"]
        assert student.label == "human"
        assert student.shared is False
        assert "profile" in student.fields
        assert "insights" in student.fields

        # Check engagement_strategy block (maps to persona label)
        engagement = course.blocks["engagement_strategy"]
        assert engagement.label == "persona"
        assert engagement.shared is False
        assert "approach" in engagement.fields

        # Check journey block
        journey = course.blocks["journey"]
        assert journey.label == "journey"
        assert journey.shared is False
        assert "module_id" in journey.fields
        assert "lesson_id" in journey.fields
        assert journey.fields["milestones"].max == 30

    def test_load_v2_tasks(self):
        """Test that v2 [[task]] array loads correctly."""
        loader = CurriculumLoader()
        course = loader.load_course("college-essay")

        # Verify tasks loaded
        assert len(course.tasks) == 1

        task = course.tasks[0]
        # New task uses on_idle instead of schedule
        assert task.on_idle is True
        assert task.idle_threshold_minutes == 5
        assert task.manual is True
        assert task.agent_types == ["tutor", "college-essay"]
        assert task.batch_size == 50

        # Verify queries - now 4 queries for the grader
        assert len(task.queries) == 4

        # Check first query - journey.grader_notes
        q1 = task.queries[0]
        assert q1.target == "journey.grader_notes"
        assert q1.target_block == "journey"
        assert q1.target_field == "grader_notes"
        assert q1.scope == SessionScope.ALL
        assert q1.merge == MergeStrategy.REPLACE

        # Check second query - journey.blockers
        q2 = task.queries[1]
        assert q2.target == "journey.blockers"
        assert q2.merge == MergeStrategy.REPLACE

        # Check third query - student.insights with append
        q3 = task.queries[2]
        assert q3.target == "student.insights"
        assert q3.merge == MergeStrategy.APPEND

        # Check fourth query - engagement_strategy.approach with llm_diff
        q4 = task.queries[3]
        assert q4.target == "engagement_strategy.approach"
        assert q4.merge == MergeStrategy.LLM_DIFF


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
