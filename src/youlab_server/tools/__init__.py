"""
Tool registry with default rules.

This module provides:
1. Agent-callable tools (query_honcho, edit_memory_block)
2. Tool registry with default execution rules
"""

from enum import Enum
from typing import NamedTuple

from youlab_server.tools.curriculum import advance_lesson
from youlab_server.tools.dialectic import query_honcho
from youlab_server.tools.memory import edit_memory_block

# =============================================================================
# TOOL RULE SYSTEM
# =============================================================================


class ToolRule(str, Enum):
    """Tool execution rules."""

    EXIT_LOOP = "exit"
    CONTINUE_LOOP = "continue"
    RUN_FIRST = "first"


class ToolMetadata(NamedTuple):
    """Metadata for a registered tool."""

    id: str
    default_rule: ToolRule
    description: str = ""


# Registry of known tools with their defaults
TOOL_REGISTRY: dict[str, ToolMetadata] = {
    "send_message": ToolMetadata(
        "send_message",
        ToolRule.EXIT_LOOP,
        "Send a message to the user",
    ),
    "query_honcho": ToolMetadata(
        "query_honcho",
        ToolRule.CONTINUE_LOOP,
        "Query conversation history via Honcho dialectic",
    ),
    "edit_memory_block": ToolMetadata(
        "edit_memory_block",
        ToolRule.CONTINUE_LOOP,
        "Update a field in the agent's memory block",
    ),
    "advance_lesson": ToolMetadata(
        "advance_lesson",
        ToolRule.CONTINUE_LOOP,
        "Request advancement to the next lesson in the curriculum",
    ),
}


def get_tool_rule(tool_spec: str) -> tuple[str, ToolRule]:
    """
    Parse tool spec into (tool_id, rule).

    Supports two formats:
    - "tool_name" - uses default rule from registry
    - "tool_name:rule" - explicit rule override

    Args:
        tool_spec: Tool specification string

    Returns:
        Tuple of (tool_id, ToolRule)

    Examples:
        >>> get_tool_rule("send_message")
        ("send_message", ToolRule.EXIT_LOOP)

        >>> get_tool_rule("custom:exit")
        ("custom", ToolRule.EXIT_LOOP)

        >>> get_tool_rule("unknown_tool")
        ("unknown_tool", ToolRule.CONTINUE_LOOP)

    """
    if ":" in tool_spec:
        tool_id, rule_str = tool_spec.split(":", 1)
        rule = ToolRule(rule_str)
    else:
        tool_id = tool_spec
        metadata = TOOL_REGISTRY.get(tool_id)
        rule = metadata.default_rule if metadata else ToolRule.CONTINUE_LOOP
    return tool_id, rule


__all__ = [
    "TOOL_REGISTRY",
    "ToolMetadata",
    "ToolRule",
    "advance_lesson",
    "edit_memory_block",
    "get_tool_rule",
    "query_honcho",
]
