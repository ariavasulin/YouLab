"""Tests for Langfuse tracing."""

from unittest.mock import MagicMock, patch

from letta_starter.server.tracing import (
    get_langfuse,
    trace_chat,
    trace_generation,
)


class TestGetLangfuse:
    """Tests for get_langfuse function."""

    def test_disabled_returns_none(self):
        """Test None returned when Langfuse disabled."""
        with patch("letta_starter.server.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False
            mock_settings.langfuse_public_key = "pk_test"
            mock_settings.langfuse_secret_key = "sk_test"  # noqa: S105

            # Reset singleton
            import letta_starter.server.tracing as tracing_module

            tracing_module._langfuse = None

            result = get_langfuse()

            assert result is None

    def test_missing_keys_returns_none(self):
        """Test None returned when keys missing."""
        with patch("letta_starter.server.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = None
            mock_settings.langfuse_secret_key = None

            # Reset singleton
            import letta_starter.server.tracing as tracing_module

            tracing_module._langfuse = None

            result = get_langfuse()

            assert result is None

    def test_creates_client_with_keys(self):
        """Test Langfuse client created with valid keys."""
        with (
            patch("letta_starter.server.tracing.settings") as mock_settings,
            patch("letta_starter.server.tracing.Langfuse") as mock_langfuse,
        ):
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk_test"
            mock_settings.langfuse_secret_key = "sk_test"  # noqa: S105
            mock_settings.langfuse_host = "https://cloud.langfuse.com"

            # Reset singleton
            import letta_starter.server.tracing as tracing_module

            tracing_module._langfuse = None

            get_langfuse()

            mock_langfuse.assert_called_once_with(
                public_key="pk_test",
                secret_key="sk_test",  # noqa: S106
                host="https://cloud.langfuse.com",
            )


class TestTraceChatContext:
    """Tests for trace_chat context manager."""

    def test_returns_trace_id(self):
        """Test context includes trace_id."""
        with (
            patch("letta_starter.server.tracing.get_langfuse", return_value=None),
            trace_chat(
                user_id="user123",
                agent_id="agent-123",
            ) as ctx,
        ):
            assert "trace_id" in ctx
            assert isinstance(ctx["trace_id"], str)

    def test_creates_trace_when_enabled(self):
        """Test Langfuse trace created when enabled."""
        mock_langfuse = MagicMock()
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace

        with (
            patch("letta_starter.server.tracing.get_langfuse", return_value=mock_langfuse),
            trace_chat(
                user_id="user123",
                agent_id="agent-123",
                chat_id="chat-456",
            ) as ctx,
        ):
            assert ctx.get("langfuse_trace") == mock_trace

        mock_langfuse.trace.assert_called_once()
        mock_langfuse.flush.assert_called_once()

    def test_graceful_without_langfuse(self):
        """Test works without Langfuse."""
        with (
            patch("letta_starter.server.tracing.get_langfuse", return_value=None),
            trace_chat(
                user_id="user123",
                agent_id="agent-123",
            ) as ctx,
        ):
            assert "trace_id" in ctx
            assert "langfuse_trace" not in ctx

    def test_handles_trace_exception(self):
        """Test handles Langfuse errors gracefully."""
        mock_langfuse = MagicMock()
        mock_langfuse.trace.side_effect = Exception("Connection error")

        # Should not raise
        with (
            patch("letta_starter.server.tracing.get_langfuse", return_value=mock_langfuse),
            trace_chat(
                user_id="user123",
                agent_id="agent-123",
            ) as ctx,
        ):
            assert "trace_id" in ctx


class TestTraceGeneration:
    """Tests for trace_generation function."""

    def test_records_generation(self):
        """Test generation recorded to trace."""
        mock_trace = MagicMock()
        context = {"langfuse_trace": mock_trace}

        trace_generation(
            trace_context=context,
            name="agent_response",
            input_text="Hello!",
            output_text="Hi there!",
        )

        mock_trace.generation.assert_called_once_with(
            name="agent_response",
            input="Hello!",
            output="Hi there!",
            model="letta",
        )

    def test_no_trace_in_context(self):
        """Test handles missing trace gracefully."""
        context = {}

        # Should not raise
        trace_generation(
            trace_context=context,
            name="agent_response",
            input_text="Hello!",
            output_text="Hi there!",
        )

    def test_handles_generation_exception(self):
        """Test handles generation errors gracefully."""
        mock_trace = MagicMock()
        mock_trace.generation.side_effect = Exception("API error")
        context = {"langfuse_trace": mock_trace}

        # Should not raise
        trace_generation(
            trace_context=context,
            name="agent_response",
            input_text="Hello!",
            output_text="Hi there!",
        )
