"""OpenHands SDK wrapper for Ralph."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

from ralph.config import settings

log = structlog.get_logger()


class OpenHandsManager:
    """
    Manages OpenHands workspaces and conversations.

    Architecture:
    - One workspace per user: {user_data_dir}/{user_id}/workspace/
    - One conversation per chat: {conversations_dir}/{user_id}/{chat_id}/
    - Workspace persists across chats (files survive)
    - Conversation is fresh per chat (context resets)
    """

    def __init__(self) -> None:
        self._conversations: dict[str, Any] = {}  # chat_id -> Conversation

    def _get_workspace_path(self, user_id: str) -> Path:
        """Get or create user workspace directory."""
        workspace = Path(settings.user_data_dir) / user_id / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _get_conversation_path(self, user_id: str, chat_id: str) -> Path:
        """Get conversation persistence directory."""
        conv_dir = Path(settings.conversations_dir) / user_id / chat_id
        conv_dir.mkdir(parents=True, exist_ok=True)
        return conv_dir

    def get_or_create_conversation(
        self,
        user_id: str,
        chat_id: str,
        callback: Callable[..., Any] | None = None,
    ) -> Any:
        """
        Get existing conversation or create new one.

        Each chat_id maps to one conversation. Workspace is shared across
        all conversations for a user.

        Returns the OpenHands Conversation object.
        """
        if chat_id in self._conversations:
            return self._conversations[chat_id]

        # Lazy import OpenHands to avoid import errors when SDK not installed
        try:
            from openhands.sdk import LLM, Agent, Conversation, Tool
            from openhands.tools.file_editor import FileEditorTool
            from openhands.tools.terminal import TerminalTool
        except ImportError as e:
            log.error("openhands_import_failed", error=str(e))
            raise RuntimeError(
                "OpenHands SDK not installed. Install with: pip install openhands-ai"
            ) from e

        # Create LLM with OpenRouter
        llm = LLM(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        # Create agent with standard tools + custom query_honcho
        from ralph.tools.query_honcho import QueryHonchoTool

        agent = Agent(
            llm=llm,
            tools=[
                Tool(name=TerminalTool.name),
                Tool(name=FileEditorTool.name),
                Tool(name=QueryHonchoTool.name),
            ],
        )

        # Create conversation with persistence
        workspace_path = self._get_workspace_path(user_id)
        persistence_path = self._get_conversation_path(user_id, chat_id)

        callbacks = [callback] if callback else []

        conversation = Conversation(
            agent=agent,
            workspace=str(workspace_path),
            persistence_dir=str(persistence_path),
            conversation_id=chat_id,
            callbacks=callbacks,
        )

        # Store user context for query_honcho tool
        from ralph.tools.query_honcho import set_user_context

        set_user_context(chat_id, user_id)

        self._conversations[chat_id] = conversation
        log.info(
            "conversation_created",
            user_id=user_id,
            chat_id=chat_id,
            workspace=str(workspace_path),
        )

        return conversation

    def cleanup_conversation(self, chat_id: str) -> None:
        """Remove conversation from memory (persistence remains on disk)."""
        if chat_id in self._conversations:
            del self._conversations[chat_id]
            log.debug("conversation_cleaned", chat_id=chat_id)


# Singleton instance
_manager: OpenHandsManager | None = None


def get_manager() -> OpenHandsManager:
    """Get or create OpenHands manager singleton."""
    global _manager
    if _manager is None:
        _manager = OpenHandsManager()
    return _manager
