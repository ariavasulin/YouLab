"""
Memory enrichment service for external updates.

This service handles memory edits from background workers with proper audit trailing.
Unlike agent tools (which auto-log to Letta message history), this service writes
audit entries to the target agent's archival memory for transparency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from youlab_server.memory.manager import MemoryManager

log = structlog.get_logger()

# Audit entry limits
AUDIT_CONTENT_MAX_CHARS = 200
AUDIT_QUERY_MAX_CHARS = 100


class MergeStrategy(str, Enum):
    """Strategy for merging content."""

    APPEND = "append"
    REPLACE = "replace"
    LLM_DIFF = "llm_diff"


@dataclass
class EnrichmentResult:
    """Result of a memory enrichment operation."""

    success: bool
    block: str
    field: str
    strategy: MergeStrategy
    message: str
    audit_entry_id: str | None = None


class MemoryEnricher:
    """
    Service for external memory enrichment with audit trailing.

    Unlike agent tools (which auto-log to message history),
    this service handles edits from background workers and
    writes audit entries to the target agent's archival memory.
    """

    def __init__(self, client: Any) -> None:
        """
        Initialize the memory enricher.

        Args:
            client: Letta client instance

        """
        self.client = client
        self.logger = log.bind(component="memory_enricher")

    def enrich(
        self,
        agent_id: str,
        block: str,
        field: str,
        content: str,
        strategy: MergeStrategy = MergeStrategy.APPEND,
        source: str = "background_worker",
        source_query: str | None = None,
    ) -> EnrichmentResult:
        """
        Enrich an agent's memory with external content.

        Args:
            agent_id: Target agent to enrich
            block: Memory block ("human" or "persona")
            field: Field to update
            content: Content to add/replace
            strategy: Merge strategy
            source: Source of the enrichment
            source_query: Optional query that produced this content

        Returns:
            EnrichmentResult with success status and details

        """
        manager = MemoryManager(client=self.client, agent_id=agent_id)

        try:
            # Apply the edit
            if block == "human":
                self._enrich_human(manager, field, content, strategy)
            elif block == "persona":
                self._enrich_persona(manager, field, content, strategy)
            else:
                return EnrichmentResult(
                    success=False,
                    block=block,
                    field=field,
                    strategy=strategy,
                    message=f"Unknown block: {block}",
                )

            # Write audit entry to target agent's archival
            audit_id = self._write_audit_entry(
                agent_id=agent_id,
                block=block,
                field=field,
                content=content,
                strategy=strategy,
                source=source,
                source_query=source_query,
            )

            self.logger.info(
                "memory_enriched",
                agent_id=agent_id,
                block=block,
                field=field,
                strategy=strategy.value,
                source=source,
            )

            return EnrichmentResult(
                success=True,
                block=block,
                field=field,
                strategy=strategy,
                message=f"Enriched {block}.{field} via {strategy.value}",
                audit_entry_id=audit_id,
            )

        except Exception as e:
            self.logger.error(
                "enrichment_failed",
                agent_id=agent_id,
                block=block,
                field=field,
                error=str(e),
            )
            return EnrichmentResult(
                success=False,
                block=block,
                field=field,
                strategy=strategy,
                message=f"Enrichment failed: {e}",
            )

    def _enrich_human(
        self,
        manager: MemoryManager,
        field: str,
        content: str,
        strategy: MergeStrategy,
    ) -> None:
        """Apply enrichment to human block."""
        human = manager.get_human_block()

        if field == "context_notes":
            if strategy == MergeStrategy.REPLACE:
                human.context_notes = [content]
            else:  # APPEND or LLM_DIFF (diff not yet implemented)
                human.add_context_note(content)
        elif field == "facts":
            if strategy == MergeStrategy.REPLACE:
                human.facts = [content]
            else:
                human.add_fact(content)
        elif field == "preferences":
            if strategy == MergeStrategy.REPLACE:
                human.preferences = [content]
            else:
                human.add_preference(content)
        else:
            raise ValueError(f"Unknown human field: {field}")

        manager.update_human(human)

    def _enrich_persona(
        self,
        manager: MemoryManager,
        field: str,
        content: str,
        strategy: MergeStrategy,
    ) -> None:
        """Apply enrichment to persona block."""
        persona = manager.get_persona_block()

        if field == "constraints":
            if strategy == MergeStrategy.REPLACE:
                persona.constraints = [content]
            elif content not in persona.constraints:
                persona.constraints.append(content)
        elif field == "expertise":
            if strategy == MergeStrategy.REPLACE:
                persona.expertise = [content]
            elif content not in persona.expertise:
                persona.expertise.append(content)
        else:
            raise ValueError(f"Unknown persona field: {field}")

        manager.update_persona(persona)

    def _write_audit_entry(
        self,
        agent_id: str,
        block: str,
        field: str,
        content: str,
        strategy: MergeStrategy,
        source: str,
        source_query: str | None,
    ) -> str | None:
        """Write audit entry to agent's archival memory."""
        timestamp = datetime.now().isoformat()

        entry_parts = [
            f"[MEMORY_EDIT {timestamp}]",
            f"Source: {source}",
            f"Block: {block}",
            f"Field: {field}",
            f"Strategy: {strategy.value}",
        ]

        if source_query:
            entry_parts.append(f"Query: {source_query[:AUDIT_QUERY_MAX_CHARS]}")

        if len(content) > AUDIT_CONTENT_MAX_CHARS:
            content_preview = content[:AUDIT_CONTENT_MAX_CHARS] + "..."
        else:
            content_preview = content
        entry_parts.append(f"Content: {content_preview}")

        audit_entry = "\n".join(entry_parts)

        try:
            self.client.insert_archival_memory(
                agent_id=agent_id,
                memory=audit_entry,
            )
            return timestamp  # Use timestamp as pseudo-ID
        except Exception as e:
            self.logger.warning(
                "audit_entry_failed",
                agent_id=agent_id,
                error=str(e),
            )
            return None
