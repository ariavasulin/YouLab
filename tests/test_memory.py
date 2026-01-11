"""Tests for memory block management."""

import pytest

from youlab_server.memory.blocks import (
    HumanBlock,
    PersonaBlock,
    SessionState,
)
from youlab_server.memory.strategies import (
    AdaptiveRotation,
    AggressiveRotation,
    ContextMetrics,
    PreservativeRotation,
)


class TestPersonaBlock:
    """Tests for PersonaBlock."""

    def test_create_persona(self, sample_persona_data):
        """Test creating a persona block."""
        persona = PersonaBlock(**sample_persona_data)
        assert persona.name == "TestAgent"
        assert persona.role == "Test assistant"
        assert len(persona.capabilities) == 2

    def test_to_memory_string(self, sample_persona_data):
        """Test serializing persona to memory string."""
        persona = PersonaBlock(**sample_persona_data)
        memory_str = persona.to_memory_string()

        assert "[IDENTITY]" in memory_str
        assert "TestAgent" in memory_str
        assert "[CAPABILITIES]" in memory_str

    def test_memory_string_respects_max_chars(self, sample_persona_data):
        """Test that memory string respects max_chars limit."""
        persona = PersonaBlock(**sample_persona_data)
        memory_str = persona.to_memory_string(max_chars=50)

        assert len(memory_str) <= 50

    def test_from_memory_string_roundtrip(self, sample_persona_data):
        """Test parsing memory string back to PersonaBlock."""
        original = PersonaBlock(**sample_persona_data)
        memory_str = original.to_memory_string()
        parsed = PersonaBlock.from_memory_string(memory_str)

        assert parsed.name == original.name
        assert parsed.role == original.role


class TestHumanBlock:
    """Tests for HumanBlock."""

    def test_create_human(self, sample_human_data):
        """Test creating a human block."""
        human = HumanBlock(**sample_human_data)
        assert human.name == "TestUser"
        assert human.role == "Developer"

    def test_to_memory_string(self, sample_human_data):
        """Test serializing human to memory string."""
        human = HumanBlock(**sample_human_data)
        memory_str = human.to_memory_string()

        assert "[USER]" in memory_str
        assert "TestUser" in memory_str
        assert "[TASK]" in memory_str

    def test_add_context_note(self):
        """Test adding context notes."""
        human = HumanBlock()
        human.add_context_note("First note")
        human.add_context_note("Second note")

        assert len(human.context_notes) == 2
        assert "First note" in human.context_notes

    def test_context_note_rolling_window(self):
        """Test that context notes maintain rolling window."""
        human = HumanBlock()
        for i in range(15):
            human.add_context_note(f"Note {i}", max_notes=10)

        assert len(human.context_notes) == 10
        assert "Note 14" in human.context_notes
        assert "Note 0" not in human.context_notes

    def test_set_task(self):
        """Test setting a task."""
        human = HumanBlock()
        human.set_task("Test task")

        assert human.current_task == "Test task"
        assert human.session_state == SessionState.ACTIVE_TASK

    def test_clear_task(self):
        """Test clearing a task."""
        human = HumanBlock(current_task="Test task")
        human.clear_task()

        assert human.current_task is None
        assert human.session_state == SessionState.IDLE

    def test_add_preference(self):
        """Test adding preferences."""
        human = HumanBlock()
        human.add_preference("Prefers concise answers")
        human.add_preference("Prefers concise answers")  # Duplicate

        assert len(human.preferences) == 1

    def test_add_fact(self):
        """Test adding facts."""
        human = HumanBlock()
        human.add_fact("Works on AI projects")

        assert "Works on AI projects" in human.facts


class TestContextMetrics:
    """Tests for ContextMetrics."""

    def test_metrics_calculation(self):
        """Test metrics calculations."""
        metrics = ContextMetrics(
            persona_chars=750,
            human_chars=1000,
            persona_max=1500,
            human_max=1500,
        )

        assert metrics.persona_usage == 0.5
        assert metrics.human_usage == pytest.approx(0.666, rel=0.01)
        assert metrics.total_chars == 1750
        assert metrics.total_max == 3000


class TestContextStrategies:
    """Tests for context rotation strategies."""

    def test_aggressive_rotation_threshold(self):
        """Test aggressive rotation triggers at 70%."""
        strategy = AggressiveRotation()

        below_threshold = ContextMetrics(
            persona_chars=500,
            human_chars=1000,
            persona_max=1500,
            human_max=1500,
        )
        above_threshold = ContextMetrics(
            persona_chars=500,
            human_chars=1200,
            persona_max=1500,
            human_max=1500,
        )

        assert not strategy.should_rotate(below_threshold)
        assert strategy.should_rotate(above_threshold)

    def test_preservative_rotation_threshold(self):
        """Test preservative rotation triggers at 90%."""
        strategy = PreservativeRotation()

        below_threshold = ContextMetrics(
            persona_chars=500,
            human_chars=1200,
            persona_max=1500,
            human_max=1500,
        )
        above_threshold = ContextMetrics(
            persona_chars=500,
            human_chars=1400,
            persona_max=1500,
            human_max=1500,
        )

        assert not strategy.should_rotate(below_threshold)
        assert strategy.should_rotate(above_threshold)

    def test_adaptive_rotation(self):
        """Test adaptive rotation."""
        strategy = AdaptiveRotation()

        metrics = ContextMetrics(
            persona_chars=500,
            human_chars=1300,
            persona_max=1500,
            human_max=1500,
        )

        # Should trigger around 80% by default
        assert strategy.should_rotate(metrics)

    def test_compress_preserves_structure(self):
        """Test that compression preserves structured content."""
        strategy = PreservativeRotation()
        content = """[USER] Alice | Developer
[TASK] Building agents
Other unstructured content here
More unstructured content"""

        compressed = strategy.compress(content, 60)

        # Should keep structured lines
        assert "[USER]" in compressed or "[TASK]" in compressed
