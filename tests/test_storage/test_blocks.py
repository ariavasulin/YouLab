"""Tests for UserBlockManager."""

import tempfile
import tomllib
from pathlib import Path

import pytest

from youlab_server.storage.blocks import UserBlockManager
from youlab_server.storage.git import GitUserStorage


class TestUserBlockManager:
    """Tests for UserBlockManager."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for user storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def user_storage(self, temp_storage_dir):
        """Create and initialize user storage."""
        storage = GitUserStorage("test_user", temp_storage_dir)
        storage.init()
        return storage

    @pytest.fixture
    def manager(self, user_storage):
        """Create a UserBlockManager without Letta client."""
        return UserBlockManager("test_user", user_storage, letta_client=None)

    @pytest.fixture
    def sample_toml(self):
        """Sample TOML content for a student block."""
        return 'name = "Alice"\nbackground = "Computer science student"'

    # =========================================================================
    # Block CRUD Tests
    # =========================================================================

    def test_list_blocks_empty(self, manager):
        """List blocks returns empty list for new user."""
        blocks = manager.list_blocks()
        assert blocks == []

    def test_list_blocks_after_write(self, manager, user_storage, sample_toml):
        """List blocks returns block labels after write."""
        user_storage.write_block("student", sample_toml, author="test")

        blocks = manager.list_blocks()
        assert "student" in blocks

    def test_get_block_toml(self, manager, user_storage, sample_toml):
        """Get block TOML returns content."""
        user_storage.write_block("student", sample_toml, author="test")

        content = manager.get_block_toml("student")
        assert content is not None
        assert 'name = "Alice"' in content

    def test_get_block_toml_nonexistent(self, manager):
        """Get block TOML returns None for nonexistent block."""
        content = manager.get_block_toml("nonexistent")
        assert content is None

    def test_get_block_markdown(self, manager, user_storage, sample_toml):
        """Get block markdown converts TOML to markdown."""
        user_storage.write_block("student", sample_toml, author="test")

        markdown = manager.get_block_markdown("student")
        assert markdown is not None
        assert "---" in markdown
        assert "block: student" in markdown
        assert "## Name" in markdown
        assert "Alice" in markdown

    def test_get_block_markdown_nonexistent(self, manager):
        """Get block markdown returns None for nonexistent block."""
        markdown = manager.get_block_markdown("nonexistent")
        assert markdown is None

    def test_update_block_from_toml(self, manager):
        """Update block from TOML creates commit."""
        toml_content = 'name = "Bob"\nrole = "Developer"'

        commit_sha = manager.update_block_from_toml(
            label="student",
            toml_content=toml_content,
            message="Add student block",
            author="test",
        )

        assert commit_sha is not None
        assert len(commit_sha) == 40  # Full SHA

        # Verify content
        content = manager.get_block_toml("student")
        assert 'name = "Bob"' in content

    def test_update_block_from_markdown(self, manager):
        """Update block from markdown converts and creates commit."""
        markdown = """---
block: student
---

## Name
Charlie

## Role
Designer
"""
        commit_sha = manager.update_block_from_markdown(
            label="student",
            markdown=markdown,
            message="Add student via markdown",
        )

        assert commit_sha is not None

        # Verify TOML content
        content = manager.get_block_toml("student")
        data = tomllib.loads(content)
        assert data["name"] == "Charlie"
        assert data["role"] == "Designer"

    # =========================================================================
    # Version History Tests
    # =========================================================================

    def test_get_history(self, manager):
        """Get history returns version list."""
        # Create initial version
        manager.update_block_from_toml("student", 'name = "Alice"', author="test")

        # Create second version
        manager.update_block_from_toml("student", 'name = "Bob"', author="test")

        history = manager.get_history("student")
        assert len(history) == 2
        assert history[0]["is_current"] is True
        assert history[1]["is_current"] is False

    def test_get_history_empty_for_new_block(self, manager):
        """Get history returns empty list for nonexistent block."""
        history = manager.get_history("nonexistent")
        assert history == []

    def test_get_version(self, manager):
        """Get version returns content at specific commit."""
        # Create initial version
        commit1 = manager.update_block_from_toml("student", 'name = "Alice"', author="test")

        # Create second version
        manager.update_block_from_toml("student", 'name = "Bob"', author="test")

        # Get first version
        content = manager.get_version("student", commit1)
        assert content is not None
        assert 'name = "Alice"' in content

    def test_restore_version(self, manager):
        """Restore version creates new commit with old content."""
        # Create initial version
        commit1 = manager.update_block_from_toml("student", 'name = "Alice"', author="test")

        # Create second version
        manager.update_block_from_toml("student", 'name = "Bob"', author="test")

        # Restore first version
        new_commit = manager.restore_version("student", commit1)
        assert new_commit is not None

        # Verify content is restored
        content = manager.get_block_toml("student")
        assert 'name = "Alice"' in content

        # Verify history has 3 entries
        history = manager.get_history("student")
        assert len(history) == 3

    # =========================================================================
    # Pending Diff Tests
    # =========================================================================

    def test_propose_edit_creates_diff(self, manager, user_storage, sample_toml):
        """Propose edit creates a pending diff."""
        user_storage.write_block("student", sample_toml, author="system")

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="User prefers Bob",
        )

        assert diff.id is not None
        assert diff.status == "pending"
        assert diff.block_label == "student"
        assert diff.agent_id == "agent1"

    def test_list_pending_diffs(self, manager, user_storage, sample_toml):
        """List pending diffs returns all pending diffs."""
        user_storage.write_block("student", sample_toml, author="system")

        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="First proposal",
        )
        manager.propose_edit(
            agent_id="agent2",
            block_label="student",
            field="background",
            operation="append",
            proposed_value='background = "Senior student"',
            reasoning="Second proposal",
        )

        diffs = manager.list_pending_diffs()
        assert len(diffs) == 2

    def test_list_pending_diffs_by_block(self, manager, user_storage, sample_toml):
        """List pending diffs filters by block."""
        user_storage.write_block("student", sample_toml, author="system")
        user_storage.write_block("journey", 'progress = "Started"', author="system")

        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Student proposal",
        )
        manager.propose_edit(
            agent_id="agent1",
            block_label="journey",
            field="progress",
            operation="append",
            proposed_value='progress = "Advanced"',
            reasoning="Journey proposal",
        )

        student_diffs = manager.list_pending_diffs(block_label="student")
        assert len(student_diffs) == 1
        assert student_diffs[0]["block"] == "student"

    def test_count_pending_diffs(self, manager, user_storage, sample_toml):
        """Count pending diffs returns counts per block."""
        user_storage.write_block("student", sample_toml, author="system")
        user_storage.write_block("journey", 'progress = "Started"', author="system")

        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="First",
        )
        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="background",
            operation="append",
            proposed_value='background = "Senior"',
            reasoning="Second",
        )
        manager.propose_edit(
            agent_id="agent1",
            block_label="journey",
            field="progress",
            operation="append",
            proposed_value='progress = "Advanced"',
            reasoning="Third",
        )

        counts = manager.count_pending_diffs()
        assert counts["student"] == 2
        assert counts["journey"] == 1

    def test_approve_diff_applies_change(self, manager, user_storage, sample_toml):
        """Approve diff applies the proposed change."""
        user_storage.write_block("student", sample_toml, author="system")

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "Bob"\nbackground = "Graduate student"',
            reasoning="Complete update",
        )

        commit_sha = manager.approve_diff(diff.id)
        assert commit_sha is not None

        # Verify content changed
        content = manager.get_block_toml("student")
        assert 'name = "Bob"' in content
        assert "Graduate student" in content

        # Verify diff status updated
        diffs = manager.list_pending_diffs()
        assert len(diffs) == 0

    def test_approve_diff_not_found(self, manager):
        """Approve diff raises error for nonexistent diff."""
        with pytest.raises(ValueError, match="not found"):
            manager.approve_diff("nonexistent-id")

    def test_approve_diff_already_approved(self, manager, user_storage, sample_toml):
        """Approve diff raises error for already approved diff."""
        user_storage.write_block("student", sample_toml, author="system")

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Update",
        )

        manager.approve_diff(diff.id)

        with pytest.raises(ValueError, match="not pending"):
            manager.approve_diff(diff.id)

    def test_reject_diff(self, manager, user_storage, sample_toml):
        """Reject diff marks it as rejected."""
        user_storage.write_block("student", sample_toml, author="system")

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Update",
        )

        manager.reject_diff(diff.id, reason="Not accurate")

        # Verify content unchanged
        content = manager.get_block_toml("student")
        assert 'name = "Alice"' in content

        # Verify diff no longer pending
        diffs = manager.list_pending_diffs()
        assert len(diffs) == 0

    def test_approve_supersedes_older_diffs(self, manager, user_storage, sample_toml):
        """Approving a diff supersedes older pending diffs for same block."""
        user_storage.write_block("student", sample_toml, author="system")

        # First proposal (will be superseded)
        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="First proposal",
        )
        diff2 = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "Charlie"',
            reasoning="Second proposal",
        )

        # Approve the second one
        manager.approve_diff(diff2.id)

        # Both should no longer be pending
        diffs = manager.list_pending_diffs()
        assert len(diffs) == 0

    # =========================================================================
    # Letta Block Name Tests
    # =========================================================================

    def test_letta_block_name(self, manager):
        """Letta block name follows user-scoped naming convention."""
        name = manager._letta_block_name("student")
        assert name == "youlab_user_test_user_student"

    # =========================================================================
    # Integration: Pending Diff includes agent_id
    # =========================================================================

    def test_pending_diff_includes_agent_id(self, manager, user_storage, sample_toml):
        """Pending diff dict includes agent_id for UI display."""
        user_storage.write_block("student", sample_toml, author="system")

        manager.propose_edit(
            agent_id="insight_synthesizer",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Observed preference",
        )

        diffs = manager.list_pending_diffs()
        assert len(diffs) == 1
        assert diffs[0]["agent_id"] == "insight_synthesizer"
