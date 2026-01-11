"""
Memory Manager - orchestrates memory lifecycle for Letta agents.

This is the central coordinator for all memory operations:
- Block serialization/deserialization
- Context rotation (core -> archival)
- Memory optimization
- Cross-session persistence

.. deprecated::
    This module is deprecated. Use agent-driven memory via edit_memory_block tool instead.
    See docs/Memory-System.md for the recommended approach.
"""

import time
import warnings
from datetime import datetime
from typing import Any

import structlog

warnings.warn(
    "youlab_server.memory.manager is deprecated. "
    "Use agent-driven memory via edit_memory_block tool instead. "
    "See docs/Memory-System.md for the recommended approach.",
    DeprecationWarning,
    stacklevel=2,
)

from youlab_server.memory.blocks import HumanBlock, PersonaBlock  # noqa: E402
from youlab_server.memory.strategies import (  # noqa: E402
    AdaptiveRotation,
    ContextMetrics,
    ContextStrategy,
)

logger = structlog.get_logger()


class MemoryManager:
    """
    Manages memory lifecycle for a Letta agent.

    Responsibilities:
    - Serialize/deserialize memory blocks
    - Monitor context usage
    - Rotate context to archival when needed
    - Provide memory analytics
    """

    def __init__(
        self,
        client: Any,
        agent_id: str,
        max_chars: int = 1500,
        strategy: ContextStrategy | None = None,
    ):
        """
        Initialize the memory manager.

        Args:
            client: Letta client instance
            agent_id: ID of the agent to manage
            max_chars: Maximum characters per memory block
            strategy: Context management strategy (default: AdaptiveRotation)

        """
        self.client = client
        self.agent_id = agent_id
        self.max_chars = max_chars
        self.strategy = strategy or AdaptiveRotation()
        self.logger = logger.bind(agent_id=agent_id, component="memory_manager")

        # Track state
        self._persona_block: PersonaBlock | None = None
        self._human_block: HumanBlock | None = None
        self._last_rotation: float | None = None

    def get_metrics(self) -> ContextMetrics:
        """Get current memory usage metrics."""
        persona_str = self._get_persona_string()
        human_str = self._get_human_string()

        return ContextMetrics(
            persona_chars=len(persona_str),
            human_chars=len(human_str),
            persona_max=self.max_chars,
            human_max=self.max_chars,
        )

    def _get_persona_string(self) -> str:
        """Get current persona memory string from agent."""
        try:
            memory = self.client.get_agent_memory(self.agent_id)
            return str(memory.get("persona", ""))
        except Exception as e:
            self.logger.warning("failed_to_get_persona", error=str(e))
            return ""

    def _get_human_string(self) -> str:
        """Get current human memory string from agent."""
        try:
            memory = self.client.get_agent_memory(self.agent_id)
            return str(memory.get("human", ""))
        except Exception as e:
            self.logger.warning("failed_to_get_human", error=str(e))
            return ""

    def get_persona_block(self) -> PersonaBlock:
        """Get the current persona as a structured block."""
        if self._persona_block is None:
            persona_str = self._get_persona_string()
            if persona_str:
                self._persona_block = PersonaBlock.from_memory_string(persona_str)
            else:
                self._persona_block = PersonaBlock(role="Assistant")
        return self._persona_block

    def get_human_block(self) -> HumanBlock:
        """Get the current human context as a structured block."""
        if self._human_block is None:
            human_str = self._get_human_string()
            if human_str:
                self._human_block = HumanBlock.from_memory_string(human_str)
            else:
                self._human_block = HumanBlock()
        return self._human_block

    def update_persona(self, persona: PersonaBlock) -> None:
        """
        Update the agent's persona memory.

        Args:
            persona: New persona block

        """
        self._persona_block = persona
        memory_str = persona.to_memory_string(self.max_chars)

        try:
            self.client.update_agent_core_memory(
                agent_id=self.agent_id,
                persona=memory_str,
            )
            self.logger.info(
                "persona_updated",
                chars=len(memory_str),
            )
        except Exception as e:
            self.logger.error("failed_to_update_persona", error=str(e))
            raise

    def update_human(self, human: HumanBlock) -> None:
        """
        Update the agent's human context memory.

        Args:
            human: New human block

        """
        self._human_block = human
        memory_str = human.to_memory_string(self.max_chars)

        # Check if rotation needed
        metrics = ContextMetrics(
            persona_chars=len(self._get_persona_string()),
            human_chars=len(memory_str),
            persona_max=self.max_chars,
            human_max=self.max_chars,
        )

        if self.strategy.should_rotate(metrics):
            self._rotate_human_to_archival()

        try:
            self.client.update_agent_core_memory(
                agent_id=self.agent_id,
                human=memory_str,
            )
            self.logger.info(
                "human_updated",
                chars=len(memory_str),
                usage=f"{metrics.human_usage:.1%}",
            )
        except Exception as e:
            self.logger.error("failed_to_update_human", error=str(e))
            raise

    def set_task(self, task: str, context: str | None = None) -> None:
        """
        Set the current task in human memory.

        Args:
            task: Task description
            context: Optional additional context

        """
        human = self.get_human_block()
        human.set_task(task)
        if context:
            human.add_context_note(context)
        self.update_human(human)

    def clear_task(self, archive: bool = True) -> None:
        """
        Clear the current task.

        Args:
            archive: Whether to archive the task context first

        """
        human = self.get_human_block()

        if archive and human.current_task:
            self._archive_task_context(human)

        human.clear_task()
        self.update_human(human)

    def add_context(self, note: str) -> None:
        """Add a context note to human memory."""
        human = self.get_human_block()
        human.add_context_note(note)
        self.update_human(human)

    def learn_preference(self, preference: str) -> None:
        """Record a learned user preference."""
        human = self.get_human_block()
        human.add_preference(preference)
        self.update_human(human)

    def learn_fact(self, fact: str) -> None:
        """Record a fact about the user."""
        human = self.get_human_block()
        human.add_fact(fact)
        self.update_human(human)

    def _rotate_human_to_archival(self) -> None:
        """Rotate current human context to archival memory."""
        human = self.get_human_block()
        memory_str = human.to_memory_string(self.max_chars)

        timestamp = datetime.now().isoformat()
        archival_entry = f"[ARCHIVED {timestamp}]\n{memory_str}"

        try:
            self.client.insert_archival_memory(
                agent_id=self.agent_id,
                memory=archival_entry,
            )
            self._last_rotation = time.time()

            # Record rotation in adaptive strategy
            metrics = self.get_metrics()
            if hasattr(self.strategy, "record_rotation"):
                self.strategy.record_rotation(metrics.human_usage)

            self.logger.info(
                "context_rotated_to_archival",
                chars=len(archival_entry),
            )
        except Exception as e:
            self.logger.error("failed_to_rotate", error=str(e))

    def _archive_task_context(self, human: HumanBlock) -> None:
        """Archive task-specific context."""
        if not human.current_task:
            return

        timestamp = datetime.now().isoformat()
        task_summary = f"""[TASK COMPLETED {timestamp}]
Task: {human.current_task}
Context: {"; ".join(human.context_notes[-5:])}"""

        try:
            self.client.insert_archival_memory(
                agent_id=self.agent_id,
                memory=task_summary,
            )
            self.logger.info("task_archived", task=human.current_task[:50])
        except Exception as e:
            self.logger.warning("failed_to_archive_task", error=str(e))

    def search_archival(self, query: str, limit: int = 5) -> list[str]:
        """
        Search archival memory for relevant context.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of matching archival entries

        """
        try:
            results = self.client.get_archival_memory(
                agent_id=self.agent_id,
                query=query,
                limit=limit,
            )
            return [r.text for r in results] if results else []
        except Exception as e:
            self.logger.warning("archival_search_failed", error=str(e))
            return []

    def get_summary(self) -> dict[str, object]:
        """Get a summary of current memory state."""
        metrics = self.get_metrics()
        human = self.get_human_block()

        return {
            "agent_id": self.agent_id,
            "persona_usage": f"{metrics.persona_usage:.1%}",
            "human_usage": f"{metrics.human_usage:.1%}",
            "total_usage": f"{metrics.total_usage:.1%}",
            "session_state": human.session_state.value,
            "current_task": human.current_task,
            "context_notes_count": len(human.context_notes),
            "last_rotation": self._last_rotation,
        }
