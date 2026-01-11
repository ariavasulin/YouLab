"""Tests for memory enricher service."""

import pytest

from youlab_server.memory.enricher import (
    EnrichmentResult,
    MemoryEnricher,
    MergeStrategy,
)


class MockLettaClient:
    """Mock Letta client for testing."""

    def __init__(self):
        self.agent_memory = {"persona": "", "human": ""}
        self.archival_entries = []

    def get_agent_memory(self, agent_id: str) -> dict:
        return self.agent_memory

    def update_agent_core_memory(self, agent_id: str, **kwargs) -> None:
        if "persona" in kwargs:
            self.agent_memory["persona"] = kwargs["persona"]
        if "human" in kwargs:
            self.agent_memory["human"] = kwargs["human"]

    def insert_archival_memory(self, agent_id: str, memory: str) -> None:
        self.archival_entries.append({"agent_id": agent_id, "memory": memory})


@pytest.fixture
def mock_client():
    """Create a mock Letta client."""
    return MockLettaClient()


@pytest.fixture
def enricher(mock_client):
    """Create a MemoryEnricher with mock client."""
    return MemoryEnricher(mock_client)


class TestMemoryEnricher:
    """Tests for MemoryEnricher."""

    def test_enrich_human_context_notes_append(self, enricher, mock_client):
        """Test enriching human block context_notes with append."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="context_notes",
            content="Student prefers visual examples",
            strategy=MergeStrategy.APPEND,
            source="test",
        )

        assert result.success is True
        assert result.block == "human"
        assert result.field == "context_notes"
        assert result.strategy == MergeStrategy.APPEND
        assert "context_notes" in result.message
        assert "[CONTEXT]" in mock_client.agent_memory["human"]

    def test_enrich_human_facts_append(self, enricher, mock_client):
        """Test enriching human block facts with append."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="facts",
            content="Works best in morning sessions",
            strategy=MergeStrategy.APPEND,
            source="background_worker",
        )

        assert result.success is True
        assert result.field == "facts"
        assert "[FACTS]" in mock_client.agent_memory["human"]

    def test_enrich_human_preferences_replace(self, enricher, mock_client):
        """Test enriching human block preferences with replace."""
        # First add a preference
        enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="preferences",
            content="Old preference",
            strategy=MergeStrategy.APPEND,
            source="test",
        )

        # Replace with new preference
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="preferences",
            content="New preference only",
            strategy=MergeStrategy.REPLACE,
            source="test",
        )

        assert result.success is True
        assert result.strategy == MergeStrategy.REPLACE
        # Should only have the new preference
        assert "New preference only" in mock_client.agent_memory["human"]

    def test_enrich_persona_constraints_append(self, enricher, mock_client):
        """Test enriching persona block constraints with append."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="persona",
            field="constraints",
            content="Use encouraging language",
            strategy=MergeStrategy.APPEND,
            source="insight-harvester",
        )

        assert result.success is True
        assert result.block == "persona"
        assert "[CONSTRAINTS]" in mock_client.agent_memory["persona"]

    def test_enrich_persona_expertise_append(self, enricher, mock_client):
        """Test enriching persona block expertise with append."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="persona",
            field="expertise",
            content="Essay structure coaching",
            strategy=MergeStrategy.APPEND,
            source="test",
        )

        assert result.success is True
        assert result.field == "expertise"
        assert "Essay structure coaching" in mock_client.agent_memory["persona"]

    def test_enrich_unknown_block_fails(self, enricher):
        """Test that enriching unknown block returns failure."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="unknown",
            field="test",
            content="test content",
            source="test",
        )

        assert result.success is False
        assert "Unknown block" in result.message

    def test_enrich_unknown_human_field_fails(self, enricher):
        """Test that enriching unknown human field returns failure."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="unknown_field",
            content="test content",
            source="test",
        )

        assert result.success is False
        assert "failed" in result.message.lower()

    def test_enrich_unknown_persona_field_fails(self, enricher):
        """Test that enriching unknown persona field returns failure."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="persona",
            field="unknown_field",
            content="test content",
            source="test",
        )

        assert result.success is False
        assert "failed" in result.message.lower()


class TestAuditTrail:
    """Tests for audit trail functionality."""

    def test_audit_entry_written_on_success(self, enricher, mock_client):
        """Test that audit entry is written to archival memory."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="context_notes",
            content="Test insight content",
            strategy=MergeStrategy.APPEND,
            source="insight-harvester",
            source_query="What is the student's learning style?",
        )

        assert result.success is True
        assert result.audit_entry_id is not None
        assert len(mock_client.archival_entries) == 1

        audit_entry = mock_client.archival_entries[0]["memory"]
        assert "[MEMORY_EDIT" in audit_entry
        assert "Source: insight-harvester" in audit_entry
        assert "Block: human" in audit_entry
        assert "Field: context_notes" in audit_entry
        assert "Strategy: append" in audit_entry
        assert "Query: What is the student's learning style?" in audit_entry
        assert "Content: Test insight content" in audit_entry

    def test_audit_entry_truncates_long_content(self, enricher, mock_client):
        """Test that long content is truncated in audit entry."""
        long_content = "A" * 300

        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="facts",
            content=long_content,
            strategy=MergeStrategy.APPEND,
            source="test",
        )

        assert result.success is True
        audit_entry = mock_client.archival_entries[0]["memory"]
        # Should be truncated to ~200 chars + "..."
        assert "..." in audit_entry
        assert len(audit_entry) < len(long_content) + 200

    def test_audit_entry_without_source_query(self, enricher, mock_client):
        """Test audit entry without optional source_query."""
        result = enricher.enrich(
            agent_id="test-agent",
            block="human",
            field="context_notes",
            content="Simple note",
            source="manual",
        )

        assert result.success is True
        audit_entry = mock_client.archival_entries[0]["memory"]
        assert "Query:" not in audit_entry


class TestEnrichmentResult:
    """Tests for EnrichmentResult dataclass."""

    def test_enrichment_result_fields(self):
        """Test EnrichmentResult has correct fields."""
        result = EnrichmentResult(
            success=True,
            block="human",
            field="facts",
            strategy=MergeStrategy.APPEND,
            message="Test message",
            audit_entry_id="2024-01-01T00:00:00",
        )

        assert result.success is True
        assert result.block == "human"
        assert result.field == "facts"
        assert result.strategy == MergeStrategy.APPEND
        assert result.message == "Test message"
        assert result.audit_entry_id == "2024-01-01T00:00:00"

    def test_enrichment_result_optional_audit_id(self):
        """Test EnrichmentResult with no audit_entry_id."""
        result = EnrichmentResult(
            success=False,
            block="human",
            field="facts",
            strategy=MergeStrategy.APPEND,
            message="Failed",
        )

        assert result.audit_entry_id is None


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_merge_strategy_values(self):
        """Test MergeStrategy enum values."""
        assert MergeStrategy.APPEND.value == "append"
        assert MergeStrategy.REPLACE.value == "replace"
        assert MergeStrategy.LLM_DIFF.value == "llm_diff"

    def test_merge_strategy_from_string(self):
        """Test creating MergeStrategy from string."""
        assert MergeStrategy("append") == MergeStrategy.APPEND
        assert MergeStrategy("replace") == MergeStrategy.REPLACE
        assert MergeStrategy("llm_diff") == MergeStrategy.LLM_DIFF
