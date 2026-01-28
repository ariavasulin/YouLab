"""HTTP endpoint for Honcho dialectic queries (called by sandboxed tools)."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from youlab_server.honcho.client import HonchoClient, SessionScope

log = structlog.get_logger()
router = APIRouter(prefix="/honcho", tags=["honcho"])


# Dependency to get Honcho client from app state
def get_honcho_client() -> HonchoClient | None:
    """Get the Honcho client - must be overridden at startup."""
    # This will be replaced by main.py's get_honcho_client via dependency override
    return None


class QueryRequest(BaseModel):
    """Request body for dialectic query."""

    user_id: str = Field(..., description="User ID to query conversations for")
    question: str = Field(..., description="Question to ask about the user")
    session_scope: str = Field(default="all", description="Scope: all, recent, current")


class QueryResponse(BaseModel):
    """Response from dialectic query."""

    insight: str | None = Field(description="Insight from conversation history")
    success: bool = Field(default=True)
    error: str | None = Field(default=None)


@router.post("/query")
async def query_dialectic(
    request: QueryRequest,
    honcho_client: Annotated[HonchoClient | None, Depends(get_honcho_client)],
) -> QueryResponse:
    """
    Query Honcho dialectic for insights about a user.

    Called by sandboxed Letta tools that can't access the Honcho client directly.
    """
    if honcho_client is None:
        return QueryResponse(
            insight=None,
            success=False,
            error="Honcho client not configured",
        )

    try:
        scope = SessionScope(request.session_scope)
    except ValueError:
        scope = SessionScope.ALL

    log.info(
        "honcho_query_via_http",
        user_id=request.user_id,
        question_preview=request.question[:50],
    )

    response = await honcho_client.query_dialectic(
        user_id=request.user_id,
        question=request.question,
        session_scope=scope,
    )

    if response is None:
        return QueryResponse(
            insight=None,
            success=False,
            error="No insight available",
        )

    return QueryResponse(insight=response.insight, success=True)
