"""HTTP endpoints for file sync management."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from youlab_server.server.sync.service import FileSyncService

router = APIRouter(prefix="/sync", tags=["sync"])

# Global service reference - set during app startup
_sync_service: FileSyncService | None = None


def get_file_sync() -> FileSyncService:
    """
    Get the file sync service.

    Raises:
        HTTPException: If sync service is not initialized.

    """
    if _sync_service is None:
        raise HTTPException(
            status_code=503,
            detail="Sync service not initialized or disabled",
        )
    return _sync_service


def set_file_sync(service: FileSyncService) -> None:
    """
    Set the global file sync service.

    Args:
        service: The file sync service instance.

    """
    global _sync_service
    _sync_service = service


# Type alias for dependency injection
SyncDep = Annotated[FileSyncService, Depends(get_file_sync)]


@router.get("/status")
async def get_sync_status(sync: SyncDep) -> dict[str, Any]:
    """
    Get sync service status.

    Returns:
        Status dict with running state, last sync time, and stats.

    """
    return sync.get_status()


@router.post("/trigger")
async def trigger_sync(sync: SyncDep) -> dict[str, Any]:
    """
    Manually trigger a sync cycle.

    Returns:
        Sync statistics from the triggered cycle.

    """
    stats = await sync.sync_all()
    return asdict(stats)


@router.get("/mappings")
async def list_mappings(sync: SyncDep) -> dict[str, Any]:
    """
    List all sync mappings.

    Returns:
        Dict with 'notes' and 'files' mapping lists.

    """
    return {
        "notes": [
            {
                "openwebui_note_id": m.openwebui_note_id,
                "letta_folder_id": m.letta_folder_id,
                "letta_file_id": m.letta_file_id,
                "title": m.title,
                "last_synced": m.last_synced,
                "status": m.status,
            }
            for m in sync.mappings.note_mappings.values()
        ],
        "files": [
            {
                "openwebui_file_id": m.openwebui_file_id,
                "openwebui_knowledge_id": m.openwebui_knowledge_id,
                "letta_folder_id": m.letta_folder_id,
                "letta_file_id": m.letta_file_id,
                "filename": m.filename,
                "last_synced": m.last_synced,
                "status": m.status,
            }
            for m in sync.mappings.file_mappings.values()
        ],
    }


@router.post("/attach/{agent_id}/{folder_name}")
async def attach_folder_to_agent(
    agent_id: str,
    folder_name: str,
    sync: SyncDep,
) -> dict[str, str]:
    """
    Attach a synced folder to an agent.

    Args:
        agent_id: The Letta agent ID.
        folder_name: Name of the folder to attach.
        sync: File sync service (injected).

    Returns:
        Status with folder ID.

    """
    folder_id = await sync.ensure_folder(folder_name)
    sync.letta.agents.folders.attach(
        agent_id=agent_id,
        folder_id=folder_id,
    )
    return {"status": "attached", "folder_id": folder_id}
