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
    """
    Generate knowledge base name for a user.

    Args:
        user_id: User ID.
        prefix: Name prefix (default: "workspace").

    Returns:
        Knowledge base name like "workspace-{user_id}".

    """
    return f"{prefix}-{user_id}"


class KnowledgeService:
    """Service for managing per-user knowledge bases."""

    def __init__(
        self,
        openwebui_client: OpenWebUIClient,
        name_prefix: str = "workspace",
    ) -> None:
        """
        Initialize service.

        Args:
            openwebui_client: OpenWebUI API client.
            name_prefix: Prefix for knowledge base names.

        """
        self.client = openwebui_client
        self.name_prefix = name_prefix
        # In-memory cache of user -> knowledge_id
        self._cache: dict[str, str] = {}

    async def get_or_create_knowledge(self, user_id: str) -> str:
        """
        Get or create knowledge base for user.

        Args:
            user_id: User ID.

        Returns:
            Knowledge base ID.

        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        name = get_knowledge_name(user_id, self.name_prefix)
        kb = await self.client.get_or_create_knowledge(name)
        kb_id = kb["id"]

        # Cache the result
        self._cache[user_id] = kb_id
        log.info("knowledge_base_resolved", user_id=user_id, kb_id=kb_id, name=name)

        return kb_id

    async def get_knowledge_id(self, user_id: str) -> str | None:
        """
        Get knowledge base ID for user if it exists.

        Args:
            user_id: User ID.

        Returns:
            Knowledge base ID or None if not found.

        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        name = get_knowledge_name(user_id, self.name_prefix)

        try:
            kbs = await self.client.list_knowledge()
            for kb in kbs:
                if kb.get("name") == name:
                    kb_id = kb["id"]
                    self._cache[user_id] = kb_id
                    return kb_id
        except Exception as e:
            log.warning("list_knowledge_failed", error=str(e))

        return None

    def clear_cache(self, user_id: str | None = None) -> None:
        """
        Clear knowledge ID cache.

        Args:
            user_id: Specific user to clear, or None to clear all.

        """
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()
