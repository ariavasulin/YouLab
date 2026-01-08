"""Honcho client for message persistence and dialectic queries."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from asyncio import Task

    from honcho import Honcho

log = structlog.get_logger()


class SessionScope(str, Enum):
    """Scope for dialectic queries."""

    ALL = "all"  # All sessions for this user
    RECENT = "recent"  # Last N sessions
    CURRENT = "current"  # Current/active session only
    SPECIFIC = "specific"  # Explicit session ID


@dataclass
class DialecticResponse:
    """Structured response from Honcho dialectic."""

    insight: str
    session_scope: SessionScope
    query: str


# Keep references to background tasks to prevent garbage collection
_background_tasks: set[Task[None]] = set()


class HonchoClient:
    """
    Manages Honcho peers and sessions for YouLab message persistence.

    Architecture:
    - One workspace: "youlab"
    - One peer per student: "student_{user_id}"
    - One shared tutor peer: "tutor"
    - One session per OpenWebUI chat: "chat_{chat_id}"
    """

    def __init__(
        self,
        workspace_id: str,
        api_key: str | None = None,
        environment: str = "demo",
    ) -> None:
        """
        Initialize Honcho client.

        Args:
            workspace_id: Honcho workspace identifier
            api_key: API key for production (None for demo/local)
            environment: "demo", "local", or "production"

        """
        self.workspace_id = workspace_id
        self.api_key = api_key
        self.environment = environment
        self._client: Honcho | None = None
        self._tutor_peer_id = "tutor"
        self._initialized = False

    @property
    def client(self) -> Honcho | None:
        """
        Lazy-load Honcho client.

        Returns None if initialization fails (e.g., network unreachable).
        """
        if self._client is None and not self._initialized:
            self._initialized = True
            try:
                from honcho import Honcho

                if self.environment in ("demo", "local"):
                    self._client = Honcho(
                        workspace_id=self.workspace_id,
                        environment=self.environment,  # type: ignore[arg-type]
                    )
                else:
                    self._client = Honcho(
                        workspace_id=self.workspace_id,
                        api_key=self.api_key,
                        environment=self.environment,  # type: ignore[arg-type]
                    )
                log.info(
                    "honcho_client_initialized",
                    workspace_id=self.workspace_id,
                    environment=self.environment,
                )
            except Exception as e:
                log.warning(
                    "honcho_client_init_failed",
                    error=str(e),
                    workspace_id=self.workspace_id,
                    environment=self.environment,
                )
                self._client = None
        return self._client

    def _get_student_peer_id(self, user_id: str) -> str:
        """Generate peer ID for a student."""
        return f"student_{user_id}"

    def _get_session_id(self, chat_id: str) -> str:
        """Generate session ID from OpenWebUI chat ID."""
        return f"chat_{chat_id}"

    async def persist_user_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        chat_title: str | None = None,
        agent_type: str = "tutor",
    ) -> None:
        """
        Persist a user message to Honcho.

        Args:
            user_id: OpenWebUI user identifier
            chat_id: OpenWebUI chat identifier
            message: User message content
            chat_title: Optional chat title for metadata
            agent_type: Type of agent (for metadata)

        """
        if self.client is None:
            return

        try:
            student_peer = self.client.peer(self._get_student_peer_id(user_id))
            session = self.client.session(self._get_session_id(chat_id))

            metadata: dict[str, object] = {
                "chat_id": chat_id,
                "agent_type": agent_type,
            }
            if chat_title:
                metadata["chat_title"] = chat_title

            session.add_messages([student_peer.message(message, metadata=metadata)])

            log.debug(
                "honcho_user_message_persisted",
                user_id=user_id,
                chat_id=chat_id,
                message_length=len(message),
            )
        except Exception as e:
            log.warning(
                "honcho_persist_failed",
                error=str(e),
                user_id=user_id,
                chat_id=chat_id,
                message_type="user",
            )

    async def persist_agent_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        chat_title: str | None = None,
        agent_type: str = "tutor",
    ) -> None:
        """
        Persist an agent response to Honcho.

        Args:
            user_id: OpenWebUI user identifier (for session context)
            chat_id: OpenWebUI chat identifier
            message: Agent response content
            chat_title: Optional chat title for metadata
            agent_type: Type of agent that responded

        """
        if self.client is None:
            return

        try:
            tutor_peer = self.client.peer(self._tutor_peer_id)
            session = self.client.session(self._get_session_id(chat_id))

            metadata: dict[str, object] = {
                "chat_id": chat_id,
                "agent_type": agent_type,
                "user_id": user_id,  # Track which student this was for
            }
            if chat_title:
                metadata["chat_title"] = chat_title

            session.add_messages([tutor_peer.message(message, metadata=metadata)])

            log.debug(
                "honcho_agent_message_persisted",
                user_id=user_id,
                chat_id=chat_id,
                message_length=len(message),
            )
        except Exception as e:
            log.warning(
                "honcho_persist_failed",
                error=str(e),
                user_id=user_id,
                chat_id=chat_id,
                message_type="agent",
            )

    def check_connection(self) -> bool:
        """
        Check if Honcho is reachable.

        Returns:
            True if connection successful, False otherwise.

        """
        if self.client is None:
            return False
        try:
            # Accessing a peer validates the connection
            _ = self.client.peer("connection_test")
            return True
        except Exception as e:
            log.warning("honcho_connection_check_failed", error=str(e))
            return False

    async def query_dialectic(
        self,
        user_id: str,
        question: str,
        session_scope: SessionScope = SessionScope.ALL,
        session_id: str | None = None,
        recent_limit: int = 5,
    ) -> DialecticResponse | None:
        """
        Query Honcho dialectic for insights about a student.

        Args:
            user_id: Student identifier
            question: Natural language question
            session_scope: Which sessions to include (currently ALL is supported)
            session_id: Specific session ID (reserved for future use)
            recent_limit: Number of recent sessions (reserved for future use)

        Returns:
            DialecticResponse with insight, or None if unavailable

        """
        if self.client is None:
            return None

        try:
            peer = self.client.peer(self._get_student_peer_id(user_id))

            # Honcho peer.chat() queries across all conversation history for this peer
            # Session-scoped filtering will be added when Honcho SDK supports it
            response = peer.chat(question)

            # Handle different return types from peer.chat()
            if response is None:
                log.warning(
                    "honcho_dialectic_empty",
                    user_id=user_id,
                    question_preview=question[:50],
                )
                return None

            # Extract string content from response
            insight: str
            if isinstance(response, str):
                insight = response
            else:
                # DialecticStreamResponse has a 'content' attribute
                insight = str(getattr(response, "content", str(response)))

            log.info(
                "honcho_dialectic_queried",
                user_id=user_id,
                question_preview=question[:50],
                session_scope=session_scope.value,
            )

            return DialecticResponse(
                insight=insight,
                session_scope=session_scope,
                query=question,
            )
        except Exception as e:
            log.warning(
                "honcho_dialectic_failed",
                error=str(e),
                user_id=user_id,
            )
            return None


def create_persist_task(
    honcho_client: HonchoClient | None,
    user_id: str,
    chat_id: str,
    message: str,
    is_user: bool,
    chat_title: str | None = None,
    agent_type: str = "tutor",
) -> None:
    """
    Fire-and-forget message persistence.

    Creates an asyncio task to persist the message without blocking.
    Safe to call even if honcho_client is None.

    Args:
        honcho_client: HonchoClient instance (or None if disabled)
        user_id: OpenWebUI user identifier
        chat_id: OpenWebUI chat identifier
        message: Message content
        is_user: True for user messages, False for agent responses
        chat_title: Optional chat title
        agent_type: Agent type for metadata

    """
    if honcho_client is None:
        return

    if not chat_id:
        log.debug("honcho_persist_skipped", reason="no_chat_id")
        return

    async def _persist() -> None:
        if is_user:
            await honcho_client.persist_user_message(
                user_id=user_id,
                chat_id=chat_id,
                message=message,
                chat_title=chat_title,
                agent_type=agent_type,
            )
        else:
            await honcho_client.persist_agent_message(
                user_id=user_id,
                chat_id=chat_id,
                message=message,
                chat_title=chat_title,
                agent_type=agent_type,
            )

    task = asyncio.create_task(_persist())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
