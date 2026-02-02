"""
CS-189 Tutor pipe for OpenWebUI.

title: CS-189 Tutor
description: CS-189 Introduction to Machine Learning tutor
version: 0.1.0
"""

import json
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

import httpx
from httpx_sse import aconnect_sse
from pydantic import BaseModel, Field


class Pipe:
    """OpenWebUI Pipe for YouLab tutoring with streaming."""

    class Valves(BaseModel):
        """Configuration options exposed in OpenWebUI admin."""

        LETTA_SERVICE_URL: str = Field(
            default="http://host.docker.internal:8100",
            description="URL of the YouLab Server HTTP service",
        )
        AGENT_TYPE: str = Field(
            default="poc-tutor",
            description="Agent type to use (course_id)",
        )
        ENABLE_LOGGING: bool = Field(
            default=True,
            description="Enable detailed logging",
        )
        ENABLE_THINKING: bool = Field(
            default=True,
            description="Show thinking indicators",
        )

    def __init__(self) -> None:
        self.name = "CS-189 Tutor"
        self.valves = self.Valves()

    async def on_startup(self) -> None:
        if self.valves.ENABLE_LOGGING:
            print(f"YouLab Pipe started. Service: {self.valves.LETTA_SERVICE_URL}")

    async def on_shutdown(self) -> None:
        if self.valves.ENABLE_LOGGING:
            print("YouLab Pipe stopped")

    async def on_valves_updated(self) -> None:
        if self.valves.ENABLE_LOGGING:
            print("YouLab Pipe valves updated")

    def _get_chat_title(self, chat_id: str | None) -> str | None:
        """Get chat title from OpenWebUI database."""
        if not chat_id or chat_id.startswith("local:"):
            return None
        try:
            from open_webui.models.chats import Chats

            chat = Chats.get_chat_by_id(chat_id)
            return chat.title if chat else None
        except ImportError:
            return None
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to get chat title: {e}")
            return None

    def _set_chat_title(self, chat_id: str | None, title: str) -> bool:
        """
        Set chat title in OpenWebUI database.

        Args:
            chat_id: The chat ID to update
            title: The new title to set

        Returns:
            True if successful, False otherwise

        """
        if not chat_id or chat_id.startswith("local:"):
            return False
        try:
            from open_webui.models.chats import Chats

            result = Chats.update_chat_title_by_id(chat_id, title)
            return result is not None
        except ImportError:
            return False
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to set chat title: {e}")
            return False

    async def _ensure_agent_exists(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        user_name: str | None = None,
    ) -> str | None:
        """Ensure agent exists for user, create if needed."""
        try:
            response = await client.get(
                f"{self.valves.LETTA_SERVICE_URL}/agents",
                params={"user_id": user_id},
            )
            if response.status_code == HTTPStatus.OK:
                for agent in response.json().get("agents", []):
                    if agent.get("agent_type") == self.valves.AGENT_TYPE:
                        return agent.get("agent_id")
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to check agents: {e}")

        # Create new agent
        try:
            response = await client.post(
                f"{self.valves.LETTA_SERVICE_URL}/agents",
                json={
                    "user_id": user_id,
                    "agent_type": self.valves.AGENT_TYPE,
                    "user_name": user_name,
                },
            )
            if response.status_code == HTTPStatus.CREATED:
                return response.json().get("agent_id")
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to create agent: {response.text}")
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to create agent: {e}")
        return None

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        """Process a message with streaming."""
        # Extract message from body
        messages = body.get("messages", [])
        user_message = messages[-1].get("content", "") if messages else ""

        if not user_message:
            return "Error: No message provided."

        # Extract user info
        user_id = __user__.get("id") if __user__ else None
        user_name = __user__.get("name") if __user__ else None

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
        chat_title = self._get_chat_title(chat_id)

        if self.valves.ENABLE_LOGGING:
            print(f"YouLab: user={user_id}, chat={chat_id}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                agent_id = await self._ensure_agent_exists(client, user_id, user_name)
                if not agent_id:
                    if __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "message",
                                "data": {"content": "Error: Could not find or create tutor agent."},
                            }
                        )
                    return ""

                # Stream from HTTP service
                async with aconnect_sse(
                    client,
                    "POST",
                    f"{self.valves.LETTA_SERVICE_URL}/chat/stream",
                    json={
                        "agent_id": agent_id,
                        "message": user_message,
                        "chat_id": chat_id,
                        "chat_title": chat_title,
                        "enable_thinking": self.valves.ENABLE_THINKING,
                    },
                ) as event_source:
                    async for sse in event_source.aiter_sse():
                        if sse.data:
                            await self._handle_sse_event(sse.data, __event_emitter__)

        except httpx.TimeoutException:
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "message", "data": {"content": "Error: Request timed out."}}
                )
        except httpx.ConnectError:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": "Error: Could not connect to tutor service."},
                    }
                )
        except Exception as e:
            error_str = str(e)
            # Ignore "incomplete chunked read" - message was already delivered
            if "incomplete chunked read" in error_str or "peer closed" in error_str:
                if self.valves.ENABLE_LOGGING:
                    print("YouLab: stream closed (message delivered)")
            else:
                if self.valves.ENABLE_LOGGING:
                    print(f"YouLab error: {e}")
                if __event_emitter__:
                    await __event_emitter__(
                        {"type": "message", "data": {"content": f"Error: {error_str}"}}
                    )

        return ""

    async def _handle_sse_event(
        self,
        data: str,
        emitter: Callable[[dict[str, Any]], Awaitable[None]] | None,
    ) -> None:
        """Handle SSE event from HTTP service."""
        if not emitter:
            return

        try:
            event = json.loads(data)
            event_type = event.get("type")

            if event_type == "status":
                await emitter(
                    {
                        "type": "status",
                        "data": {
                            "description": event.get("content", "Processing..."),
                            "done": False,
                        },
                    }
                )
            elif event_type == "message":
                await emitter({"type": "message", "data": {"content": event.get("content", "")}})
            elif event_type == "done":
                await emitter({"type": "status", "data": {"description": "Complete", "done": True}})
            elif event_type == "error":
                await emitter(
                    {
                        "type": "message",
                        "data": {"content": f"Error: {event.get('message', 'Unknown')}"},
                    }
                )

        except json.JSONDecodeError:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to parse SSE: {data}")
