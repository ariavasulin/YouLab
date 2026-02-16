"""
Knowledge base management service.

Handles per-user knowledge base creation and mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ralph.sync.openwebui_client import OpenWebUIClient

log = structlog.get_logger()


def get_knowledge_name(user_id: str, prefix: str = "workspace") -> str:
    """Generate knowledge base name like "workspace-{user_id}"."""
    return f"{prefix}-{user_id}"


class KnowledgeService:
    """Service for managing per-user knowledge bases."""

    def __init__(
        self,
        openwebui_client: OpenWebUIClient,
        name_prefix: str = "workspace",
    ) -> None:
        self.client = openwebui_client
        self.name_prefix = name_prefix
        self._cache: dict[str, str] = {}

    async def get_or_create_knowledge(self, user_id: str) -> str:
        """Get or create knowledge base for user. Returns KB ID."""
        if user_id in self._cache:
            return self._cache[user_id]

        name = get_knowledge_name(user_id, self.name_prefix)
        kb = await self.client.get_or_create_knowledge(name)
        kb_id = kb["id"]

        self._cache[user_id] = kb_id
        log.info("knowledge_base_resolved", user_id=user_id, kb_id=kb_id, name=name)

        return kb_id
