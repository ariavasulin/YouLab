"""Memory block CRUD API endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from youlab_server.server.users import get_storage_manager
from youlab_server.storage.blocks import UserBlockManager
from youlab_server.storage.git import GitUserStorageManager, parse_frontmatter

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
    content: str  # Full markdown with frontmatter
    body: str  # Body only (for editor)
    metadata: dict[str, Any]  # Parsed frontmatter
    pending_diffs: int


class BlockUpdateRequest(BaseModel):
    """Request to update a block."""

    content: str  # Markdown content (body or full)
    message: str | None = None
    schema_ref: str | None = None  # Optional schema reference (renamed to avoid pydantic conflict)


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
    old_value: str | None = None
    new_value: str | None = None


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
    content = manager.get_block_markdown(label)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Block {label} not found")

    body = manager.get_block_body(label) or ""
    metadata = manager.get_block_metadata(label) or {}
    counts = manager.count_pending_diffs()

    return BlockDetail(
        label=label,
        content=content,
        body=body,
        metadata=metadata,
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
    commit_sha = manager.update_block(
        label=label,
        content=request.content,
        message=request.message,
        schema=request.schema_ref,
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
) -> dict[str, Any]:
    """Get block content at a specific version."""
    manager = get_block_manager(user_id, storage)
    content = manager.get_version(label, commit_sha)
    if content is None:
        raise HTTPException(status_code=404, detail="Version not found")

    # Parse frontmatter from historical content
    metadata, body = parse_frontmatter(content)

    return {
        "content": content,
        "body": body,
        "metadata": metadata,
        "sha": commit_sha,
    }


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
