"""
Base agent with integrated observability and memory management.

All agents in the system should inherit from BaseAgent to get
consistent logging, tracing, and memory handling.

.. deprecated::
    This module is deprecated. Use Letta agents directly via AgentManager instead.
    See docs/Agent-System.md for the recommended approach.
"""

import warnings
from typing import Any

import structlog

warnings.warn(
    "letta_starter.agents.base is deprecated. "
    "Use Letta agents directly via AgentManager instead. "
    "See docs/Agent-System.md for the recommended approach.",
    DeprecationWarning,
    stacklevel=2,
)

from letta_starter.memory.blocks import HumanBlock, PersonaBlock  # noqa: E402
from letta_starter.memory.manager import MemoryManager  # noqa: E402
from letta_starter.observability.tracing import Tracer, get_tracer  # noqa: E402


class BaseAgent:
    """
    Base class for Letta agents with integrated observability.

    Provides:
    - Structured memory management
    - Automatic LLM call tracing
    - Consistent logging
    - Error handling patterns
    """

    def __init__(
        self,
        name: str,
        persona: PersonaBlock,
        human: HumanBlock,
        client: Any,
        tracer: Tracer | None = None,
        max_memory_chars: int = 1500,
    ):
        """
        Initialize a base agent.

        Args:
            name: Agent name (used for identification and logging)
            persona: Agent persona memory block
            human: Human context memory block
            client: Letta client instance
            tracer: Optional tracer (default: global tracer)
            max_memory_chars: Maximum chars per memory block

        """
        self.name = name
        self.client = client
        self.tracer = tracer or get_tracer()
        self.logger = structlog.get_logger().bind(agent=name)

        # Create the agent in Letta
        try:
            self.agent_state = self.client.create_agent(
                name=name,
                memory={
                    "persona": persona.to_memory_string(max_memory_chars),
                    "human": human.to_memory_string(max_memory_chars),
                },
            )
            self.agent_id = self.agent_state.id
        except Exception as e:
            # Agent might already exist, try to get it
            self.logger.info("agent_create_failed_trying_get", error=str(e))
            agents = self.client.list_agents()
            existing = next((a for a in agents if a.name == name), None)
            if existing:
                self.agent_state = existing
                self.agent_id = existing.id
            else:
                raise

        # Initialize memory manager
        self.memory = MemoryManager(
            client=self.client,
            agent_id=self.agent_id,
            max_chars=max_memory_chars,
        )

        self.logger.info(
            "agent_initialized",
            agent_id=self.agent_id,
        )

    def send_message(self, message: str, session_id: str | None = None) -> str:
        """
        Send a message to the agent and get a response.

        Args:
            message: User message
            session_id: Optional session ID for tracing

        Returns:
            Agent response text

        """
        self.logger.debug(
            "message_received",
            message_length=len(message),
            session_id=session_id,
        )

        with self.tracer.trace_llm_call(
            model="letta",  # Letta wraps the actual model
            agent_name=self.name,
            operation="send_message",
        ) as metrics:
            try:
                response = self._send_message_internal(message)

                # Try to extract token usage from response
                if hasattr(response, "usage"):
                    metrics.prompt_tokens = getattr(response.usage, "prompt_tokens", 0)
                    metrics.completion_tokens = getattr(response.usage, "completion_tokens", 0)

                response_text = self._extract_response_text(response)

                self.logger.debug(
                    "message_sent",
                    response_length=len(response_text),
                    session_id=session_id,
                )

                return response_text

            except Exception as e:
                self.logger.error(
                    "message_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    session_id=session_id,
                )
                raise

    def _send_message_internal(self, message: str) -> Any:
        """
        Internal method to send message to Letta.

        Override this in subclasses to customize message handling.
        """
        return self.client.send_message(
            agent_id=self.agent_id,
            message=message,
            role="user",
        )

    def _extract_response_text(self, response: Any) -> str:
        """
        Extract text from Letta response.

        Letta responses can contain multiple message types.
        This extracts the user-facing assistant messages.
        """
        texts = []

        if hasattr(response, "messages"):
            for msg in response.messages:
                # Check for assistant_message attribute
                if hasattr(msg, "assistant_message") and msg.assistant_message:
                    texts.append(msg.assistant_message)
                # Check for text attribute
                elif hasattr(msg, "text") and msg.text:
                    texts.append(msg.text)

        return "\n".join(texts) if texts else ""

    def update_context(self, task: str | None = None, note: str | None = None) -> None:
        """
        Update the agent's context.

        Args:
            task: New task to set
            note: Context note to add

        """
        if task:
            self.memory.set_task(task)
        if note:
            self.memory.add_context(note)

    def learn(self, preference: str | None = None, fact: str | None = None) -> None:
        """
        Record learned information about the user.

        Args:
            preference: A user preference to remember
            fact: A fact about the user to remember

        """
        if preference:
            self.memory.learn_preference(preference)
        if fact:
            self.memory.learn_fact(fact)

    def get_memory_summary(self) -> dict[str, object]:
        """Get a summary of the agent's memory state."""
        return self.memory.get_summary()

    def search_memory(self, query: str, limit: int = 5) -> list[str]:
        """
        Search the agent's archival memory.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching archival entries

        """
        return self.memory.search_archival(query, limit)

    def __repr__(self) -> str:
        return f"BaseAgent(name={self.name!r}, agent_id={self.agent_id!r})"
