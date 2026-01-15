"""
Notes API adapter for git-backed memory blocks.

Provides Notes-compatible endpoints that NoteEditor can use to
edit memory blocks stored in git with markdown + YAML frontmatter.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Annotated, Any

import markdown
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from youlab_server.server.users import get_current_user, get_storage_manager
from youlab_server.storage.blocks import UserBlockManager
from youlab_server.storage.git import GitUserStorageManager, parse_frontmatter

log = structlog.get_logger()
router = APIRouter(prefix="/you/notes", tags=["notes-adapter"])

# Type aliases
StorageDep = Annotated[GitUserStorageManager, Depends(get_storage_manager)]


# =============================================================================
# Pydantic Models (Notes API compatible)
# =============================================================================


class NoteContent(BaseModel):
    """TipTap content structure."""

    model_config = ConfigDict(populate_by_name=True)

    json_content: dict[str, Any] | None = Field(
        default=None, alias="json", serialization_alias="json"
    )  # Always null - we don't store TipTap JSON
    html: str = ""
    md: str = ""


class NoteVersion(BaseModel):
    """A version snapshot for undo/redo."""

    model_config = ConfigDict(populate_by_name=True)

    json_content: dict[str, Any] | None = Field(
        default=None, alias="json", serialization_alias="json"
    )
    html: str = ""
    md: str = ""
    sha: str = ""  # Git commit SHA (extension)
    message: str = ""  # Commit message (extension)
    timestamp: str = ""  # ISO timestamp (extension)


class NoteData(BaseModel):
    """Note data payload."""

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
    """Summary for list endpoint."""

    id: str
    title: str
    data: dict[str, Any] | None = None
    updated_at: int
    created_at: int


class NoteForm(BaseModel):
    """Form for create/update."""

    title: str
    data: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    access_control: dict[str, Any] | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def _md_to_html(md_content: str) -> str:
    """Convert markdown to HTML."""
    return markdown.markdown(
        md_content,
        extensions=["fenced_code", "tables", "nl2br"],
    )


def _parse_timestamp(updated_at_str: str) -> int:
    """Parse ISO timestamp to nanoseconds epoch."""
    try:
        if updated_at_str:
            dt = datetime.fromisoformat(updated_at_str)
            return int(dt.timestamp() * 1_000_000_000)
    except (ValueError, TypeError):
        # Invalid timestamp format, fall back to current time
        log.debug("invalid_timestamp", timestamp=updated_at_str)
    return int(time.time() * 1_000_000_000)


def _block_to_note(
    label: str,
    user_id: str,
    content: str,
    metadata: dict[str, Any],
    versions: list[dict[str, Any]],
) -> NoteResponse:
    """Convert a memory block to NoteResponse format."""
    _, body = parse_frontmatter(content)
    html = _md_to_html(body)

    # Convert git versions to NoteVersion format
    note_versions = []
    for v in versions:
        v_content = v.get("content", "")
        _, v_body = parse_frontmatter(v_content) if v_content else ({}, "")
        note_versions.append(
            NoteVersion(
                html=_md_to_html(v_body) if v_body else "",
                md=v_body,
                sha=v.get("sha", ""),
                message=v.get("message", ""),
                timestamp=v.get("timestamp", ""),
            )
        )

    # Extract timestamps from metadata
    updated_at = _parse_timestamp(metadata.get("updated_at", ""))

    # Use title from metadata or generate from label
    title = metadata.get("title", label.replace("_", " ").title())

    return NoteResponse(
        id=label,
        user_id=user_id,
        title=title,
        data=NoteData(
            content=NoteContent(html=html, md=body),
            versions=note_versions,
            files=None,
        ),
        meta=metadata.get("meta"),
        access_control=metadata.get("access_control"),
        created_at=updated_at,  # We don't track created_at separately
        updated_at=updated_at,
        write_access=True,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/", response_model=list[NoteItemResponse])
async def list_notes(
    request: Request,
    storage: StorageDep,
) -> list[NoteItemResponse]:
    """List all memory blocks as notes."""
    user = await get_current_user(request)
    user_storage = storage.get(user.id)

    if not user_storage.exists:
        return []

    manager = UserBlockManager(user.id, user_storage)
    labels = manager.list_blocks()

    notes = []
    for label in labels:
        metadata = manager.get_block_metadata(label) or {}
        updated_at = _parse_timestamp(metadata.get("updated_at", ""))
        title = metadata.get("title", label.replace("_", " ").title())

        notes.append(
            NoteItemResponse(
                id=label,
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
    storage: StorageDep,
) -> NoteResponse:
    """Get a memory block as a note."""
    user = await get_current_user(request)
    user_storage = storage.get(user.id)

    if not user_storage.exists:
        raise HTTPException(status_code=404, detail="User storage not found")

    manager = UserBlockManager(user.id, user_storage)

    content = manager.get_block_markdown(note_id)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Block {note_id} not found")

    metadata = manager.get_block_metadata(note_id) or {}

    # Get version history with content
    history = manager.get_history(note_id, limit=20)
    versions_with_content = []
    for v in history:
        v_content = manager.get_version(note_id, v["sha"])
        versions_with_content.append({**v, "content": v_content or ""})

    return _block_to_note(
        label=note_id,
        user_id=user.id,
        content=content,
        metadata=metadata,
        versions=versions_with_content,
    )


@router.post("/{note_id}/update", response_model=NoteResponse)
async def update_note_by_id(
    request: Request,
    note_id: str,
    form_data: NoteForm,
    storage: StorageDep,
) -> NoteResponse:
    """Update a memory block via notes API."""
    user = await get_current_user(request)
    user_storage = storage.get(user.id)

    if not user_storage.exists:
        raise HTTPException(status_code=404, detail="User storage not found")

    manager = UserBlockManager(user.id, user_storage)

    # Check block exists
    if manager.get_block_markdown(note_id) is None:
        raise HTTPException(status_code=404, detail=f"Block {note_id} not found")

    # Extract markdown content from form_data
    md_content = ""
    if form_data.data and "content" in form_data.data:
        content_data = form_data.data["content"]
        if isinstance(content_data, dict):
            md_content = content_data.get("md", "")

    if not md_content:
        raise HTTPException(status_code=400, detail="No markdown content provided")

    # Update the block with title (this handles frontmatter and Letta sync)
    manager.update_block(
        label=note_id,
        content=md_content,
        message=f"Update {note_id}",
        title=form_data.title,
        sync_to_letta=True,
    )

    # Return updated note
    content = manager.get_block_markdown(note_id) or ""
    metadata = manager.get_block_metadata(note_id) or {}

    history = manager.get_history(note_id, limit=20)
    versions_with_content = []
    for v in history:
        v_content = manager.get_version(note_id, v["sha"])
        versions_with_content.append({**v, "content": v_content or ""})

    return _block_to_note(
        label=note_id,
        user_id=user.id,
        content=content,
        metadata=metadata,
        versions=versions_with_content,
    )
