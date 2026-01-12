"""Tests for PendingDiff and PendingDiffStore."""

import json
import tempfile
from pathlib import Path

import pytest

from youlab_server.storage.diffs import PendingDiff, PendingDiffStore


class TestPendingDiff:
    """Tests for PendingDiff dataclass."""

    def test_create_generates_uuid(self):
        """Create method generates unique UUID."""
        diff1 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new",
            reasoning="test",
        )
        diff2 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new",
            reasoning="test",
        )

        assert diff1.id != diff2.id
        assert len(diff1.id) == 36  # UUID format

    def test_create_sets_defaults(self):
        """Create method sets default values."""
        diff = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="append",
            current_value="old",
            proposed_value="new",
            reasoning="Adding info",
        )

        assert diff.status == "pending"
        assert diff.confidence == "medium"
        assert diff.source_query is None
        assert diff.reviewed_at is None
        assert diff.applied_commit is None
        assert diff.created_at is not None

    def test_create_with_custom_values(self):
        """Create method accepts custom values."""
        diff = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="journey",
            field=None,
            operation="llm_diff",
            current_value="old content",
            proposed_value="new content",
            reasoning="Updating journey",
            confidence="high",
            source_query="What progress did we make?",
        )

        assert diff.block_label == "journey"
        assert diff.field is None
        assert diff.operation == "llm_diff"
        assert diff.confidence == "high"
        assert diff.source_query == "What progress did we make?"


class TestPendingDiffStore:
    """Tests for PendingDiffStore."""

    @pytest.fixture
    def temp_diffs_dir(self):
        """Create a temporary directory for diffs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_diffs_dir):
        """Create a PendingDiffStore with temp directory."""
        return PendingDiffStore(temp_diffs_dir)

    @pytest.fixture
    def sample_diff(self):
        """Create a sample pending diff."""
        return PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value='name = "Alice"',
            proposed_value='name = "Bob"',
            reasoning="User prefers Bob",
        )

    def test_save_creates_file(self, store, sample_diff, temp_diffs_dir):
        """Save creates a JSON file."""
        store.save(sample_diff)

        file_path = temp_diffs_dir / f"{sample_diff.id}.json"
        assert file_path.exists()

        data = json.loads(file_path.read_text())
        assert data["id"] == sample_diff.id
        assert data["user_id"] == "user1"
        assert data["block_label"] == "student"

    def test_get_returns_diff(self, store, sample_diff):
        """Get returns saved diff."""
        store.save(sample_diff)

        retrieved = store.get(sample_diff.id)
        assert retrieved is not None
        assert retrieved.id == sample_diff.id
        assert retrieved.user_id == sample_diff.user_id
        assert retrieved.block_label == sample_diff.block_label
        assert retrieved.status == "pending"

    def test_get_returns_none_for_missing(self, store):
        """Get returns None for non-existent diff."""
        result = store.get("nonexistent-id")
        assert result is None

    def test_list_pending_returns_all_pending(self, store):
        """List pending returns all pending diffs."""
        diff1 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new",
            reasoning="test1",
        )
        diff2 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="journey",
            field="progress",
            operation="append",
            current_value="old",
            proposed_value="new",
            reasoning="test2",
        )
        store.save(diff1)
        store.save(diff2)

        pending = store.list_pending()
        assert len(pending) == 2

    def test_list_pending_filters_by_block(self, store):
        """List pending filters by block label."""
        diff1 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new",
            reasoning="test1",
        )
        diff2 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="journey",
            field="progress",
            operation="append",
            current_value="old",
            proposed_value="new",
            reasoning="test2",
        )
        store.save(diff1)
        store.save(diff2)

        student_diffs = store.list_pending(block_label="student")
        assert len(student_diffs) == 1
        assert student_diffs[0].block_label == "student"

    def test_list_pending_excludes_non_pending(self, store, sample_diff):
        """List pending excludes approved/rejected diffs."""
        store.save(sample_diff)
        store.update_status(sample_diff.id, "approved")

        pending = store.list_pending()
        assert len(pending) == 0

    def test_count_pending_returns_counts_per_block(self, store):
        """Count pending returns counts per block."""
        for i in range(3):
            diff = PendingDiff.create(
                user_id="user1",
                agent_id="agent1",
                block_label="student",
                field="name",
                operation="replace",
                current_value="old",
                proposed_value=f"new{i}",
                reasoning=f"test{i}",
            )
            store.save(diff)

        for i in range(2):
            diff = PendingDiff.create(
                user_id="user1",
                agent_id="agent1",
                block_label="journey",
                field="progress",
                operation="append",
                current_value="old",
                proposed_value=f"new{i}",
                reasoning=f"test{i}",
            )
            store.save(diff)

        counts = store.count_pending()
        assert counts["student"] == 3
        assert counts["journey"] == 2

    def test_update_status_changes_status(self, store, sample_diff):
        """Update status changes diff status."""
        store.save(sample_diff)
        store.update_status(sample_diff.id, "approved", applied_commit="abc123")

        retrieved = store.get(sample_diff.id)
        assert retrieved is not None
        assert retrieved.status == "approved"
        assert retrieved.applied_commit == "abc123"
        assert retrieved.reviewed_at is not None

    def test_supersede_older_marks_older_diffs(self, store):
        """Supersede older marks other pending diffs as superseded."""
        diff1 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new1",
            reasoning="first",
        )
        diff2 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            current_value="old",
            proposed_value="new2",
            reasoning="second",
        )
        diff3 = PendingDiff.create(
            user_id="user1",
            agent_id="agent1",
            block_label="journey",  # Different block
            field="progress",
            operation="append",
            current_value="old",
            proposed_value="new3",
            reasoning="third",
        )
        store.save(diff1)
        store.save(diff2)
        store.save(diff3)

        # Supersede student diffs except diff2
        count = store.supersede_older("student", keep_id=diff2.id)
        assert count == 1

        # Check statuses
        assert store.get(diff1.id).status == "superseded"
        assert store.get(diff2.id).status == "pending"
        assert store.get(diff3.id).status == "pending"  # Different block, unchanged

    def test_list_pending_sorted_by_created_at(self, store):
        """List pending returns diffs sorted by created_at (newest first)."""
        import time

        diffs = []
        for i in range(3):
            diff = PendingDiff.create(
                user_id="user1",
                agent_id="agent1",
                block_label="student",
                field="name",
                operation="replace",
                current_value="old",
                proposed_value=f"new{i}",
                reasoning=f"test{i}",
            )
            store.save(diff)
            diffs.append(diff)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        pending = store.list_pending()
        assert len(pending) == 3
        # Newest first
        assert pending[0].id == diffs[2].id
        assert pending[1].id == diffs[1].id
        assert pending[2].id == diffs[0].id
