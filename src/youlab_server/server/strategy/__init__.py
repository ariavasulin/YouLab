"""Strategy agent package - RAG-enabled project knowledge assistant."""

from youlab_server.server.strategy.manager import StrategyManager
from youlab_server.server.strategy.router import (
    get_strategy_manager,
    init_strategy_manager,
    router,
)
from youlab_server.server.strategy.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    SearchDocumentsResponse,
    UploadDocumentRequest,
    UploadDocumentResponse,
)

__all__ = [
    "AskRequest",
    "AskResponse",
    "HealthResponse",
    "SearchDocumentsResponse",
    "StrategyManager",
    "UploadDocumentRequest",
    "UploadDocumentResponse",
    "get_strategy_manager",
    "init_strategy_manager",
    "router",
]
