"""Tests for user management endpoints."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from youlab_server.server.main import app
from youlab_server.server.users import get_storage_manager, set_storage_manager
from youlab_server.storage.git import GitUserStorage, GitUserStorageManager


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
def mock_storage_manager():
    """Create a mock GitUserStorageManager."""
    manager = MagicMock(spec=GitUserStorageManager)

    # Default: user doesn't exist
    mock_storage = MagicMock(spec=GitUserStorage)
    mock_storage.exists = False
    mock_storage.init = MagicMock()
    mock_storage.write_block = MagicMock(return_value="abc123")
    manager.get.return_value = mock_storage
    manager.user_exists.return_value = False

    return manager


@pytest.fixture
def users_test_client(mock_storage_manager, mock_agent_manager):
    """Test client with mocked storage manager."""
    # Set up the storage manager
    set_storage_manager(mock_storage_manager)
    app.state.agent_manager = mock_agent_manager

    # Override the dependency
    app.dependency_overrides[get_storage_manager] = lambda: mock_storage_manager

    yield TestClient(app)

    # Clean up
    app.dependency_overrides.clear()
    set_storage_manager(None)


class TestUserInitEndpoint:
    """Tests for POST /users/init endpoint."""

    def test_init_user_creates_storage(self, users_test_client, mock_storage_manager):
        """Test user initialization creates storage directory."""
        # Mock curriculum to return None (no course config)
        with patch("youlab_server.server.users.curriculum") as mock_curriculum:
            mock_curriculum.get.return_value = None

            response = users_test_client.post(
                "/users/init",
                json={"user_id": "test-user-123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"
        assert data["created"] is True
        assert data["message"] == "Initialized 0 memory blocks"

        # Verify storage was initialized
        mock_storage_manager.get.assert_called_with("test-user-123")
        mock_storage = mock_storage_manager.get.return_value
        mock_storage.init.assert_called_once()

    def test_init_user_with_name(self, users_test_client, mock_storage_manager):
        """Test user initialization with name parameter."""
        with patch("youlab_server.server.users.curriculum") as mock_curriculum:
            mock_curriculum.get.return_value = None

            response = users_test_client.post(
                "/users/init",
                json={
                    "user_id": "test-user-123",
                    "name": "Alice Smith",
                    "email": "alice@example.com",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test-user-123"
        assert data["created"] is True

    def test_init_user_idempotent(self, users_test_client, mock_storage_manager):
        """Test that initializing an existing user is idempotent."""
        # Set up mock to indicate user already exists
        mock_storage = mock_storage_manager.get.return_value
        mock_storage.exists = True

        with patch("youlab_server.server.users.curriculum"):
            response = users_test_client.post(
                "/users/init",
                json={"user_id": "existing-user"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "existing-user"
        assert data["created"] is False
        assert data["message"] == "User already initialized"

        # Verify init was NOT called since user exists
        mock_storage.init.assert_not_called()

    def test_init_user_missing_user_id(self, users_test_client):
        """Test that user_id is required."""
        response = users_test_client.post(
            "/users/init",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_init_user_with_course_blocks(self, users_test_client, mock_storage_manager):
        """Test user initialization creates blocks from course config."""
        from pydantic import BaseModel

        # Create real Pydantic models for testing
        class StudentBlock(BaseModel):
            name: str = ""
            background: str = ""

        class JourneyBlock(BaseModel):
            progress: str = ""

        # Create mock course config
        mock_course = MagicMock()
        mock_course.blocks = {
            "student": MagicMock(label="human"),
            "journey": MagicMock(label="persona"),
        }

        # Create mock block registry with real Pydantic models
        mock_registry = {
            "student": StudentBlock,
            "journey": JourneyBlock,
        }

        with patch("youlab_server.server.users.curriculum") as mock_curriculum:
            mock_curriculum.get.return_value = mock_course
            mock_curriculum.get_block_registry.return_value = mock_registry

            response = users_test_client.post(
                "/users/init",
                json={
                    "user_id": "test-user",
                    "name": "Alice",
                    "course_id": "college-essay",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["created"] is True
        assert len(data["blocks_initialized"]) == 2
        assert "student" in data["blocks_initialized"]
        assert "journey" in data["blocks_initialized"]


class TestUserExistsEndpoint:
    """Tests for GET /users/{user_id}/exists endpoint."""

    def test_user_exists_true(self, users_test_client, mock_storage_manager):
        """Test exists endpoint returns true when user exists."""
        mock_storage_manager.user_exists.return_value = True

        response = users_test_client.get("/users/existing-user/exists")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True

    def test_user_exists_false(self, users_test_client, mock_storage_manager):
        """Test exists endpoint returns false when user doesn't exist."""
        mock_storage_manager.user_exists.return_value = False

        response = users_test_client.get("/users/nonexistent-user/exists")

        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False


class TestUserInitIntegration:
    """Integration tests for user initialization with real storage."""

    def test_init_creates_git_repo(self, temp_storage_dir):
        """Test that initialization creates a real git repo."""
        manager = GitUserStorageManager(temp_storage_dir)
        set_storage_manager(manager)
        app.dependency_overrides[get_storage_manager] = lambda: manager

        try:
            client = TestClient(app)

            with patch("youlab_server.server.users.curriculum") as mock_curriculum:
                mock_curriculum.get.return_value = None

                response = client.post(
                    "/users/init",
                    json={"user_id": "integration-test-user"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["created"] is True

            # Verify git repo was actually created
            user_dir = temp_storage_dir / "integration-test-user"
            assert user_dir.exists()
            assert (user_dir / ".git").exists()
            assert (user_dir / "memory-blocks").exists()

        finally:
            app.dependency_overrides.clear()
            set_storage_manager(None)
