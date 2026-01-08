"""Tests for OpenWebUI Pipe."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from letta_starter.pipelines.letta_pipe import Pipe


class TestPipeInit:
    """Tests for Pipe initialization."""

    def test_pipeline_name(self):
        """Test pipeline has correct name."""
        pipeline = Pipe()
        assert pipeline.name == "YouLab Tutor"

    def test_pipeline_has_valves(self):
        """Test pipeline has valves configuration."""
        pipeline = Pipe()
        assert hasattr(pipeline, "valves")
        assert pipeline.valves.LETTA_SERVICE_URL == "http://host.docker.internal:8100"

    def test_valves_default_values(self):
        """Test valves have correct defaults."""
        pipeline = Pipe()
        assert pipeline.valves.AGENT_TYPE == "tutor"
        assert pipeline.valves.ENABLE_LOGGING is True
        assert pipeline.valves.ENABLE_THINKING is True


class TestPipeLifecycle:
    """Tests for pipeline lifecycle methods."""

    @pytest.mark.asyncio
    async def test_on_startup(self, capsys):
        """Test startup handler."""
        pipeline = Pipe()
        await pipeline.on_startup()

        captured = capsys.readouterr()
        assert "YouLab Pipe started" in captured.out

    @pytest.mark.asyncio
    async def test_on_shutdown(self, capsys):
        """Test shutdown handler."""
        pipeline = Pipe()
        await pipeline.on_shutdown()

        captured = capsys.readouterr()
        assert "YouLab Pipe stopped" in captured.out


class TestGetChatTitle:
    """Tests for _get_chat_title method."""

    def test_no_chat_id(self):
        """Test returns None when no chat_id."""
        pipeline = Pipe()
        result = pipeline._get_chat_title(None)  # noqa: SLF001
        assert result is None

    def test_local_chat_id(self):
        """Test returns None for local: prefixed IDs."""
        pipeline = Pipe()
        result = pipeline._get_chat_title("local:some-id")  # noqa: SLF001
        assert result is None

    def test_openwebui_import_error(self):
        """Test handles ImportError gracefully."""
        pipeline = Pipe()
        result = pipeline._get_chat_title("some-chat-id")  # noqa: SLF001
        # Without OpenWebUI, should return None
        assert result is None


class TestSetChatTitle:
    """Tests for _set_chat_title method."""

    def test_no_chat_id(self):
        """Test returns False when no chat_id."""
        pipeline = Pipe()
        result = pipeline._set_chat_title(None, "New Title")  # noqa: SLF001
        assert result is False

    def test_local_chat_id(self):
        """Test returns False for local: prefixed IDs."""
        pipeline = Pipe()
        result = pipeline._set_chat_title("local:some-id", "New Title")  # noqa: SLF001
        assert result is False

    def test_openwebui_import_error(self):
        """Test handles ImportError gracefully."""
        pipeline = Pipe()
        result = pipeline._set_chat_title("some-chat-id", "New Title")  # noqa: SLF001
        # Without OpenWebUI, should return False
        assert result is False

    def test_successful_update(self):
        """Test returns True when update succeeds."""
        pipeline = Pipe()

        mock_chats = MagicMock()
        mock_chats.update_chat_title_by_id.return_value = MagicMock()  # Non-None

        with patch.dict("sys.modules", {"open_webui.models.chats": MagicMock(Chats=mock_chats)}):
            result = pipeline._set_chat_title("chat-123", "New Title")  # noqa: SLF001

        assert result is True
        mock_chats.update_chat_title_by_id.assert_called_once_with("chat-123", "New Title")

    def test_update_returns_none(self):
        """Test returns False when update returns None (chat not found)."""
        pipeline = Pipe()

        mock_chats = MagicMock()
        mock_chats.update_chat_title_by_id.return_value = None

        with patch.dict("sys.modules", {"open_webui.models.chats": MagicMock(Chats=mock_chats)}):
            result = pipeline._set_chat_title("chat-123", "New Title")  # noqa: SLF001

        assert result is False


class TestEnsureAgentExists:
    """Tests for _ensure_agent_exists method."""

    @pytest.mark.asyncio
    async def test_agent_exists(self):
        """Test returns agent_id when agent exists."""
        pipeline = Pipe()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "agents": [{"agent_id": "existing-id", "agent_type": "tutor"}]
        }
        mock_client.get.return_value = mock_response

        result = await pipeline._ensure_agent_exists(mock_client, "user123")  # noqa: SLF001

        assert result == "existing-id"

    @pytest.mark.asyncio
    async def test_agent_created(self):
        """Test creates agent when not exists."""
        pipeline = Pipe()

        mock_client = AsyncMock(spec=httpx.AsyncClient)

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

        result = await pipeline._ensure_agent_exists(mock_client, "user123", "Alice")  # noqa: SLF001

        assert result == "new-agent-id"


class TestPipe:
    """Tests for main pipe method."""

    @pytest.mark.asyncio
    async def test_missing_message(self):
        """Test error when no message in body."""
        pipeline = Pipe()

        result = await pipeline.pipe(
            body={"messages": []},
            __user__={"id": "user123"},
        )

        assert "Error" in result
        assert "message" in result.lower()

    @pytest.mark.asyncio
    async def test_missing_user(self):
        """Test emits error when no user context."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        result = await pipeline.pipe(
            body={"messages": [{"content": "Hello"}]},
            __user__=None,
            __event_emitter__=mock_emitter,
        )

        assert result == ""
        mock_emitter.assert_called_once()
        call_args = mock_emitter.call_args[0][0]
        assert call_args["type"] == "message"
        assert "user" in call_args["data"]["content"].lower()

    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        """Test emits error when user has no id."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        result = await pipeline.pipe(
            body={"messages": [{"content": "Hello"}]},
            __user__={"name": "Test"},  # No id
            __event_emitter__=mock_emitter,
        )

        assert result == ""
        mock_emitter.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_creation_failure(self):
        """Test error handling when agent creation fails."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
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

            result = await pipeline.pipe(
                body={"messages": [{"content": "Hello!"}]},
                __user__={"id": "user123"},
                __event_emitter__=mock_emitter,
            )

            assert result == ""
            mock_emitter.assert_called_once()
            call_args = mock_emitter.call_args[0][0]
            assert call_args["type"] == "message"
            assert "Error" in call_args["data"]["content"]

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout error handling during streaming."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Agent exists
            mock_get = MagicMock()
            mock_get.status_code = 200
            mock_get.json.return_value = {
                "agents": [{"agent_id": "agent-123", "agent_type": "tutor"}]
            }
            mock_client.get.return_value = mock_get

            # Timeout on stream attempt
            with patch(
                "letta_starter.pipelines.letta_pipe.aconnect_sse",
                side_effect=httpx.TimeoutException("Timeout"),
            ):
                result = await pipeline.pipe(
                    body={"messages": [{"content": "Hello!"}]},
                    __user__={"id": "user123"},
                    __event_emitter__=mock_emitter,
                )

            assert result == ""
            mock_emitter.assert_called_once()
            call_args = mock_emitter.call_args[0][0]
            assert "timed out" in call_args["data"]["content"].lower()

    @pytest.mark.asyncio
    async def test_connect_error_handling(self):
        """Test connection error handling."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Agent exists
            mock_get = MagicMock()
            mock_get.status_code = 200
            mock_get.json.return_value = {
                "agents": [{"agent_id": "agent-123", "agent_type": "tutor"}]
            }
            mock_client.get.return_value = mock_get

            # Connection error on stream attempt
            with patch(
                "letta_starter.pipelines.letta_pipe.aconnect_sse",
                side_effect=httpx.ConnectError("Connection refused"),
            ):
                result = await pipeline.pipe(
                    body={"messages": [{"content": "Hello!"}]},
                    __user__={"id": "user123"},
                    __event_emitter__=mock_emitter,
                )

            assert result == ""
            mock_emitter.assert_called_once()
            call_args = mock_emitter.call_args[0][0]
            assert "connect" in call_args["data"]["content"].lower()


class TestHandleSSEEvent:
    """Tests for _handle_sse_event method."""

    @pytest.mark.asyncio
    async def test_status_event(self):
        """Test handling status event."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        await pipeline._handle_sse_event(  # noqa: SLF001
            '{"type": "status", "content": "Thinking..."}',
            mock_emitter,
        )

        mock_emitter.assert_called_once()
        call_args = mock_emitter.call_args[0][0]
        assert call_args["type"] == "status"
        assert call_args["data"]["description"] == "Thinking..."
        assert call_args["data"]["done"] is False

    @pytest.mark.asyncio
    async def test_message_event(self):
        """Test handling message event."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        await pipeline._handle_sse_event(  # noqa: SLF001
            '{"type": "message", "content": "Hello there!"}',
            mock_emitter,
        )

        mock_emitter.assert_called_once()
        call_args = mock_emitter.call_args[0][0]
        assert call_args["type"] == "message"
        assert call_args["data"]["content"] == "Hello there!"

    @pytest.mark.asyncio
    async def test_done_event(self):
        """Test handling done event."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        await pipeline._handle_sse_event(  # noqa: SLF001
            '{"type": "done"}',
            mock_emitter,
        )

        mock_emitter.assert_called_once()
        call_args = mock_emitter.call_args[0][0]
        assert call_args["type"] == "status"
        assert call_args["data"]["done"] is True

    @pytest.mark.asyncio
    async def test_error_event(self):
        """Test handling error event."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        await pipeline._handle_sse_event(  # noqa: SLF001
            '{"type": "error", "message": "Something went wrong"}',
            mock_emitter,
        )

        mock_emitter.assert_called_once()
        call_args = mock_emitter.call_args[0][0]
        assert call_args["type"] == "message"
        assert "Something went wrong" in call_args["data"]["content"]

    @pytest.mark.asyncio
    async def test_invalid_json(self, capsys):
        """Test handling invalid JSON gracefully."""
        pipeline = Pipe()
        mock_emitter = AsyncMock()

        await pipeline._handle_sse_event(  # noqa: SLF001
            "not valid json",
            mock_emitter,
        )

        mock_emitter.assert_not_called()
        captured = capsys.readouterr()
        assert "Failed to parse SSE" in captured.out

    @pytest.mark.asyncio
    async def test_no_emitter(self):
        """Test returns early when no emitter provided."""
        pipeline = Pipe()

        # Should not raise
        await pipeline._handle_sse_event(  # noqa: SLF001
            '{"type": "message", "content": "test"}',
            None,
        )
