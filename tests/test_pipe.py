"""Tests for OpenWebUI Pipe."""

from unittest.mock import MagicMock, patch

import pytest

from letta_starter.pipelines.letta_pipe import Pipeline


class TestPipelineInit:
    """Tests for Pipeline initialization."""

    def test_pipeline_name(self):
        """Test pipeline has correct name."""
        pipeline = Pipeline()
        assert pipeline.name == "YouLab Tutor"

    def test_pipeline_has_valves(self):
        """Test pipeline has valves configuration."""
        pipeline = Pipeline()
        assert hasattr(pipeline, "valves")
        assert pipeline.valves.LETTA_SERVICE_URL == "http://localhost:8100"

    def test_valves_default_values(self):
        """Test valves have correct defaults."""
        pipeline = Pipeline()
        assert pipeline.valves.AGENT_TYPE == "tutor"
        assert pipeline.valves.ENABLE_LOGGING is True


class TestPipelineLifecycle:
    """Tests for pipeline lifecycle methods."""

    @pytest.mark.asyncio
    async def test_on_startup(self, capsys):
        """Test startup handler."""
        pipeline = Pipeline()
        await pipeline.on_startup()

        captured = capsys.readouterr()
        assert "YouLab Pipeline started" in captured.out

    @pytest.mark.asyncio
    async def test_on_shutdown(self, capsys):
        """Test shutdown handler."""
        pipeline = Pipeline()
        await pipeline.on_shutdown()

        captured = capsys.readouterr()
        assert "YouLab Pipeline stopped" in captured.out


class TestGetChatTitle:
    """Tests for _get_chat_title method."""

    def test_no_chat_id(self):
        """Test returns None when no chat_id."""
        pipeline = Pipeline()
        result = pipeline._get_chat_title(None)  # noqa: SLF001
        assert result is None

    def test_local_chat_id(self):
        """Test returns None for local: prefixed IDs."""
        pipeline = Pipeline()
        result = pipeline._get_chat_title("local:some-id")  # noqa: SLF001
        assert result is None

    def test_openwebui_import_error(self):
        """Test handles ImportError gracefully."""
        pipeline = Pipeline()
        result = pipeline._get_chat_title("some-chat-id")  # noqa: SLF001
        # Without OpenWebUI, should return None
        assert result is None


class TestEnsureAgentExists:
    """Tests for _ensure_agent_exists method."""

    def test_agent_exists(self):
        """Test returns agent_id when agent exists."""
        pipeline = Pipeline()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "agents": [{"agent_id": "existing-id", "agent_type": "tutor"}]
            }
            mock_client.get.return_value = mock_response

            with mock_client:
                result = pipeline._ensure_agent_exists(mock_client, "user123")  # noqa: SLF001

            assert result == "existing-id"

    def test_agent_created(self):
        """Test creates agent when not exists."""
        pipeline = Pipeline()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            # First call: no agents
            mock_get_response = MagicMock()
            mock_get_response.status_code = 200
            mock_get_response.json.return_value = {"agents": []}
            mock_client.get.return_value = mock_get_response

            # Second call: create agent
            mock_post_response = MagicMock()
            mock_post_response.status_code = 201
            mock_post_response.json.return_value = {"agent_id": "new-agent-id"}
            mock_client.post.return_value = mock_post_response

            with mock_client:
                result = pipeline._ensure_agent_exists(mock_client, "user123", "Alice")  # noqa: SLF001

            assert result == "new-agent-id"


class TestPipe:
    """Tests for main pipe method."""

    def test_missing_user(self):
        """Test error when no user context."""
        pipeline = Pipeline()

        result = pipeline.pipe(
            user_message="Hello",
            model_id="test",
            messages=[],
            body={},
            __user__=None,
        )

        assert "Error" in result
        assert "user" in result.lower()

    def test_missing_user_id(self):
        """Test error when user has no id."""
        pipeline = Pipeline()

        result = pipeline.pipe(
            user_message="Hello",
            model_id="test",
            messages=[],
            body={},
            __user__={"name": "Test"},  # No id
        )

        assert "Error" in result

    @patch("httpx.Client")
    def test_successful_chat(self, mock_client_class):
        """Test successful message flow."""
        pipeline = Pipeline()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        # Mock agent exists
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"agents": [{"agent_id": "agent-123", "agent_type": "tutor"}]}
        mock_client.get.return_value = mock_get

        # Mock chat response
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"response": "Hello! I'm here to help."}
        mock_client.post.return_value = mock_post

        result = pipeline.pipe(
            user_message="Hello!",
            model_id="test",
            messages=[],
            body={},
            __user__={"id": "user123", "name": "Alice"},
            __metadata__={"chat_id": "chat-456"},
        )

        assert result == "Hello! I'm here to help."

    @patch("httpx.Client")
    def test_agent_creation_failure(self, mock_client_class):
        """Test error handling when agent creation fails."""
        pipeline = Pipeline()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        # Mock no existing agents
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"agents": []}
        mock_client.get.return_value = mock_get

        # Mock failed creation
        mock_post = MagicMock()
        mock_post.status_code = 500
        mock_post.text = "Internal error"
        mock_client.post.return_value = mock_post

        result = pipeline.pipe(
            user_message="Hello!",
            model_id="test",
            messages=[],
            body={},
            __user__={"id": "user123"},
        )

        assert "Error" in result

    @patch("httpx.Client")
    def test_timeout_handling(self, mock_client_class):
        """Test timeout error handling during chat."""
        import httpx

        pipeline = Pipeline()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        # Agent exists (no timeout here)
        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {"agents": [{"agent_id": "agent-123", "agent_type": "tutor"}]}
        mock_client.get.return_value = mock_get

        # Timeout on chat request
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        result = pipeline.pipe(
            user_message="Hello!",
            model_id="test",
            messages=[],
            body={},
            __user__={"id": "user123"},
        )

        assert "timed out" in result.lower()
