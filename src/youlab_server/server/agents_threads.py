"""Background agent thread management endpoints and utilities."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from youlab_server.server.users import get_storage_manager
from youlab_server.storage.blocks import UserBlockManager
from youlab_server.storage.git import GitUserStorageManager

if TYPE_CHECKING:
    from youlab_server.server.sync.openwebui_client import OpenWebUIClient

log = structlog.get_logger()
router = APIRouter(prefix="/users/{user_id}/agents", tags=["agents"])

# Type alias for dependency injection
StorageDep = Annotated[GitUserStorageManager, Depends(get_storage_manager)]


class ThreadRun(BaseModel):
    """A single background agent thread run."""

    id: str
    chat_id: str
    date: str
    display_date: str


class BackgroundAgent(BaseModel):
    """Background agent with thread history."""

    name: str
    pending_diffs: int
    threads: list[ThreadRun]


@router.get("", response_model=list[BackgroundAgent])
async def list_background_agents(
    user_id: str,
    storage: StorageDep,
) -> list[BackgroundAgent]:
    """
    List background agents with their thread history.

    Returns agents grouped by name, each with:
    - List of thread runs (OpenWebUI chat IDs)
    - Pending diff count for this agent
    - Threads sorted by date (newest first)
    """
    user_storage = storage.get(user_id)
    if not user_storage.exists:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get pending diffs count per agent using UserBlockManager
    manager = UserBlockManager(user_id, user_storage)
    pending_diffs = manager.list_pending_diffs()

    # Group diffs by agent
    agent_diffs: dict[str, int] = {}
    for diff in pending_diffs:
        agent_id = diff.get("agent_id", "unknown")
        agent_diffs[agent_id] = agent_diffs.get(agent_id, 0) + 1

    # Get background agent threads from storage
    # Thread metadata stored in: {user_dir}/agent_threads/{agent_name}/{chat_id}.json
    agents_dir = user_storage.user_dir / "agent_threads"
    agents: list[BackgroundAgent] = []

    if not agents_dir.exists():
        return agents

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        agent_name = agent_dir.name.replace("_", " ").title()
        threads: list[ThreadRun] = []

        for thread_file in sorted(
            agent_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(thread_file.read_text())
                created_at = data.get("created_at", "")
                run_date = datetime.fromisoformat(created_at) if created_at else datetime.now()
                threads.append(
                    ThreadRun(
                        id=thread_file.stem,
                        chat_id=data.get("chat_id", thread_file.stem),
                        date=created_at,
                        display_date=run_date.strftime("%b %d, %Y"),
                    )
                )
            except Exception as e:
                log.warning(
                    "thread_parse_failed",
                    agent=agent_name,
                    file=thread_file.name,
                    error=str(e),
                )

        agents.append(
            BackgroundAgent(
                name=agent_name,
                pending_diffs=agent_diffs.get(agent_dir.name, 0),
                threads=threads,
            )
        )

    # Sort agents by name
    agents.sort(key=lambda a: a.name)

    return agents


@router.post("/{agent_name}/threads")
async def register_agent_thread(
    user_id: str,
    agent_name: str,
    chat_id: Annotated[str, Query(description="The OpenWebUI chat ID")],
    storage: StorageDep,
) -> dict[str, str]:
    """
    Register a new background agent thread run.

    Called when a background agent job starts to create the thread mapping.
    """
    user_storage = storage.get(user_id)
    if not user_storage.exists:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Create agent threads directory
    agent_dir = user_storage.user_dir / "agent_threads" / agent_name.lower().replace(" ", "_")
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Save thread metadata
    thread_file = agent_dir / f"{chat_id}.json"
    thread_file.write_text(
        json.dumps(
            {
                "chat_id": chat_id,
                "created_at": datetime.now().isoformat(),
                "agent_name": agent_name,
            },
            indent=2,
        )
    )

    log.info(
        "agent_thread_registered",
        user_id=user_id,
        agent=agent_name,
        chat_id=chat_id,
    )

    return {"status": "registered", "chat_id": chat_id}


async def create_agent_thread(
    user_id: str,
    agent_id: str,
    agent_name: str,
    openwebui_client: OpenWebUIClient,
) -> str:
    """
    Create a new chat thread for a background agent run.

    Archives the previous active thread and creates a new one in the agent's folder.
    The folder is created if it doesn't exist.

    Args:
        user_id: The user ID (for logging).
        agent_id: The agent ID.
        agent_name: Display name for the agent (used as folder name).
        openwebui_client: OpenWebUI API client.

    Returns:
        The chat ID of the newly created thread.

    """
    # Ensure folder exists (no emoji prefix)
    folder_name = agent_name
    folder_id = await openwebui_client.ensure_folder(
        folder_name,
        meta={"type": "background_agent", "agentId": agent_id},
    )

    # Archive previous active threads in this folder
    existing_chats = await openwebui_client.get_chats_by_folder(folder_id)
    for chat in existing_chats:
        if not chat.get("archived"):
            await openwebui_client.archive_chat(chat["id"])

    # Create new thread with date-based title
    date_str = datetime.now().strftime("%b %d, %Y")
    title = f"{agent_name} - {date_str}"

    chat = await openwebui_client.create_chat(
        {"title": title, "models": [], "messages": []},
        folder_id,
    )

    log.info(
        "agent_thread_created",
        user_id=user_id,
        agent_id=agent_id,
        agent_name=agent_name,
        folder_id=folder_id,
        chat_id=chat["id"],
    )

    return chat["id"]
