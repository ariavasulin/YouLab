"""Tests for memory block CRUD API endpoints."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from youlab_server.server.main import app
from youlab_server.server.users import get_storage_manager, set_storage_manager
from youlab_server.storage.git import GitUserStorageManager


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for user storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage_manager(temp_storage_dir):
    """Create a real GitUserStorageManager with temp directory."""
    return GitUserStorageManager(temp_storage_dir)


@pytest.fixture
def blocks_test_client(storage_manager, mock_agent_manager):
    """Test client with real storage manager for blocks testing."""
    set_storage_manager(storage_manager)
    app.state.agent_manager = mock_agent_manager
    app.dependency_overrides[get_storage_manager] = lambda: storage_manager

    yield TestClient(app)

    app.dependency_overrides.clear()
    set_storage_manager(None)


@pytest.fixture
def initialized_user(storage_manager):
    """Create an initialized user with some blocks."""
    user_storage = storage_manager.get("test-user")
    user_storage.init()

    # Create a student block
    user_storage.write_block(
        "student",
        'name = "Alice"\nbackground = "Computer science student"',
        message="Initialize student block",
        author="system",
    )

    # Create a journey block
    user_storage.write_block(
        "journey",
        'progress = "Module 1"',
        message="Initialize journey block",
        author="system",
    )

    return "test-user"


class TestListBlocksEndpoint:
    """Tests for GET /users/{user_id}/blocks endpoint."""

    def test_list_blocks_returns_blocks(self, blocks_test_client, initialized_user):
        """List blocks returns all blocks for a user."""
        response = blocks_test_client.get(f"/users/{initialized_user}/blocks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        labels = [b["label"] for b in data]
        assert "student" in labels
        assert "journey" in labels

    def test_list_blocks_includes_pending_diff_counts(
        self, blocks_test_client, storage_manager, initialized_user
    ):
        """List blocks includes pending diff count per block."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        # Create a pending diff
        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Test",
        )

        response = blocks_test_client.get(f"/users/{initialized_user}/blocks")

        assert response.status_code == 200
        data = response.json()

        student_block = next(b for b in data if b["label"] == "student")
        assert student_block["pending_diffs"] == 1

    def test_list_blocks_user_not_found(self, blocks_test_client):
        """List blocks returns 404 for nonexistent user."""
        response = blocks_test_client.get("/users/nonexistent-user/blocks")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetBlockEndpoint:
    """Tests for GET /users/{user_id}/blocks/{label} endpoint."""

    def test_get_block_returns_detail(self, blocks_test_client, initialized_user):
        """Get block returns TOML and markdown content."""
        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")

        assert response.status_code == 200
        data = response.json()

        assert data["label"] == "student"
        assert 'name = "Alice"' in data["content_toml"]
        assert "---" in data["content_markdown"]
        assert "block: student" in data["content_markdown"]
        assert "Alice" in data["content_markdown"]

    def test_get_block_not_found(self, blocks_test_client, initialized_user):
        """Get block returns 404 for nonexistent block."""
        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateBlockEndpoint:
    """Tests for PUT /users/{user_id}/blocks/{label} endpoint."""

    def test_update_block_from_markdown(self, blocks_test_client, initialized_user):
        """Update block from markdown content."""
        markdown = """---
block: student
---

## Name
Bob

## Background
Updated background
"""
        response = blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={"content": markdown, "format": "markdown"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "student"
        assert len(data["commit_sha"]) == 40

        # Verify content updated
        get_response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")
        assert "Bob" in get_response.json()["content_toml"]

    def test_update_block_from_toml(self, blocks_test_client, initialized_user):
        """Update block from TOML content."""
        toml_content = 'name = "Charlie"\nbackground = "New background"'

        response = blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={"content": toml_content, "format": "toml"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["commit_sha"]) == 40

        # Verify content updated
        get_response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")
        assert 'name = "Charlie"' in get_response.json()["content_toml"]

    def test_update_block_with_custom_message(self, blocks_test_client, initialized_user):
        """Update block with custom commit message."""
        response = blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={
                "content": 'name = "Dave"',
                "format": "toml",
                "message": "Custom commit message",
            },
        )

        assert response.status_code == 200


class TestBlockHistoryEndpoint:
    """Tests for GET /users/{user_id}/blocks/{label}/history endpoint."""

    def test_get_history(self, blocks_test_client, initialized_user):
        """Get history returns version list."""
        # Make another edit to have 2 versions
        blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={"content": 'name = "Bob"', "format": "toml"},
        )

        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["is_current"] is True
        assert data[1]["is_current"] is False
        assert all(len(v["sha"]) == 40 for v in data)

    def test_get_history_with_limit(self, blocks_test_client, initialized_user):
        """Get history respects limit parameter."""
        # Make several edits
        for i in range(5):
            blocks_test_client.put(
                f"/users/{initialized_user}/blocks/student",
                json={"content": f'name = "Version{i}"', "format": "toml"},
            )

        response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/history?limit=3"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestBlockVersionEndpoint:
    """Tests for GET /users/{user_id}/blocks/{label}/versions/{sha} endpoint."""

    def test_get_specific_version(self, blocks_test_client, initialized_user):
        """Get specific version returns content at that commit."""
        # Get current version's SHA
        history_response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/history"
        )
        original_sha = history_response.json()[0]["sha"]

        # Make an edit
        blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={"content": 'name = "NewName"', "format": "toml"},
        )

        # Get the original version
        response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/versions/{original_sha}"
        )

        assert response.status_code == 200
        data = response.json()
        assert 'name = "Alice"' in data["content"]
        assert data["sha"] == original_sha

    def test_get_version_not_found(self, blocks_test_client, initialized_user):
        """Get version returns 404 for nonexistent SHA."""
        response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/versions/0000000000000000000000000000000000000000"
        )

        assert response.status_code == 404


class TestRestoreBlockEndpoint:
    """Tests for POST /users/{user_id}/blocks/{label}/restore endpoint."""

    def test_restore_version(self, blocks_test_client, initialized_user):
        """Restore creates new commit with old content."""
        # Get current version's SHA
        history_response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/history"
        )
        original_sha = history_response.json()[0]["sha"]

        # Make an edit
        blocks_test_client.put(
            f"/users/{initialized_user}/blocks/student",
            json={"content": 'name = "ChangedName"', "format": "toml"},
        )

        # Restore original version
        response = blocks_test_client.post(
            f"/users/{initialized_user}/blocks/student/restore",
            json={"commit_sha": original_sha},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["commit_sha"]) == 40

        # Verify content restored
        get_response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")
        assert 'name = "Alice"' in get_response.json()["content_toml"]

        # Verify history has 3 entries
        history_response = blocks_test_client.get(
            f"/users/{initialized_user}/blocks/student/history"
        )
        assert len(history_response.json()) == 3


class TestBlockDiffsEndpoints:
    """Tests for pending diff endpoints."""

    def test_list_block_diffs(self, blocks_test_client, storage_manager, initialized_user):
        """List diffs returns pending diffs for a block."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        # Create pending diffs
        manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field="name",
            operation="replace",
            proposed_value='name = "Bob"',
            reasoning="Test reasoning",
        )

        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student/diffs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["block"] == "student"
        assert data[0]["reasoning"] == "Test reasoning"

    def test_approve_diff(self, blocks_test_client, storage_manager, initialized_user):
        """Approve diff applies the change."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "ApprovedName"',
            reasoning="Approval test",
        )

        response = blocks_test_client.post(
            f"/users/{initialized_user}/blocks/student/diffs/{diff.id}/approve"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["diff_id"] == diff.id
        assert len(data["commit_sha"]) == 40

        # Verify content changed
        get_response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")
        assert "ApprovedName" in get_response.json()["content_toml"]

    def test_approve_diff_not_found(self, blocks_test_client, initialized_user):
        """Approve diff returns 400 for nonexistent diff."""
        response = blocks_test_client.post(
            f"/users/{initialized_user}/blocks/student/diffs/nonexistent-id/approve"
        )

        assert response.status_code == 400

    def test_reject_diff(self, blocks_test_client, storage_manager, initialized_user):
        """Reject diff marks it as rejected."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "RejectedName"',
            reasoning="Rejection test",
        )

        response = blocks_test_client.post(
            f"/users/{initialized_user}/blocks/student/diffs/{diff.id}/reject"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["diff_id"] == diff.id

        # Verify content unchanged
        get_response = blocks_test_client.get(f"/users/{initialized_user}/blocks/student")
        assert 'name = "Alice"' in get_response.json()["content_toml"]

    def test_reject_diff_with_reason(self, blocks_test_client, storage_manager, initialized_user):
        """Reject diff accepts optional reason."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        diff = manager.propose_edit(
            agent_id="agent1",
            block_label="student",
            field=None,
            operation="replace",
            proposed_value='name = "WrongName"',
            reasoning="Test",
        )

        response = blocks_test_client.post(
            f"/users/{initialized_user}/blocks/student/diffs/{diff.id}/reject?reason=Not%20accurate"
        )

        assert response.status_code == 200


class TestDiffCountsEndpoint:
    """Tests for GET /users/{user_id}/blocks/diffs/counts endpoint."""

    def test_get_diff_counts(self, blocks_test_client, storage_manager, initialized_user):
        """Get diff counts returns counts per block."""
        from youlab_server.storage.blocks import UserBlockManager

        user_storage = storage_manager.get(initialized_user)
        manager = UserBlockManager(initialized_user, user_storage)

        # Create diffs for different blocks
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
            proposed_value='progress = "Module 2"',
            reasoning="Third",
        )

        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/diffs/counts")

        assert response.status_code == 200
        data = response.json()
        assert data["student"] == 2
        assert data["journey"] == 1

    def test_get_diff_counts_empty(self, blocks_test_client, initialized_user):
        """Get diff counts returns empty dict when no diffs."""
        response = blocks_test_client.get(f"/users/{initialized_user}/blocks/diffs/counts")

        assert response.status_code == 200
        data = response.json()
        assert data == {}
