"""Honcho message persistence and dialectic queries."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from typing import Any

    from honcho import Honcho

from ralph.config import settings

# Optional structlog - fall back to print for OpenWebUI environment
try:
    import structlog

    log = structlog.get_logger()
except ImportError:

    class _PrintLogger:
        def info(self, msg: str, **kwargs: Any) -> None:
            print(f"[INFO] {msg}: {kwargs}")

        def error(self, msg: str, **kwargs: Any) -> None:
            print(f"[ERROR] {msg}: {kwargs}")

        def warning(self, msg: str, **kwargs: Any) -> None:
            print(f"[WARNING] {msg}: {kwargs}")

    log = _PrintLogger()  # type: ignore[assignment]


@dataclass
class DialecticResponse:
    """Response from Honcho dialectic query."""

    insight: str
    query: str


class HonchoClient:
    """
    Minimal Honcho client for Ralph.

    Architecture:
    - Workspace: settings.honcho_workspace_id
    - Student peer: "student_{user_id}"
    - Tutor peer: "tutor"
    - Session: "chat_{chat_id}"
    """

    def __init__(self) -> None:
        self._client: Honcho | None = None
        self._initialized = False

    @property
    def client(self) -> Honcho | None:
        """Lazy-load Honcho client."""
        if self._client is None and not self._initialized:
            self._initialized = True
            try:
                from honcho import Honcho

                env = cast(
                    "Literal['local', 'production', 'demo']",
                    settings.honcho_environment,
                )
                if env in ("demo", "local"):
                    self._client = Honcho(
                        workspace_id=settings.honcho_workspace_id,
                        environment=env,
                    )
                else:
                    self._client = Honcho(
                        workspace_id=settings.honcho_workspace_id,
                        api_key=settings.honcho_api_key,
                        environment=env,
                    )
                log.info("honcho_initialized", workspace=settings.honcho_workspace_id)
            except Exception as e:
                log.warning("honcho_init_failed", error=str(e))
        return self._client

    async def persist_message(
        self,
        user_id: str,
        chat_id: str,
        message: str,
        is_user: bool,
    ) -> None:
        """Persist a message to Honcho."""
        if self.client is None:
            return

        try:
            peer_id = f"student_{user_id}" if is_user else "tutor"
            peer = self.client.peer(peer_id)
            session = self.client.session(f"chat_{chat_id}")

            metadata: dict[str, object] = {"chat_id": chat_id, "user_id": user_id}
            session.add_messages([peer.message(message, metadata=metadata)])

            log.debug("message_persisted", user_id=user_id, chat_id=chat_id, is_user=is_user)
        except Exception as e:
            log.warning("persist_failed", error=str(e), user_id=user_id)

    async def query_dialectic(self, user_id: str, question: str) -> DialecticResponse | None:
        """Query Honcho for insights about a student."""
        if self.client is None:
            return None

        try:
            peer = self.client.peer(f"student_{user_id}")
            response = peer.chat(question)

            if response is None:
                return None

            insight = (
                response
                if isinstance(response, str)
                else str(getattr(response, "content", response))
            )

            log.info("dialectic_queried", user_id=user_id, question=question[:50])
            return DialecticResponse(insight=insight, query=question)
        except Exception as e:
            log.warning("dialectic_failed", error=str(e), user_id=user_id)
            return None


# Singleton instance
_honcho: HonchoClient | None = None


def get_honcho() -> HonchoClient:
    """Get or create Honcho client singleton."""
    global _honcho
    if _honcho is None:
        _honcho = HonchoClient()
    return _honcho


def persist_message_fire_and_forget(
    user_id: str,
    chat_id: str,
    message: str,
    is_user: bool,
) -> None:
    """Fire-and-forget message persistence."""
    if not chat_id:
        return

    async def _persist() -> None:
        await get_honcho().persist_message(user_id, chat_id, message, is_user)

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_persist())
        del task  # Fire-and-forget, we don't need to await
    except RuntimeError:
        # No running loop, run synchronously
        asyncio.run(_persist())
