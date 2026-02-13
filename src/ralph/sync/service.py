"""Process-level sync service singleton."""

from __future__ import annotations

import structlog

from ralph.config import get_settings
from ralph.sync.knowledge import KnowledgeService
from ralph.sync.openwebui_client import OpenWebUIClient

log = structlog.get_logger()

_client: OpenWebUIClient | None = None
_knowledge: KnowledgeService | None = None


def get_sync_client() -> OpenWebUIClient | None:
    """Get or create process-level OpenWebUI client."""
    global _client
    settings = get_settings()
    if not settings.openwebui_url or not settings.openwebui_api_key:
        return None
    if not settings.sync_to_openwebui:
        return None
    if _client is None:
        _client = OpenWebUIClient(
            base_url=settings.openwebui_url,
            api_key=settings.openwebui_api_key,
        )
        log.info("sync_client_created", base_url=settings.openwebui_url)
    return _client


def get_knowledge_service() -> KnowledgeService | None:
    """Get or create process-level knowledge service."""
    global _knowledge
    client = get_sync_client()
    if client is None:
        return None
    if _knowledge is None:
        settings = get_settings()
        _knowledge = KnowledgeService(
            openwebui_client=client,
            name_prefix=settings.sync_knowledge_prefix,
        )
    return _knowledge


async def close_sync_client() -> None:
    """Close the singleton client. Call on shutdown."""
    global _client, _knowledge
    if _client:
        await _client.close()
        _client = None
    _knowledge = None
