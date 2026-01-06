"""Integration tests for Honcho with server endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestServerHonchoIntegration:
    """Test Honcho integration in server endpoints."""

    @pytest.fixture
    def mock_agent_manager(self) -> MagicMock:
        """Create mock agent manager."""
        manager = MagicMock()
        manager.get_agent_info.return_value = {
            "agent_id": "agent-123",
            "user_id": "user-456",
            "agent_type": "tutor",
            "agent_name": "youlab_user-456_tutor",
        }
        manager.send_message.return_value = "Hello! I'm here to help."
        manager.check_letta_connection.return_value = True
        return manager

    @pytest.fixture
    def mock_honcho_client(self) -> MagicMock:
        """Create mock Honcho client."""
        client = MagicMock()
        client.check_connection.return_value = True
        return client

    def test_health_includes_honcho_status(
        self,
        mock_agent_manager: MagicMock,
        mock_honcho_client: MagicMock,
    ) -> None:
        """Test health endpoint includes Honcho connection status."""
        with (
            patch("letta_starter.server.main.get_agent_manager") as mock_get_manager,
            patch("letta_starter.server.main.get_honcho_client") as mock_get_honcho,
        ):
            mock_get_manager.return_value = mock_agent_manager
            mock_get_honcho.return_value = mock_honcho_client

            from letta_starter.server.main import app

            client = TestClient(app)

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert "honcho_connected" in data
