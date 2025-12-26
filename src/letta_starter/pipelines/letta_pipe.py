"""
Open WebUI Pipeline for Letta agents.

This file can be:
1. Copied directly to Open WebUI's pipelines directory
2. Uploaded via the Open WebUI admin interface
3. Used as a reference for custom pipeline implementations

The Pipeline class follows Open WebUI's pipeline specification.
"""

from collections.abc import Generator, Iterator
from typing import Any

from pydantic import BaseModel, Field


class Pipeline:
    """
    Open WebUI Pipeline for Letta agents.

    Exposes Letta agents through Open WebUI's chat interface.
    Configure using the Valves in the Open WebUI admin panel.
    """

    class Valves(BaseModel):
        """
        Configuration options exposed in Open WebUI admin.

        These can be modified at runtime through the UI.
        """

        LETTA_BASE_URL: str = Field(
            default="http://localhost:8283",
            description="URL of the Letta server",
        )
        LETTA_AGENT_NAME: str = Field(
            default="default",
            description="Name of the Letta agent to use",
        )
        CREATE_IF_NOT_EXISTS: bool = Field(
            default=True,
            description="Create agent if it doesn't exist",
        )
        ENABLE_LOGGING: bool = Field(
            default=True,
            description="Enable detailed logging",
        )

    def __init__(self) -> None:
        """Initialize the pipeline."""
        self.name = "Letta Agent"
        self.valves = self.Valves()
        self.client = None
        self.agent_id: str | None = None

    async def on_startup(self) -> None:
        """
        Called when the pipeline starts.

        Initializes the Letta client and gets/creates the agent.
        """
        try:
            from letta import create_client
        except ImportError:
            print("ERROR: letta package not installed. Run: pip install letta")
            return

        try:
            # Initialize Letta client
            self.client = create_client(base_url=self.valves.LETTA_BASE_URL)

            # Get or create the agent
            self._initialize_agent()

            if self.valves.ENABLE_LOGGING:
                print(f"Letta Pipeline started. Agent ID: {self.agent_id}")

        except Exception as e:
            print(f"ERROR: Failed to start Letta Pipeline: {e}")

    async def on_shutdown(self) -> None:
        """Called when the pipeline stops."""
        if self.valves.ENABLE_LOGGING:
            print("Letta Pipeline stopped")

    async def on_valves_updated(self) -> None:
        """Called when valves are updated via the UI."""
        if self.valves.ENABLE_LOGGING:
            print("Letta Pipeline valves updated, reinitializing...")

        # Reinitialize with new settings
        await self.on_startup()

    def _initialize_agent(self) -> None:
        """Get existing agent or create new one."""
        if not self.client:
            return

        agent_name = self.valves.LETTA_AGENT_NAME

        # Try to find existing agent
        agents = self.client.list_agents()
        existing = next((a for a in agents if a.name == agent_name), None)

        if existing:
            self.agent_id = existing.id
            if self.valves.ENABLE_LOGGING:
                print(f"Using existing agent: {agent_name} ({self.agent_id})")
            return

        # Create new agent if allowed
        if self.valves.CREATE_IF_NOT_EXISTS:
            try:
                from letta_starter.memory.blocks import DEFAULT_PERSONA, HumanBlock

                agent = self.client.create_agent(
                    name=agent_name,
                    memory={
                        "persona": DEFAULT_PERSONA.to_memory_string(),
                        "human": HumanBlock().to_memory_string(),
                    },
                )
                self.agent_id = agent.id
                if self.valves.ENABLE_LOGGING:
                    print(f"Created new agent: {agent_name} ({self.agent_id})")
            except ImportError:
                # Fallback if letta_starter not available
                agent = self.client.create_agent(
                    name=agent_name,
                    memory={
                        "persona": "[IDENTITY] Assistant | General-purpose AI assistant\n[STYLE] friendly, adaptive",
                        "human": "[USER] Unknown",
                    },
                )
                self.agent_id = agent.id
        else:
            raise ValueError(f"Agent '{agent_name}' not found and CREATE_IF_NOT_EXISTS is False")

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> str | Generator[str, None, None] | Iterator[str]:
        """
        Process a message through the Letta agent.

        This is the main entry point called by Open WebUI for each message.

        Args:
            user_message: The user's message text
            model_id: The selected model ID (from Open WebUI)
            messages: Full conversation history
            body: Additional request body data

        Returns:
            Agent response as string or generator for streaming
        """
        if not self.client or not self.agent_id:
            return "Error: Letta client not initialized. Check pipeline configuration."

        try:
            # Send message to Letta agent
            response = self.client.send_message(
                agent_id=self.agent_id,
                message=user_message,
                role="user",
            )

            # Extract response text
            response_text = self._extract_response(response)

            if self.valves.ENABLE_LOGGING:
                print(f"Letta response: {len(response_text)} chars")

            return response_text if response_text else "No response from agent."

        except Exception as e:
            error_msg = f"Error communicating with Letta: {str(e)}"
            if self.valves.ENABLE_LOGGING:
                print(f"ERROR: {error_msg}")
            return error_msg

    def _extract_response(self, response: Any) -> str:
        """Extract text from Letta response object."""
        texts = []

        if hasattr(response, "messages"):
            for msg in response.messages:
                # assistant_message is the user-facing response
                if hasattr(msg, "assistant_message") and msg.assistant_message:
                    texts.append(msg.assistant_message)
                # Fallback to text attribute
                elif hasattr(msg, "text") and msg.text:
                    texts.append(msg.text)

        return "\n".join(texts)


# For standalone testing
if __name__ == "__main__":
    import asyncio

    async def test() -> None:
        pipeline = Pipeline()
        await pipeline.on_startup()

        if pipeline.agent_id:
            response = pipeline.pipe(
                user_message="Hello! What can you help me with?",
                model_id="letta",
                messages=[],
                body={},
            )
            print(f"Response: {response}")

        await pipeline.on_shutdown()

    asyncio.run(test())
