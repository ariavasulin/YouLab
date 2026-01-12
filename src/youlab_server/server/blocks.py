"""Memory block CRUD API endpoints."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from youlab_server.server.users import get_storage_manager
from youlab_server.storage.blocks import UserBlockManager
from youlab_server.storage.git import GitUserStorageManager

log = structlog.get_logger()
router = APIRouter(prefix="/users/{user_id}/blocks", tags=["blocks"])

# Type alias for dependency injection
StorageDep = Annotated[GitUserStorageManager, Depends(get_storage_manager)]


def get_block_manager(user_id: str, storage: StorageDep) -> UserBlockManager:
    """Get UserBlockManager for a user."""
    user_storage = storage.get(user_id)
    if not user_storage.exists:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return UserBlockManager(user_id, user_storage)


# =============================================================================
# Request/Response Models
# =============================================================================


class BlockSummary(BaseModel):
    """Summary of a memory block."""

    label: str
    pending_diffs: int


class BlockDetail(BaseModel):
    """Detailed block information."""

    label: str
    content_toml: str
    content_markdown: str
    pending_diffs: int


class BlockUpdateRequest(BaseModel):
    """Request to update a block."""

    content: str
    format: str = "markdown"  # "markdown" or "toml"
    message: str | None = None


class BlockUpdateResponse(BaseModel):
    """Response after updating a block."""

    commit_sha: str
    label: str


class VersionInfo(BaseModel):
    """Information about a block version."""

    sha: str
    message: str
    author: str
    timestamp: str
    is_current: bool


class RestoreRequest(BaseModel):
    """Request to restore a previous version."""

    commit_sha: str


class DiffSummary(BaseModel):
    """Summary of a pending diff."""

    id: str
    block: str
    field: str | None
    operation: str
    reasoning: str
    confidence: str
    created_at: str
    agent_id: str


class ApproveResponse(BaseModel):
    """Response after approving a diff."""

    diff_id: str
    commit_sha: str


# =============================================================================
# Block Endpoints
# =============================================================================


@router.get("", response_model=list[BlockSummary])
async def list_blocks(
    user_id: str,
    storage: StorageDep,
) -> list[BlockSummary]:
    """List all memory blocks for a user."""
    manager = get_block_manager(user_id, storage)
    labels = manager.list_blocks()
    counts = manager.count_pending_diffs()

    return [BlockSummary(label=label, pending_diffs=counts.get(label, 0)) for label in labels]


@router.get("/diffs/counts")
async def get_diff_counts(
    user_id: str,
    storage: StorageDep,
) -> dict[str, int]:
    """Get pending diff counts per block."""
    manager = get_block_manager(user_id, storage)
    return manager.count_pending_diffs()


@router.get("/{label}", response_model=BlockDetail)
async def get_block(
    user_id: str,
    label: str,
    storage: StorageDep,
) -> BlockDetail:
    """Get a specific memory block."""
    manager = get_block_manager(user_id, storage)
    toml_content = manager.get_block_toml(label)
    if toml_content is None:
        raise HTTPException(status_code=404, detail=f"Block {label} not found")

    markdown = manager.get_block_markdown(label) or ""
    counts = manager.count_pending_diffs()

    return BlockDetail(
        label=label,
        content_toml=toml_content,
        content_markdown=markdown,
        pending_diffs=counts.get(label, 0),
    )


@router.put("/{label}", response_model=BlockUpdateResponse)
async def update_block(
    user_id: str,
    label: str,
    request: BlockUpdateRequest,
    storage: StorageDep,
) -> BlockUpdateResponse:
    """Update a memory block (user edit)."""
    manager = get_block_manager(user_id, storage)
    if request.format == "markdown":
        commit_sha = manager.update_block_from_markdown(
            label=label,
            markdown=request.content,
            message=request.message,
        )
    else:
        commit_sha = manager.update_block_from_toml(
            label=label,
            toml_content=request.content,
            message=request.message,
        )

    return BlockUpdateResponse(commit_sha=commit_sha, label=label)


# =============================================================================
# Version History Endpoints
# =============================================================================


@router.get("/{label}/history", response_model=list[VersionInfo])
async def get_block_history(
    user_id: str,
    label: str,
    storage: StorageDep,
    limit: Annotated[int, Query(le=100)] = 20,
) -> list[VersionInfo]:
    """Get version history for a block."""
    manager = get_block_manager(user_id, storage)
    history = manager.get_history(label, limit)
    return [VersionInfo(**v) for v in history]


@router.get("/{label}/versions/{commit_sha}")
async def get_block_version(
    user_id: str,
    label: str,
    commit_sha: str,
    storage: StorageDep,
) -> dict[str, str]:
    """Get block content at a specific version."""
    manager = get_block_manager(user_id, storage)
    content = manager.get_version(label, commit_sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"content": content, "sha": commit_sha}


@router.post("/{label}/restore", response_model=BlockUpdateResponse)
async def restore_block_version(
    user_id: str,
    label: str,
    request: RestoreRequest,
    storage: StorageDep,
) -> BlockUpdateResponse:
    """Restore a block to a previous version."""
    manager = get_block_manager(user_id, storage)
    try:
        commit_sha = manager.restore_version(label, request.commit_sha)
        return BlockUpdateResponse(commit_sha=commit_sha, label=label)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


# =============================================================================
# Pending Diff Endpoints
# =============================================================================


@router.get("/{label}/diffs", response_model=list[DiffSummary])
async def list_block_diffs(
    user_id: str,
    label: str,
    storage: StorageDep,
) -> list[DiffSummary]:
    """List pending diffs for a block."""
    manager = get_block_manager(user_id, storage)
    diffs = manager.list_pending_diffs(label)
    return [DiffSummary(**d) for d in diffs]


@router.post("/{label}/diffs/{diff_id}/approve", response_model=ApproveResponse)
async def approve_diff(
    user_id: str,
    label: str,
    diff_id: str,
    storage: StorageDep,
) -> ApproveResponse:
    """Approve and apply a pending diff."""
    manager = get_block_manager(user_id, storage)
    try:
        commit_sha = manager.approve_diff(diff_id)
        return ApproveResponse(diff_id=diff_id, commit_sha=commit_sha)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{label}/diffs/{diff_id}/reject")
async def reject_diff(
    user_id: str,
    label: str,
    diff_id: str,
    storage: StorageDep,
    reason: Annotated[str | None, Query()] = None,
) -> dict[str, str]:
    """Reject a pending diff."""
    manager = get_block_manager(user_id, storage)
    manager.reject_diff(diff_id, reason)
    return {"status": "rejected", "diff_id": diff_id}
