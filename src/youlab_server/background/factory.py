"""
Factory for creating Letta agents dedicated to background tasks.

Background agents are separate from user-facing agents and are designed for:
- Analyzing conversation history via Honcho
- Proposing memory block updates
- Running autonomously without user interaction
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from letta_client import Letta

log = structlog.get_logger()


class BackgroundAgentFactory:
    """
    Creates and manages Letta agents for background tasks.

    Each background task + user combination gets a dedicated agent.
    Agents are cached and reused across runs.
    """

    def __init__(self, letta_client: Letta) -> None:
        """
        Initialize the factory.

        Args:
            letta_client: Letta client for agent operations.

        """
        self.letta = letta_client
        # Cache: (task_name, user_id) -> agent_id
        self._cache: dict[tuple[str, str], str] = {}
        self.logger = log.bind(component="background_agent_factory")

    def _agent_name(self, task_name: str, user_id: str) -> str:
        """Generate unique agent name for a background task + user."""
        return f"background_{task_name}_{user_id}"

    def get_or_create_agent(
        self,
        task_name: str,
        user_id: str,
        system_prompt: str,
        tools: list[str],
        memory_blocks: dict[str, str],
        model: str = "openai/gpt-4o",
        fresh: bool = True,
    ) -> str:
        """
        Get or create a Letta agent for a background task.

        Args:
            task_name: Name of the background task.
            user_id: User ID this agent operates on behalf of.
            system_prompt: System prompt defining agent behavior.
            tools: List of tool names the agent can use.
            memory_blocks: Dict of {block_name: content} to inject.
            model: LLM model to use.
            fresh: If True (default), delete existing agent and create fresh.
                   This prevents message history confusion across runs.

        Returns:
            Agent ID.

        """
        cache_key = (task_name, user_id)
        agent_name = self._agent_name(task_name, user_id)

        # For background agents, default to fresh start each run
        # This avoids message history confusion across different students/contexts
        if fresh:
            self._delete_existing_agent(agent_name, cache_key)

        if not fresh:
            # Check cache first
            if cache_key in self._cache:
                agent_id = self._cache[cache_key]
                # Update memory blocks on existing agent
                self._update_agent_context(
                    agent_id, memory_blocks, system_prompt, task_name, user_id
                )
                return agent_id

            # Check if agent exists in Letta
            agents = self.letta.agents.list()
            for agent in agents:
                if agent.name == agent_name:
                    self._cache[cache_key] = agent.id
                    self._update_agent_context(
                        agent.id, memory_blocks, system_prompt, task_name, user_id
                    )
                    self.logger.debug(
                        "background_agent_found",
                        task_name=task_name,
                        user_id=user_id,
                        agent_id=agent.id,
                    )
                    return agent.id

        # Create new agent
        agent_id = self._create_agent(
            agent_name=agent_name,
            task_name=task_name,
            user_id=user_id,
            system_prompt=system_prompt,
            tools=tools,
            memory_blocks=memory_blocks,
            model=model,
        )
        self._cache[cache_key] = agent_id
        return agent_id

    def _delete_existing_agent(self, agent_name: str, cache_key: tuple[str, str]) -> None:
        """Delete an existing background agent to ensure fresh start."""
        # Clear from cache
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Delete from Letta if exists
        try:
            agents = self.letta.agents.list()
            for agent in agents:
                if agent.name == agent_name:
                    self.letta.agents.delete(agent.id)
                    self.logger.debug(
                        "background_agent_deleted",
                        agent_name=agent_name,
                        agent_id=agent.id,
                    )
                    break
        except Exception as e:
            self.logger.warning(
                "background_agent_delete_failed",
                agent_name=agent_name,
                error=str(e),
            )

    def _create_agent(
        self,
        agent_name: str,
        task_name: str,
        user_id: str,
        system_prompt: str,
        tools: list[str],
        memory_blocks: dict[str, str],
        model: str,
    ) -> str:
        """Create a new background agent in Letta."""
        # Convert memory blocks dict to Letta format
        # Use "human" label for all user context blocks
        letta_blocks = []
        for block_name, content in memory_blocks.items():
            letta_blocks.append(
                {
                    "label": block_name,
                    "value": content,
                }
            )

        # If no blocks provided, create a minimal context block
        if not letta_blocks:
            letta_blocks.append(
                {
                    "label": "context",
                    "value": f"Background agent for user {user_id}",
                }
            )

        agent = self.letta.agents.create(
            name=agent_name,
            model=model,
            embedding="openai/text-embedding-3-small",
            system=system_prompt,
            memory_blocks=letta_blocks,
            tools=tools if tools else None,
            metadata={
                "youlab_background_task": task_name,
                "youlab_user_id": user_id,
                "youlab_agent_type": "background",
            },
        )

        self.logger.info(
            "background_agent_created",
            task_name=task_name,
            user_id=user_id,
            agent_id=agent.id,
            tools=tools,
            blocks=list(memory_blocks.keys()),
        )

        return agent.id

    def _update_agent_context(
        self,
        agent_id: str,
        memory_blocks: dict[str, str],
        system_prompt: str,
        task_name: str = "",
        user_id: str = "",
    ) -> None:
        """
        Update an existing agent's memory blocks with fresh content.

        This ensures the agent has current memory block state before running.
        """
        try:
            # Update system prompt if it has changed
            agent = self.letta.agents.retrieve(agent_id)
            if agent.system != system_prompt:
                self.letta.agents.modify(agent_id, system=system_prompt)

            # Ensure metadata includes user_id (for sandbox tool access)
            if task_name and user_id:
                try:
                    self.letta.agents.modify(
                        agent_id=agent_id,
                        metadata={
                            "youlab_background_task": task_name,
                            "youlab_user_id": user_id,
                            "youlab_agent_type": "background",
                        },
                    )
                except Exception as e:
                    self.logger.debug("metadata_update_skipped", error=str(e))

            # Update memory blocks
            # Get existing blocks and update their values
            agent_blocks = self.letta.agents.blocks.list(agent_id)
            existing_labels = {b.label: b.id for b in agent_blocks}

            for block_name, content in memory_blocks.items():
                if block_name in existing_labels:
                    # Update existing block
                    self.letta.blocks.modify(
                        block_id=existing_labels[block_name],
                        value=content,
                    )
                else:
                    # Create and attach new block
                    new_block = self.letta.blocks.create(
                        label=block_name,
                        value=content,
                    )
                    self.letta.agents.blocks.attach(
                        agent_id=agent_id,
                        block_id=new_block.id,
                    )

            self.logger.debug(
                "background_agent_context_updated",
                agent_id=agent_id,
                blocks_updated=list(memory_blocks.keys()),
            )
        except Exception as e:
            self.logger.warning(
                "background_agent_context_update_failed",
                agent_id=agent_id,
                error=str(e),
            )

    def send_instruction(
        self,
        agent_id: str,
        instruction: str,
        user_id: str,
    ) -> str:
        """
        Send an instruction to a background agent and get response.

        Args:
            agent_id: The agent to send the instruction to.
            instruction: The instruction/task for the agent.
            user_id: User ID for tool context injection.

        Returns:
            Agent's response text.

        """
        # Set up tool context before sending message
        self._setup_tool_context(agent_id, user_id)

        response = self.letta.agents.messages.create(
            agent_id=agent_id,
            input=instruction,
        )

        return self._extract_response(response)

    def _setup_tool_context(self, agent_id: str, user_id: str) -> None:
        """Set up context needed by tools (query_honcho, edit_memory_block)."""
        # Note (ARI-85): This context setup doesn't work for Letta sandbox execution.
        # When tools run in sandbox, they can't access youlab_server module.
        from youlab_server.tools.dialectic import set_user_context

        # Set user context so query_honcho knows which user to query
        set_user_context(agent_id, user_id)

    def _extract_response(self, response: Any) -> str:
        """Extract text from Letta response."""
        texts = []
        if hasattr(response, "messages"):
            for msg in response.messages:
                if hasattr(msg, "assistant_message") and msg.assistant_message:
                    texts.append(msg.assistant_message)
                elif hasattr(msg, "text") and msg.text:
                    texts.append(msg.text)
        return "\n".join(texts) if texts else ""
