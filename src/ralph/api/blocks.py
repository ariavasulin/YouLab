"""Memory blocks API endpoints backed by Dolt."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic needs runtime access
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ralph.dolt import DoltClient, get_dolt_client

router = APIRouter(prefix="/users/{user_id}/blocks", tags=["blocks"])


# Request/Response Models
class BlockResponse(BaseModel):
    """Memory block response."""

    user_id: str
    label: str
    title: str | None
    body: str | None
    schema_ref: str | None
    updated_at: datetime
    pending_diffs: int = 0


class BlockListResponse(BaseModel):
    """List of memory blocks."""

    blocks: list[BlockResponse]


class BlockUpdateRequest(BaseModel):
    """Request to update a block."""

    body: str
    title: str | None = None
    schema_ref: str | None = None
    message: str | None = None


class VersionResponse(BaseModel):
    """Version history entry."""

    commit_sha: str
    message: str
    author: str
    timestamp: datetime
    is_current: bool


class VersionListResponse(BaseModel):
    """List of versions."""

    versions: list[VersionResponse]


class ProposalResponse(BaseModel):
    """Pending proposal response."""

    branch_name: str
    block_label: str
    agent_id: str
    reasoning: str
    confidence: str
    created_at: datetime


class ProposalDiffResponse(BaseModel):
    """Diff for a pending proposal - matches frontend PendingDiff interface."""

    id: str  # Use branch_name as unique ID
    block: str  # Block label
    field: str | None = None  # Always null for body-level diffs
    operation: str = (
        "full_replace"  # Full document replacement (frontend expects this for proper diff display)
    )
    reasoning: str
    confidence: str
    created_at: datetime | None  # Will be serialized as createdAt
    agent_id: str  # Will be serialized as agentId
    old_value: str | None = None  # Current body content
    new_value: str | None = None  # Proposed body content

    model_config = {"populate_by_name": True}


class ProposeEditRequest(BaseModel):
    """Request to propose an edit (from agent)."""

    agent_id: str
    body: str
    reasoning: str
    confidence: str = "medium"


class ProposeEditResponse(BaseModel):
    """Response from proposing an edit."""

    branch_name: str
    success: bool
    error: str | None = None


class RestoreRequest(BaseModel):
    """Request to restore a block to a previous version."""

    commit_sha: str


# Dependency
DoltDep = Annotated[DoltClient, Depends(get_dolt_client)]


# Endpoints
@router.get("", response_model=list[BlockResponse])
async def list_blocks(user_id: str, dolt: DoltDep) -> list[BlockResponse]:
    """List all memory blocks for a user."""
    blocks = await dolt.list_blocks(user_id)

    # Get per-block pending counts
    proposals = await dolt.list_proposals(user_id)
    pending_by_block = {p.block_label: 1 for p in proposals}

    return [
        BlockResponse(
            user_id=b.user_id,
            label=b.label,
            title=b.title,
            body=b.body,
            schema_ref=b.schema_ref,
            updated_at=b.updated_at,
            pending_diffs=pending_by_block.get(b.label, 0),
        )
        for b in blocks
    ]


@router.get("/{label}", response_model=BlockResponse)
async def get_block(user_id: str, label: str, dolt: DoltDep) -> BlockResponse:
    """Get a specific memory block."""
    block = await dolt.get_block(user_id, label)
    if not block:
        raise HTTPException(status_code=404, detail=f"Block {label} not found")

    pending = 1 if await dolt.get_proposal_diff(user_id, label) else 0

    return BlockResponse(
        user_id=block.user_id,
        label=block.label,
        title=block.title,
        body=block.body,
        schema_ref=block.schema_ref,
        updated_at=block.updated_at,
        pending_diffs=pending,
    )


@router.put("/{label}", response_model=BlockResponse)
async def update_block(
    user_id: str,
    label: str,
    request: BlockUpdateRequest,
    dolt: DoltDep,
) -> BlockResponse:
    """Update a memory block (user edit)."""
    await dolt.update_block(
        user_id=user_id,
        label=label,
        body=request.body,
        title=request.title,
        schema_ref=request.schema_ref,
        author="user",
        message=request.message,
    )

    block = await dolt.get_block(user_id, label)
    if not block:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated block")

    return BlockResponse(
        user_id=block.user_id,
        label=block.label,
        title=block.title,
        body=block.body,
        schema_ref=block.schema_ref,
        updated_at=block.updated_at,
        pending_diffs=0,
    )


@router.delete("/{label}")
async def delete_block(user_id: str, label: str, dolt: DoltDep) -> dict[str, str | bool]:
    """Delete a memory block."""
    result = await dolt.delete_block(user_id, label)
    if not result:
        raise HTTPException(status_code=404, detail=f"Block {label} not found")
    return {"deleted": True, "commit_sha": result}


@router.get("/{label}/history", response_model=VersionListResponse)
async def get_block_history(
    user_id: str,
    label: str,
    dolt: DoltDep,
    limit: int = 20,
) -> VersionListResponse:
    """Get version history for a block."""
    versions = await dolt.get_block_history(user_id, label, limit=limit)
    return VersionListResponse(
        versions=[
            VersionResponse(
                commit_sha=v.commit_hash,
                message=v.message,
                author=v.author,
                timestamp=v.timestamp,
                is_current=v.is_current,
            )
            for v in versions
        ]
    )


@router.get("/{label}/versions/{commit_sha}", response_model=BlockResponse)
async def get_block_at_version(
    user_id: str,
    label: str,
    commit_sha: str,
    dolt: DoltDep,
) -> BlockResponse:
    """Get a block at a specific version."""
    block = await dolt.get_block_at_version(user_id, label, commit_sha)
    if not block:
        raise HTTPException(
            status_code=404, detail=f"Block {label} not found at commit {commit_sha}"
        )
    return BlockResponse(
        user_id=block.user_id,
        label=block.label,
        title=block.title,
        body=block.body,
        schema_ref=block.schema_ref,
        updated_at=block.updated_at,
        pending_diffs=0,
    )


@router.post("/{label}/restore", response_model=BlockResponse)
async def restore_block(
    user_id: str,
    label: str,
    request: RestoreRequest,
    dolt: DoltDep,
) -> BlockResponse:
    """Restore a block to a previous version."""
    try:
        await dolt.restore_block(user_id, label, request.commit_sha)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    block = await dolt.get_block(user_id, label)
    if not block:
        raise HTTPException(status_code=500, detail="Failed to retrieve restored block")

    return BlockResponse(
        user_id=block.user_id,
        label=block.label,
        title=block.title,
        body=block.body,
        schema_ref=block.schema_ref,
        updated_at=block.updated_at,
        pending_diffs=0,
    )


# Proposal endpoints
@router.get("/{label}/diffs", response_model=list[ProposalDiffResponse])
async def get_pending_diffs(
    user_id: str,
    label: str,
    dolt: DoltDep,
) -> list[ProposalDiffResponse]:
    """Get pending diffs for a block."""
    diff = await dolt.get_proposal_diff(user_id, label)
    if not diff:
        return []
    # Convert branch_name to URL-safe ID (replace / with __)
    branch_name = str(diff["branch_name"])
    url_safe_id = branch_name.replace("/", "__")
    return [
        ProposalDiffResponse(
            id=url_safe_id,
            block=str(diff["block_label"]),
            field=None,
            operation="full_replace",  # Body-level diffs are full document replacements
            reasoning=str(diff["reasoning"]) if diff["reasoning"] else "",
            confidence=str(diff["confidence"]) if diff["confidence"] else "medium",
            created_at=diff["created_at"],  # type: ignore[arg-type]
            agent_id=str(diff["agent_id"]) if diff["agent_id"] else "unknown",
            old_value=diff["current_body"] if isinstance(diff["current_body"], str) else None,
            new_value=diff["proposed_body"] if isinstance(diff["proposed_body"], str) else None,
        )
    ]


@router.post("/{label}/propose", response_model=ProposeEditResponse)
async def propose_edit(
    user_id: str,
    label: str,
    request: ProposeEditRequest,
    dolt: DoltDep,
) -> ProposeEditResponse:
    """Propose an edit to a block (called by agents)."""
    try:
        branch_name = await dolt.create_proposal(
            user_id=user_id,
            block_label=label,
            new_body=request.body,
            agent_id=request.agent_id,
            reasoning=request.reasoning,
            confidence=request.confidence,
        )
        return ProposeEditResponse(branch_name=branch_name, success=True)
    except Exception as e:
        return ProposeEditResponse(branch_name="", success=False, error=str(e))


@router.post("/{label}/diffs/{diff_id}/approve")
async def approve_diff(
    user_id: str,
    label: str,
    diff_id: str,  # Ignored - we use label as key
    dolt: DoltDep,
) -> dict[str, str | bool]:
    """Approve a pending diff."""
    try:
        commit_sha = await dolt.approve_proposal(user_id, label)
        return {"approved": True, "commit_sha": commit_sha}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{label}/diffs/{diff_id}/reject")
async def reject_diff(
    user_id: str,
    label: str,
    diff_id: str,  # Ignored - we use label as key
    dolt: DoltDep,
) -> dict[str, bool]:
    """Reject a pending diff."""
    result = await dolt.reject_proposal(user_id, label)
    if not result:
        raise HTTPException(status_code=404, detail="No pending proposal found")
    return {"rejected": True}
