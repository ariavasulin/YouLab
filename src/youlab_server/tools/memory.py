"""Memory block editing tool for Letta agents."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from youlab_server.memory.blocks import HumanBlock, PersonaBlock

log = structlog.get_logger()

# Global references
_letta_client: Any = None

# Protected fields that require explicit override
PROTECTED_FIELDS = {"persona.name", "persona.role"}


class MergeStrategy(str, Enum):
    """Strategy for merging new content with existing."""

    APPEND = "append"  # Add to existing list/content
    REPLACE = "replace"  # Overwrite existing content
    LLM_DIFF = "llm_diff"  # Use LLM to intelligently merge


def set_letta_client(client: Any) -> None:
    """Set the global Letta client for tool use."""
    global _letta_client
    _letta_client = client


def edit_memory_block(
    block: str,
    field: str,
    content: str,
    strategy: str = "append",
    agent_state: dict[str, Any] | None = None,
) -> str:
    """
    Update a field in your memory blocks.

    Use this tool to:
    - Record learned facts about the student
    - Update context notes with new information
    - Adjust your communication style based on insights

    Args:
        block: Which memory block to edit:
               - "human": Student context (facts, preferences, notes)
               - "persona": Your behavior (constraints, style)
        field: Which field to update:
               - human: "context_notes", "facts", "preferences"
               - persona: "constraints", "expertise"
        content: The content to add or replace
        strategy: How to merge with existing content:
                 - "append": Add to existing (default, safe)
                 - "replace": Overwrite existing
                 - "llm_diff": Intelligently merge old and new
        agent_state: Agent state injected by Letta (contains agent_id)

    Returns:
        Confirmation of the update or error message.

    """
    if _letta_client is None:
        return "Memory system unavailable. Update not applied."

    agent_id = agent_state.get("agent_id") if agent_state else None
    if not agent_id:
        return "Unable to identify agent. Update not applied."

    # Check protected fields
    field_key = f"{block}.{field}"
    if field_key in PROTECTED_FIELDS:
        log.warning(
            "protected_field_edit_attempted",
            agent_id=agent_id,
            field=field_key,
        )
        return (
            f"Cannot edit protected field '{field_key}'. This field requires manual configuration."
        )

    try:
        strategy_enum = MergeStrategy(strategy)
    except ValueError:
        strategy_enum = MergeStrategy.APPEND

    try:
        result = _apply_memory_edit(
            agent_id=agent_id,
            block=block,
            field=field,
            content=content,
            strategy=strategy_enum,
        )

        log.info(
            "memory_block_edited",
            agent_id=agent_id,
            block=block,
            field=field,
            strategy=strategy,
            content_preview=content[:50],
            source="agent_tool",
        )

        return result

    except Exception as e:
        log.error(
            "memory_edit_failed",
            agent_id=agent_id,
            block=block,
            field=field,
            error=str(e),
        )
        return f"Failed to update memory: {e}"


def _apply_memory_edit(
    agent_id: str,
    block: str,
    field: str,
    content: str,
    strategy: MergeStrategy,
) -> str:
    """Apply the memory edit using MemoryManager."""
    from youlab_server.memory.manager import MemoryManager

    manager = MemoryManager(
        client=_letta_client,
        agent_id=agent_id,
    )

    if block == "human":
        human = manager.get_human_block()
        _update_human_field(human, field, content, strategy)
        manager.update_human(human)
        return f"Updated human.{field} via {strategy.value}"

    if block == "persona":
        persona = manager.get_persona_block()
        _update_persona_field(persona, field, content, strategy)
        manager.update_persona(persona)
        return f"Updated persona.{field} via {strategy.value}"

    return f"Unknown block '{block}'. Use 'human' or 'persona'."


def _update_human_field(
    human: HumanBlock,
    field: str,
    content: str,
    strategy: MergeStrategy,
) -> None:
    """Update a field on the human block."""
    if field == "context_notes":
        if strategy == MergeStrategy.REPLACE:
            human.context_notes = [content]
        elif strategy == MergeStrategy.APPEND:
            human.add_context_note(content)
        elif strategy == MergeStrategy.LLM_DIFF:
            merged = _llm_merge(human.context_notes, content)
            human.context_notes = [merged]

    elif field == "facts":
        if strategy == MergeStrategy.REPLACE:
            human.facts = [content]
        elif strategy == MergeStrategy.APPEND:
            human.add_fact(content)
        elif strategy == MergeStrategy.LLM_DIFF:
            merged = _llm_merge(human.facts, content)
            human.facts = [merged]

    elif field == "preferences":
        if strategy == MergeStrategy.REPLACE:
            human.preferences = [content]
        elif strategy == MergeStrategy.APPEND:
            human.add_preference(content)
        elif strategy == MergeStrategy.LLM_DIFF:
            merged = _llm_merge(human.preferences, content)
            human.preferences = [merged]
    else:
        raise ValueError(f"Unknown human field: {field}")


def _update_persona_field(
    persona: PersonaBlock,
    field: str,
    content: str,
    strategy: MergeStrategy,
) -> None:
    """Update a field on the persona block."""
    if field == "constraints":
        if strategy == MergeStrategy.REPLACE:
            persona.constraints = [content]
        elif strategy == MergeStrategy.APPEND:
            if content not in persona.constraints:
                persona.constraints.append(content)
        elif strategy == MergeStrategy.LLM_DIFF:
            merged = _llm_merge(persona.constraints, content)
            persona.constraints = [merged]

    elif field == "expertise":
        if strategy == MergeStrategy.REPLACE:
            persona.expertise = [content]
        elif strategy == MergeStrategy.APPEND:
            if content not in persona.expertise:
                persona.expertise.append(content)
        elif strategy == MergeStrategy.LLM_DIFF:
            merged = _llm_merge(persona.expertise, content)
            persona.expertise = [merged]
    else:
        raise ValueError(f"Unknown persona field: {field}")


def _llm_merge(existing: list[str] | str, new_content: str) -> str:
    """Use LLM to intelligently merge existing and new content."""
    # TODO: Implement LLM-based merging
    # For now, fall back to append behavior
    existing_str = "; ".join(existing) if isinstance(existing, list) else existing
    return f"{existing_str}; {new_content}"
