"""
Workspace file sync HTTP API endpoints.

Provides endpoints for the local daemon (Phase 2) to sync files with Ralph workspaces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ralph.config import get_settings
from ralph.sync.models import SyncResult, WorkspaceIndex
from ralph.sync.openwebui_client import OpenWebUIClient
from ralph.sync.workspace_sync import WorkspaceSync

router = APIRouter(prefix="/users/{user_id}/workspace", tags=["workspace"])


# Request/Response Models


class FileMetadataResponse(BaseModel):
    """Response for single file operations."""

    path: str
    hash: str
    size: int


class SyncRequest(BaseModel):
    """Request to trigger sync."""

    direction: Literal["to_openwebui", "from_openwebui", "bidirectional"] = "bidirectional"


# Dependencies


def get_workspace_path(user_id: str) -> Path:
    """Get workspace directory for a user."""
    settings = get_settings()
    if settings.agent_workspace:
        # Shared workspace (e.g., a codebase)
        return Path(settings.agent_workspace)
    # Per-user isolated workspace
    workspace = Path(settings.user_data_dir) / user_id / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def get_openwebui_client() -> OpenWebUIClient | None:
    """Get OpenWebUI client if configured."""
    settings = get_settings()
    if not settings.openwebui_url or not settings.openwebui_api_key:
        return None
    return OpenWebUIClient(
        base_url=settings.openwebui_url,
        api_key=settings.openwebui_api_key,
    )


async def get_workspace_sync(user_id: str) -> WorkspaceSync:
    """Get workspace sync service for a user."""
    workspace_path = get_workspace_path(user_id)
    openwebui_client = get_openwebui_client()
    sync = WorkspaceSync(
        workspace_path=workspace_path,
        user_id=user_id,
        openwebui_client=openwebui_client,
    )
    await sync.load_state()
    return sync


# Type alias for dependency
WorkspaceSyncDep = Annotated[WorkspaceSync, Depends(get_workspace_sync)]


# Endpoints


@router.get("/files", response_model=WorkspaceIndex)
async def list_workspace_files(
    user_id: str,
    refresh: bool = False,
) -> WorkspaceIndex:
    """
    List all files in workspace with hashes.

    Args:
        user_id: User ID.
        refresh: If True, rescan workspace before returning.

    Returns:
        Workspace file index.

    """
    workspace_path = get_workspace_path(user_id)
    sync = WorkspaceSync(workspace_path=workspace_path, user_id=user_id)

    if refresh:
        files = await sync.refresh_index()
    else:
        await sync.load_state()
        files = sync.get_file_index()

    total_size = sum(f.size for f in files)

    return WorkspaceIndex(
        user_id=user_id,
        files=files,
        total_size=total_size,
    )


@router.get("/files/{path:path}")
async def get_workspace_file(
    user_id: str,
    path: str,
) -> Response:
    """
    Download file content.

    Args:
        user_id: User ID.
        path: File path within workspace.

    Returns:
        File content as bytes.

    """
    workspace_path = get_workspace_path(user_id)
    sync = WorkspaceSync(workspace_path=workspace_path, user_id=user_id)

    try:
        content = await sync.read_file(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {path}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Guess content type from extension
    suffix = Path(path).suffix.lower()
    content_type_map = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".html": "text/html",
        ".css": "text/css",
        ".xml": "application/xml",
        ".yaml": "application/x-yaml",
        ".yml": "application/x-yaml",
    }
    content_type = content_type_map.get(suffix, "application/octet-stream")

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{Path(path).name}"',
        },
    )


@router.put("/files/{path:path}", response_model=FileMetadataResponse)
async def put_workspace_file(
    user_id: str,
    path: str,
    request: Request,
) -> FileMetadataResponse:
    """
    Upload/update file in workspace.

    Args:
        user_id: User ID.
        path: File path within workspace.
        request: Request with file content in body.

    Returns:
        Updated file metadata.

    """
    workspace_path = get_workspace_path(user_id)
    sync = WorkspaceSync(workspace_path=workspace_path, user_id=user_id)

    # Read content from request body
    content = await request.body()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file content")

    try:
        metadata = await sync.write_file(path, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return FileMetadataResponse(
        path=metadata.path,
        hash=metadata.hash,
        size=metadata.size,
    )


@router.delete("/files/{path:path}")
async def delete_workspace_file(
    user_id: str,
    path: str,
) -> dict[str, bool]:
    """
    Delete file from workspace.

    Args:
        user_id: User ID.
        path: File path within workspace.

    Returns:
        Deletion confirmation.

    """
    workspace_path = get_workspace_path(user_id)
    sync = WorkspaceSync(workspace_path=workspace_path, user_id=user_id)

    try:
        deleted = await sync.delete_file(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not deleted:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    return {"deleted": True}


@router.post("/sync", response_model=SyncResult)
async def trigger_sync(
    user_id: str,
    sync_request: SyncRequest,
) -> SyncResult:
    """
    Trigger workspace sync with OpenWebUI.

    Args:
        user_id: User ID.
        sync_request: Sync direction configuration.

    Returns:
        Sync result with counts and errors.

    """
    workspace_path = get_workspace_path(user_id)
    openwebui_client = get_openwebui_client()

    if openwebui_client is None:
        raise HTTPException(
            status_code=503,
            detail="OpenWebUI sync not configured. Set RALPH_OPENWEBUI_URL and RALPH_OPENWEBUI_API_KEY.",
        )

    sync = WorkspaceSync(
        workspace_path=workspace_path,
        user_id=user_id,
        openwebui_client=openwebui_client,
    )

    result = SyncResult(success=True)

    if sync_request.direction in ("to_openwebui", "bidirectional"):
        to_result = await sync.sync_to_openwebui()
        result.files_uploaded = to_result.files_uploaded
        result.files_deleted += to_result.files_deleted
        result.errors.extend(to_result.errors)
        if not to_result.success:
            result.success = False

    if sync_request.direction in ("from_openwebui", "bidirectional"):
        from_result = await sync.sync_from_openwebui()
        result.files_downloaded = from_result.files_downloaded
        result.errors.extend(from_result.errors)
        if not from_result.success:
            result.success = False

    # Close OpenWebUI client
    await openwebui_client.close()

    return result
