"""
Notes API adapter - bridges OpenWebUI Notes format to Dolt-backed blocks.

This adapter provides Notes-compatible endpoints that OpenWebUI's NoteEditor
can use to edit memory blocks stored in Dolt with version history.

Endpoints:
- GET  /you/notes/           - List notes for user
- GET  /you/notes/{note_id}  - Get single note with versions
- POST /you/notes/{id}/update - Update a note
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ralph.dolt import DoltClient, MemoryBlock, VersionInfo, get_dolt_client

if TYPE_CHECKING:
    from datetime import datetime

log = structlog.get_logger()
router = APIRouter(prefix="/you/notes", tags=["notes-adapter"])

# Type alias for dependency injection
DoltDep = Annotated[DoltClient, Depends(get_dolt_client)]


# =============================================================================
# Pydantic Models (OpenWebUI Notes API compatible)
# =============================================================================


class NoteContent(BaseModel):
    """TipTap content structure - matches OpenWebUI's NoteContent."""

    model_config = ConfigDict(populate_by_name=True)

    json_content: dict[str, Any] | None = Field(
        default=None, alias="json", serialization_alias="json"
    )  # Always null - we don't store TipTap JSON
    html: str = ""
    md: str = ""


class NoteVersion(BaseModel):
    """Version entry matching OpenWebUI format with YouLab extensions."""

    model_config = ConfigDict(populate_by_name=True)

    json_content: dict[str, Any] | None = Field(
        default=None, alias="json", serialization_alias="json"
    )
    html: str = ""
    md: str = ""
    sha: str = ""  # Dolt commit hash
    message: str = ""  # Commit message
    timestamp: str = ""  # ISO timestamp


class NoteData(BaseModel):
    """Note data payload matching OpenWebUI's NoteData."""

    content: NoteContent
    versions: list[NoteVersion] = []
    files: list[dict[str, Any]] | None = None


class NoteModel(BaseModel):
    """Full note model matching OpenWebUI's NoteModel."""

    id: str
    user_id: str
    title: str
    data: NoteData
    meta: dict[str, Any] | None = None
    access_control: dict[str, Any] | None = None
    created_at: int  # nanoseconds epoch
    updated_at: int  # nanoseconds epoch


class NoteResponse(NoteModel):
    """Note response with write_access flag."""

    write_access: bool = True


class NoteItemResponse(BaseModel):
    """Summary for list endpoint (lighter weight)."""

    id: str
    title: str
    data: dict[str, Any] | None = None
    updated_at: int
    created_at: int


class NoteForm(BaseModel):
    """Form for create/update - matches OpenWebUI's NoteForm."""

    title: str
    data: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    access_control: dict[str, Any] | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def _md_to_html(md_content: str) -> str:
    """
    Simple markdown to HTML conversion.

    For now, just wraps in a div. Could use markdown library for proper
    conversion if TipTap needs rendered HTML.
    """
    # Basic HTML escaping and paragraph conversion
    html = md_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert newlines to paragraphs
    paragraphs = html.split("\n\n")
    if len(paragraphs) > 1:
        html = "".join(f"<p>{p}</p>" for p in paragraphs if p.strip())
    return f"<div>{html}</div>"


def _datetime_to_nanos(dt: datetime) -> int:
    """Convert datetime to nanoseconds epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def _version_to_note_version(version: VersionInfo, body: str | None = None) -> NoteVersion:
    """Convert a Dolt VersionInfo to NoteVersion format."""
    md = body or ""
    return NoteVersion(
        html=_md_to_html(md) if md else "",
        md=md,
        sha=version.commit_hash,
        message=version.message,
        timestamp=version.timestamp.isoformat() if version.timestamp else "",
    )


def _block_to_note_response(
    block: MemoryBlock,
    versions: list[NoteVersion] | None = None,
) -> NoteResponse:
    """Convert a MemoryBlock to NoteResponse format."""
    body = block.body or ""
    html = _md_to_html(body)
    updated_at = _datetime_to_nanos(block.updated_at)

    return NoteResponse(
        id=block.label,
        user_id=block.user_id,
        title=block.title or block.label.replace("_", " ").title(),
        data=NoteData(
            content=NoteContent(html=html, md=body),
            versions=versions or [],
            files=None,
        ),
        meta=None,
        access_control=None,
        created_at=updated_at,  # We don't track created_at separately in Dolt schema
        updated_at=updated_at,
        write_access=True,
    )


async def _get_user_id_from_request(request: Request) -> str:
    """
    Extract user ID from request headers.

    User ID comes via X-User-Id header set by OpenWebUI.
    Falls back to Bearer token extraction if needed.
    """
    # Try X-User-Id header first (YouLab convention)
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return user_id

    # Try Authorization header as fallback
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        # Use token prefix as user_id (for development)
        # Real implementation would decode JWT
        uuid_length = 36
        return token[:uuid_length] if len(token) >= uuid_length else token

    raise HTTPException(status_code=401, detail="User authentication required")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=list[NoteItemResponse])
async def list_notes(
    request: Request,
    dolt: DoltDep,
) -> list[NoteItemResponse]:
    """List all memory blocks as notes for the current user."""
    user_id = await _get_user_id_from_request(request)

    blocks = await dolt.list_blocks(user_id)

    notes = []
    for block in blocks:
        updated_at = _datetime_to_nanos(block.updated_at)
        title = block.title or block.label.replace("_", " ").title()

        notes.append(
            NoteItemResponse(
                id=block.label,
                title=title,
                data=None,
                updated_at=updated_at,
                created_at=updated_at,
            )
        )

    return notes


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note_by_id(
    request: Request,
    note_id: str,
    dolt: DoltDep,
) -> NoteResponse:
    """Get a memory block as a note with version history."""
    user_id = await _get_user_id_from_request(request)

    block = await dolt.get_block(user_id, note_id)
    if not block:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    # Get version history
    history = await dolt.get_block_history(user_id, note_id, limit=20)

    # Convert versions - we need to get content for each version
    versions = []
    for version in history:
        # Get the block content at this specific version
        version_block = await dolt.get_block_at_version(user_id, note_id, version.commit_hash)
        version_body = version_block.body if version_block else ""
        versions.append(_version_to_note_version(version, version_body))

    return _block_to_note_response(block, versions)


@router.post("/{note_id}/update", response_model=NoteResponse)
async def update_note_by_id(
    request: Request,
    note_id: str,
    form_data: NoteForm,
    dolt: DoltDep,
) -> NoteResponse:
    """Update a memory block via notes API."""
    user_id = await _get_user_id_from_request(request)

    # Check block exists
    existing = await dolt.get_block(user_id, note_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

    # Extract markdown content from form_data
    md_content = ""
    if form_data.data and "content" in form_data.data:
        content_data = form_data.data["content"]
        if isinstance(content_data, dict):
            md_content = content_data.get("md", "")

    if not md_content:
        raise HTTPException(status_code=400, detail="No markdown content provided")

    # Update the block
    await dolt.update_block(
        user_id=user_id,
        label=note_id,
        body=md_content,
        title=form_data.title,
        author="user",
        message=f"Update {note_id}",
    )

    # Return updated note with fresh version history
    block = await dolt.get_block(user_id, note_id)
    if not block:
        raise HTTPException(status_code=500, detail="Failed to fetch updated block")

    history = await dolt.get_block_history(user_id, note_id, limit=20)
    versions = []
    for version in history:
        version_block = await dolt.get_block_at_version(user_id, note_id, version.commit_hash)
        version_body = version_block.body if version_block else ""
        versions.append(_version_to_note_version(version, version_body))

    return _block_to_note_response(block, versions)
