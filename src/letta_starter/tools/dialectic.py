"""Honcho dialectic query tool for Letta agents."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from letta_starter.honcho.client import HonchoClient

log = structlog.get_logger()

# Global reference set by service initialization
_honcho_client: HonchoClient | None = None
_user_context: dict[str, str] = {}  # agent_id -> user_id mapping


def set_honcho_client(client: HonchoClient | None) -> None:
    """Set the global Honcho client for tool use."""
    global _honcho_client
    _honcho_client = client


def set_user_context(agent_id: str, user_id: str) -> None:
    """Set user context for an agent (called before chat)."""
    _user_context[agent_id] = user_id


def query_honcho(
    question: str,
    session_scope: str = "all",
    agent_state: dict[str, Any] | None = None,  # Letta injects this
) -> str:
    """
    Query Honcho for insights about the current student.

    Use this tool to understand:
    - Student learning patterns and preferences
    - Communication style that works best
    - Historical context from past conversations
    - Engagement patterns and motivations

    Args:
        question: Natural language question about the student
                  (e.g., "What learning style works best for this student?")
        session_scope: Which conversations to include:
                      - "all": All sessions (default)
                      - "recent": Last few sessions
                      - "current": This conversation only
        agent_state: Agent state injected by Letta (contains agent_id)

    Returns:
        Honcho's insight about the student based on conversation history.
        Returns error message if query fails.

    """
    if _honcho_client is None:
        return "Honcho is not available. Proceeding without external insights."

    # Get user_id from agent context
    agent_id = agent_state.get("agent_id") if agent_state else None
    user_id = _user_context.get(agent_id) if agent_id else None

    if not user_id:
        return "Unable to identify current student. Cannot query Honcho."

    from letta_starter.honcho.client import SessionScope

    try:
        scope = SessionScope(session_scope)
    except ValueError:
        scope = SessionScope.ALL

    # Run async query in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        _honcho_client.query_dialectic(
            user_id=user_id,
            question=question,
            session_scope=scope,
        )
    )

    if result is None:
        return "Failed to query Honcho. The service may be temporarily unavailable."

    return result.insight
