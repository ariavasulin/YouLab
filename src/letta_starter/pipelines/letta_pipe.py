"""
OpenWebUI Pipeline for YouLab.

This Pipe forwards requests to the LettaStarter HTTP service.
It extracts user context from OpenWebUI and chat title from the database.
"""

from collections.abc import Generator, Iterator
from http import HTTPStatus
from typing import Any

import httpx
from pydantic import BaseModel, Field


class Pipeline:
    """
    OpenWebUI Pipeline for YouLab tutoring.

    Forwards messages to the LettaStarter HTTP service.
    Configure using Valves in the OpenWebUI admin panel.
    """

    class Valves(BaseModel):
        """Configuration options exposed in OpenWebUI admin."""

        LETTA_SERVICE_URL: str = Field(
            default="http://localhost:8100",
            description="URL of the LettaStarter HTTP service",
        )
        AGENT_TYPE: str = Field(
            default="tutor",
            description="Agent type to use (tutor, etc.)",
        )
        ENABLE_LOGGING: bool = Field(
            default=True,
            description="Enable detailed logging",
        )

    def __init__(self) -> None:
        """Initialize the pipeline."""
        self.name = "YouLab Tutor"
        self.valves = self.Valves()

    async def on_startup(self) -> None:
        """Called when the pipeline starts."""
        if self.valves.ENABLE_LOGGING:
            print(f"YouLab Pipeline started. Service URL: {self.valves.LETTA_SERVICE_URL}")

    async def on_shutdown(self) -> None:
        """Called when the pipeline stops."""
        if self.valves.ENABLE_LOGGING:
            print("YouLab Pipeline stopped")

    async def on_valves_updated(self) -> None:
        """Called when valves are updated via the UI."""
        if self.valves.ENABLE_LOGGING:
            print("YouLab Pipeline valves updated")

    def _get_chat_title(self, chat_id: str | None) -> str | None:
        """Get chat title from OpenWebUI database."""
        if not chat_id or chat_id.startswith("local:"):
            return None

        try:
            from open_webui.models.chats import Chats

            chat = Chats.get_chat_by_id(chat_id)
            return chat.title if chat else None
        except ImportError:
            # Not running inside OpenWebUI
            return None
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to get chat title: {e}")
            return None

    def _ensure_agent_exists(
        self,
        client: httpx.Client,
        user_id: str,
        user_name: str | None = None,
    ) -> str | None:
        """Ensure agent exists for user, create if needed. Returns agent_id."""
        # Check if agent exists
        try:
            response = client.get(
                f"{self.valves.LETTA_SERVICE_URL}/agents",
                params={"user_id": user_id},
            )
            if response.status_code == HTTPStatus.OK:
                agents = response.json().get("agents", [])
                # Find agent of correct type
                for agent in agents:
                    if agent.get("agent_type") == self.valves.AGENT_TYPE:
                        return agent.get("agent_id")
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to check existing agents: {e}")

        # Create new agent
        try:
            response = client.post(
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
            return None
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"Failed to create agent: {e}")
            return None

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> str | Generator[str, None, None] | Iterator[str]:
        """
        Process a message through the YouLab tutor.

        Args:
            user_message: The user's message text
            model_id: The selected model ID (from OpenWebUI)
            messages: Full conversation history
            body: Additional request body data
            __user__: User information from OpenWebUI
            __metadata__: Request metadata (chat_id, message_id, etc.)

        Returns:
            Agent response as string

        """
        # Extract user info
        user_id = __user__.get("id") if __user__ else None
        user_name = __user__.get("name") if __user__ else None

        if not user_id:
            return "Error: Could not identify user. Please log in."

        # Extract chat context
        chat_id = __metadata__.get("chat_id") if __metadata__ else None
        chat_title = self._get_chat_title(chat_id)

        if self.valves.ENABLE_LOGGING:
            print(f"YouLab: user={user_id}, chat={chat_id}, title={chat_title}")

        try:
            with httpx.Client(timeout=120.0) as client:
                # Ensure agent exists
                agent_id = self._ensure_agent_exists(client, user_id, user_name)
                if not agent_id:
                    return "Error: Could not create or find your tutor agent."

                # Send message
                response = client.post(
                    f"{self.valves.LETTA_SERVICE_URL}/chat",
                    json={
                        "agent_id": agent_id,
                        "message": user_message,
                        "chat_id": chat_id,
                        "chat_title": chat_title,
                    },
                )

                if response.status_code == HTTPStatus.OK:
                    return response.json().get("response", "No response from tutor.")
                if self.valves.ENABLE_LOGGING:
                    print(f"YouLab chat error: {response.status_code} - {response.text}")
                return f"Error communicating with tutor: {response.status_code}"

        except httpx.TimeoutException:
            return "Error: Request timed out. Please try again."
        except Exception as e:
            if self.valves.ENABLE_LOGGING:
                print(f"YouLab error: {e}")
            return f"Error: {e!s}"


# For standalone testing
if __name__ == "__main__":
    import asyncio

    async def test() -> None:
        pipeline = Pipeline()
        await pipeline.on_startup()

        # Simulate OpenWebUI context
        response = pipeline.pipe(
            user_message="Hello! What can you help me with?",
            model_id="youlab",
            messages=[],
            body={},
            __user__={"id": "test-user-123", "name": "Test User"},
            __metadata__={"chat_id": "local:test"},
        )
        print(f"Response: {response}")

        await pipeline.on_shutdown()

    asyncio.run(test())
