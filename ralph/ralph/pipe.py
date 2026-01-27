"""
Ralph Wiggum pipe for OpenWebUI.

title: Ralph Wiggum
description: Claude Code-like experience with OpenHands sandbox
version: 0.1.0
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = structlog.get_logger()


class Pipe:
    """OpenWebUI Pipe for Ralph - OpenHands integration with streaming."""

    class Valves:
        """Configuration exposed in OpenWebUI admin."""

        def __init__(self) -> None:
            self.ENABLE_LOGGING: bool = True

    def __init__(self) -> None:
        self.name = "Ralph Wiggum"
        self.valves = self.Valves()
        self._response_buffer: str = ""

    async def on_startup(self) -> None:
        """Initialize on startup."""
        if self.valves.ENABLE_LOGGING:
            print("Ralph Pipe started")

    async def on_shutdown(self) -> None:
        """Cleanup on shutdown."""
        if self.valves.ENABLE_LOGGING:
            print("Ralph Pipe stopped")

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message with streaming."""
        from ralph.honcho import persist_message_fire_and_forget
        from ralph.openhands_client import get_manager

        # Extract message
        messages = body.get("messages", [])
        user_message = messages[-1].get("content", "") if messages else ""

        if not user_message:
            return "Error: No message provided."

        # Extract user info
        user_id = __user__.get("id") if __user__ else None

        if not user_id:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: Could not identify user. Please log in."},
                    }
                )
            return ""

        # Get chat context
        chat_id = __metadata__.get("chat_id") if __metadata__ else None

        if not chat_id:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: No chat context available."},
                    }
                )
            return ""

        if self.valves.ENABLE_LOGGING:
            print(f"Ralph: user={user_id}, chat={chat_id}")

        # Persist user message
        persist_message_fire_and_forget(user_id, chat_id, user_message, is_user=True)

        # Reset response buffer
        self._response_buffer = ""

        # Create streaming callback
        async def stream_callback(event: Any) -> None:
            """Handle OpenHands events and stream to OpenWebUI."""
            if __event_emitter__ is None:
                return

            event_type = getattr(event, "type", None)

            if event_type == "message" and hasattr(event, "message"):
                # Agent message - stream it
                content = event.message
                self._response_buffer += content
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": content},
                    }
                )

            elif event_type == "observation":
                # Tool output - show as status
                if hasattr(event, "content"):
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": f"Running: {event.content[:100]}...",
                                "done": False,
                            },
                        }
                    )

        try:
            # Get or create conversation
            manager = get_manager()
            conversation = manager.get_or_create_conversation(
                user_id=user_id,
                chat_id=chat_id,
                callback=stream_callback,
            )

            # Send message and run
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Thinking...", "done": False},
                    }
                )

            conversation.send_message(user_message)

            # Run conversation (this will trigger callbacks)
            import asyncio

            await asyncio.to_thread(conversation.run)

            # Mark complete
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Complete", "done": True},
                    }
                )

            # Persist agent response
            if self._response_buffer:
                persist_message_fire_and_forget(
                    user_id, chat_id, self._response_buffer, is_user=False
                )

        except Exception as e:
            error_msg = str(e)
            if self.valves.ENABLE_LOGGING:
                print(f"Ralph error: {error_msg}")
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": f"Error: {error_msg}"},
                    }
                )

        return ""
