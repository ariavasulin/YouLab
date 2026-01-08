"""Tests for Honcho integration."""

from unittest.mock import MagicMock, patch

import pytest

from letta_starter.honcho.client import HonchoClient, create_persist_task


class TestHonchoClient:
    """Tests for HonchoClient class."""

    def test_peer_id_generation(self) -> None:
        """Test peer ID generation."""
        client = HonchoClient(workspace_id="test", environment="demo")
        # Access private method for testing - noqa: SLF001
        assert client._get_student_peer_id("user123") == "student_user123"

    def test_session_id_generation(self) -> None:
        """Test session ID generation."""
        client = HonchoClient(workspace_id="test", environment="demo")
        # Access private method for testing - noqa: SLF001
        assert client._get_session_id("chat456") == "chat_chat456"

    @patch("honcho.Honcho")
    def test_client_lazy_init(self, mock_honcho_class: MagicMock) -> None:
        """Test that Honcho client is lazily initialized."""
        client = HonchoClient(workspace_id="test", environment="demo")
        # Access private attribute for testing - noqa: SLF001
        assert client._client is None

        # Access client property
        _ = client.client

        mock_honcho_class.assert_called_once()
        assert client._client is not None

    @patch("honcho.Honcho")
    def test_production_client_requires_api_key(self, mock_honcho_class: MagicMock) -> None:
        """Test production environment uses API key."""
        client = HonchoClient(
            workspace_id="test",
            api_key="secret-key",
            environment="production",
        )
        _ = client.client

        mock_honcho_class.assert_called_once_with(
            workspace_id="test",
            api_key="secret-key",
            environment="production",
        )


class TestPersistTask:
    """Tests for fire-and-forget persistence."""

    def test_persist_skips_when_client_none(self) -> None:
        """Test that persistence is skipped when client is None."""
        # Should not raise any exceptions
        create_persist_task(
            honcho_client=None,
            user_id="user123",
            chat_id="chat456",
            message="test",
            is_user=True,
        )

    def test_persist_skips_when_no_chat_id(self) -> None:
        """Test that persistence is skipped when chat_id is empty."""
        mock_client = MagicMock(spec=HonchoClient)

        create_persist_task(
            honcho_client=mock_client,
            user_id="user123",
            chat_id="",  # Empty chat_id
            message="test",
            is_user=True,
        )

        # No async task should be created for persistence
        mock_client.persist_user_message.assert_not_called()


class TestHonchoClientPersistence:
    """Tests for message persistence methods."""

    @pytest.mark.asyncio
    async def test_persist_user_message_logs_on_error(self) -> None:
        """Test that errors are logged but not raised."""
        client = HonchoClient(workspace_id="test", environment="demo")

        # Mock the internal client to raise an exception
        mock_honcho = MagicMock()
        mock_honcho.peer.side_effect = Exception("Connection failed")
        client._client = mock_honcho
        client._initialized = True

        # Should not raise
        await client.persist_user_message(
            user_id="user123",
            chat_id="chat456",
            message="test message",
        )

    @pytest.mark.asyncio
    async def test_persist_agent_message_includes_metadata(self) -> None:
        """Test that agent messages include correct metadata."""
        client = HonchoClient(workspace_id="test", environment="demo")

        mock_honcho = MagicMock()
        mock_peer = MagicMock()
        mock_session = MagicMock()
        mock_honcho.peer.return_value = mock_peer
        mock_honcho.session.return_value = mock_session
        client._client = mock_honcho
        client._initialized = True

        await client.persist_agent_message(
            user_id="user123",
            chat_id="chat456",
            message="response",
            chat_title="Test Chat",
            agent_type="tutor",
        )

        # Verify peer and session were accessed
        mock_honcho.peer.assert_called_with("tutor")
        mock_honcho.session.assert_called_with("chat_chat456")

        # Verify message was added
        mock_session.add_messages.assert_called_once()
