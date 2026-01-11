"""
Langfuse tracing for the HTTP service.

This is a minimal stub for TDD. Tests should fail until implementation is complete.
"""

import contextlib
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from langfuse import Langfuse

from youlab_server.config.settings import ServiceSettings

# Module-level settings instance (can be patched in tests)
settings = ServiceSettings()

# Lazy-loaded Langfuse client
_langfuse: Langfuse | None = None


def get_langfuse() -> Langfuse | None:
    """Get or create Langfuse client."""
    global _langfuse

    if not settings.langfuse_enabled:
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    if _langfuse is None:
        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    return _langfuse


@contextmanager
def trace_chat(
    user_id: str,
    agent_id: str,
    chat_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing a chat request."""
    trace_id = str(uuid4())
    context: dict[str, Any] = {"trace_id": trace_id}

    langfuse = get_langfuse()
    trace = None

    if langfuse:
        with contextlib.suppress(Exception):
            trace = langfuse.trace(
                id=trace_id,
                name="chat",
                user_id=user_id,
                session_id=chat_id,
                metadata={
                    "agent_id": agent_id,
                    **(metadata or {}),
                },
            )
            context["langfuse_trace"] = trace

    try:
        yield context
    finally:
        if langfuse and trace:
            with contextlib.suppress(Exception):
                langfuse.flush()


def trace_generation(
    trace_context: dict[str, Any],
    name: str,
    input_text: str,
    output_text: str,
    model: str = "letta",
) -> None:
    """Record a generation span within a trace."""
    trace = trace_context.get("langfuse_trace")
    if trace:
        with contextlib.suppress(Exception):
            trace.generation(
                name=name,
                input=input_text,
                output=output_text,
                model=model,
            )
