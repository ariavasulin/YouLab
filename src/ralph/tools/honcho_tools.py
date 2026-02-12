"""Honcho tools for Agno agents."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from agno.run import RunContext  # noqa: TC002 - must be available at runtime for Agno
from agno.tools import Toolkit

from ralph.honcho import get_honcho

logger = logging.getLogger(__name__)

_LOG_PREVIEW_LENGTH = 200


class HonchoTools(Toolkit):
    """
    Toolkit for querying Honcho about students.

    This toolkit provides tools for the agent to query Honcho's dialectic
    system for insights about the current student based on their conversation
    history and context.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize HonchoTools."""
        tools = [self.query_student]
        super().__init__(name="honcho_tools", tools=tools, **kwargs)

    def query_student(self, run_context: RunContext, question: str) -> str:
        """
        Query Honcho for insights about the current student.

        Use this tool when you need to understand the student better, recall
        previous interactions, or get context about their learning journey.

        Args:
            run_context: Agno run context with user_id and session info.
            question: A natural language question about the student.
                     Examples: "What topics has this student struggled with?",
                     "What is their learning style?", "What were we discussing last time?"

        Returns:
            Insights about the student from Honcho's dialectic system,
            or an error message if the query fails.

        """
        # Get user_id from RunContext (injected by Agno)
        user_id = run_context.user_id
        if not user_id:
            # Fallback: try dependencies
            deps = run_context.dependencies or {}
            user_id = deps.get("user_id")

        if not user_id:
            return "Unable to identify student. No user context available."

        logger.info("Querying Honcho for user %s: %s", user_id, question)

        try:
            # Run async query in sync context (Agno tools are sync by default)
            honcho = get_honcho()

            # Create event loop if needed (tool may be called from sync context)
            try:
                asyncio.get_running_loop()
                # If we're in an async context, use thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run, honcho.query_dialectic(user_id, question)
                    ).result(timeout=30)
            except RuntimeError:
                # No running loop, can use asyncio.run directly
                result = asyncio.run(honcho.query_dialectic(user_id, question))

            if result is None:
                logger.debug("Dialectic returned None for user %s", user_id)
                return "No insights available for this student yet."

            preview = (
                result.insight[:_LOG_PREVIEW_LENGTH]
                if len(result.insight) > _LOG_PREVIEW_LENGTH
                else result.insight
            )
            logger.debug("Dialectic response for user %s: %s", user_id, preview)
            return result.insight

        except Exception as e:
            logger.warning("Honcho query failed: %s", e)
            return f"Unable to retrieve student insights: {e!s}"
