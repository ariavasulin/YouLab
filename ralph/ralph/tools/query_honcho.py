"""Query Honcho tool for OpenHands agent."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import structlog

log = structlog.get_logger()

# Chat ID -> User ID mapping (set when conversation created)
_user_context: dict[str, str] = {}


def set_user_context(chat_id: str, user_id: str) -> None:
    """Set user context for a conversation."""
    _user_context[chat_id] = user_id


def _get_base_class() -> type[Any]:
    """Get BaseTool class, with fallback for testing."""
    try:
        from openhands.tools.base import BaseTool

        return BaseTool
    except ImportError:
        # Fallback for testing without OpenHands installed
        return object


class QueryHonchoTool(_get_base_class()):
    """
    Query Honcho for insights about the current student.

    Use this to understand:
    - Student learning patterns and preferences
    - Historical context from past conversations
    - What approaches have worked before
    - Student's current struggles or goals
    """

    name: ClassVar[str] = "query_honcho"
    description: ClassVar[str] = """Query for insights about the current student based on their conversation history.

    Args:
        question: Natural language question about the student.
                  Examples:
                  - "What learning style works best for this student?"
                  - "What has this student been working on recently?"
                  - "What does this student struggle with?"
                  - "What motivates this student?"

    Returns:
        Insight about the student based on their conversation history,
        or an error message if unavailable.
    """

    def __call__(self, question: str, **kwargs: Any) -> str:
        """Execute the tool."""
        # Get user_id from context
        # OpenHands passes conversation context, we need to extract chat_id
        chat_id = kwargs.get("conversation_id")
        user_id = _user_context.get(chat_id) if chat_id else None

        if not user_id:
            # Fallback: try to find any user context (single user case)
            if len(_user_context) == 1:
                user_id = next(iter(_user_context.values()))
            else:
                return "Unable to identify current student. Cannot query history."

        # Query Honcho
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        from ralph.honcho import get_honcho

        result = loop.run_until_complete(get_honcho().query_dialectic(user_id, question))

        if result is None:
            return "No conversation history available yet. This may be a new student."

        return result.insight
