"""FastAPI router for strategy agent endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from letta_starter.server.strategy.manager import StrategyManager
from letta_starter.server.strategy.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    SearchDocumentsResponse,
    UploadDocumentRequest,
    UploadDocumentResponse,
)

log = structlog.get_logger()

router = APIRouter()

# Module-level manager instance, initialized by init_strategy_manager
_strategy_manager: StrategyManager | None = None


def init_strategy_manager(letta_base_url: str) -> StrategyManager:
    """Initialize the strategy manager. Called during app startup."""
    global _strategy_manager
    _strategy_manager = StrategyManager(letta_base_url=letta_base_url)
    return _strategy_manager


def get_strategy_manager() -> StrategyManager:
    """Get the strategy manager instance. Used as FastAPI dependency."""
    if _strategy_manager is None:
        raise RuntimeError("Strategy manager not initialized")
    return _strategy_manager


# Type alias for dependency injection
StrategyManagerDep = Annotated[StrategyManager, Depends(get_strategy_manager)]


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: UploadDocumentRequest,
    manager: StrategyManagerDep,
) -> UploadDocumentResponse:
    """Upload a document to the strategy agent's archival memory."""
    try:
        manager.upload_document(content=request.content, tags=request.tags)
        return UploadDocumentResponse(success=True)
    except Exception as e:
        log.exception("document_upload_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload document - Letta may be unavailable",
        ) from None


@router.post("/ask")
async def ask(
    request: AskRequest,
    manager: StrategyManagerDep,
) -> AskResponse:
    """Ask the strategy agent a question."""
    try:
        response_text = manager.ask(request.question)
        return AskResponse(
            response=response_text if response_text else "No response from strategy agent."
        )
    except Exception as e:
        log.exception("strategy_ask_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to query strategy agent - Letta may be unavailable",
        ) from None


@router.get("/documents")
async def search_documents(
    query: str,
    manager: StrategyManagerDep,
    limit: int = 5,
) -> SearchDocumentsResponse:
    """Search the strategy agent's archival memory."""
    try:
        documents = manager.search_documents(query=query, limit=limit)
        return SearchDocumentsResponse(documents=documents)
    except Exception as e:
        log.exception("document_search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to search documents - Letta may be unavailable",
        ) from None


@router.get("/health")
async def health(
    manager: StrategyManagerDep,
) -> HealthResponse:
    """Check strategy agent health."""
    agent_exists = manager.check_agent_exists()
    return HealthResponse(
        status="ready" if agent_exists else "not_ready",
        agent_exists=agent_exists,
    )
