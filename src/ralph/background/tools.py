"""Tool factory for background agents."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agno.tools.file import FileTools
from agno.tools.shell import ShellTools

if TYPE_CHECKING:
    from agno.tools.toolkit import Toolkit

from ralph.config import get_settings


def strip_agno_fields(toolkit: Toolkit) -> Toolkit:
    """Strip Agno-specific fields that some models don't accept."""
    for func in toolkit.functions.values():
        func.requires_confirmation = None  # type: ignore[assignment]
        func.external_execution = None  # type: ignore[assignment]
    return toolkit


def get_workspace_path(user_id: str) -> Path:
    """Get workspace directory for a user."""
    settings = get_settings()
    if settings.agent_workspace:
        return Path(settings.agent_workspace)
    workspace = Path(settings.user_data_dir) / user_id / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def create_tools_for_task(
    tool_names: list[str],
    user_id: str,
) -> list[Toolkit]:
    """
    Create tool instances for a background task.

    Args:
        tool_names: List of tool names to include
        user_id: User ID for workspace scoping

    Returns:
        List of Toolkit instances

    """
    workspace = get_workspace_path(user_id)
    tools: list[Toolkit] = []

    for name in tool_names:
        if name == "file_tools":
            tools.append(strip_agno_fields(FileTools(base_dir=workspace)))
        elif name == "shell_tools":
            tools.append(strip_agno_fields(ShellTools(base_dir=workspace)))

    return tools
