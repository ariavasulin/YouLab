"""Data models for workspace sync."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic needs runtime access
from typing import Literal

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    """
    Metadata for a synced file.

    Matches the format used by openwebui-content-sync for compatibility.
    """

    path: str
    """Relative path within the workspace."""

    hash: str
    """SHA256 hash of file content (prefixed with 'sha256:')."""

    size: int
    """File size in bytes."""

    modified: datetime
    """Last modification time."""

    source: Literal["ralph", "openwebui", "local"] = "ralph"
    """Origin of the most recent version."""

    openwebui_file_id: str | None = None
    """OpenWebUI file ID if synced to KB."""

    synced_at: datetime | None = None
    """Last sync timestamp."""


class SyncState(BaseModel):
    """
    Persistent sync state for a user's workspace.

    Stored as JSON in the workspace directory.
    """

    version: int = 1
    """Schema version for future migrations."""

    user_id: str
    """User ID this state belongs to."""

    knowledge_id: str | None = None
    """OpenWebUI knowledge base ID for this user."""

    last_sync: datetime | None = None
    """Timestamp of last successful sync."""

    files: dict[str, FileMetadata] = Field(default_factory=dict)
    """Map of relative path -> file metadata."""


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    """Whether sync completed successfully."""

    files_uploaded: int = 0
    """Number of files uploaded to OpenWebUI."""

    files_downloaded: int = 0
    """Number of files downloaded from OpenWebUI."""

    files_deleted: int = 0
    """Number of files deleted."""

    errors: list[str] = Field(default_factory=list)
    """Any errors encountered during sync."""

    duration_ms: int = 0
    """Sync duration in milliseconds."""


class FileIndexEntry(BaseModel):
    """
    Entry in the workspace file index.

    Lightweight version for API responses.
    """

    path: str
    """Relative file path."""

    hash: str
    """SHA256 hash (prefixed with 'sha256:')."""

    size: int
    """File size in bytes."""

    modified: datetime
    """Last modified timestamp."""


class WorkspaceIndex(BaseModel):
    """Response model for workspace file listing."""

    user_id: str
    files: list[FileIndexEntry]
    total_size: int
    """Total size of all files in bytes."""
