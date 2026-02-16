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
    hash: str
    size: int
    modified: datetime
    source: Literal["ralph", "openwebui", "local"] = "ralph"
    openwebui_file_id: str | None = None
    synced_at: datetime | None = None


class SyncState(BaseModel):
    """
    Persistent sync state for a user's workspace.

    Stored as JSON in the workspace directory.
    """

    version: int = 1
    user_id: str
    knowledge_id: str | None = None
    last_sync: datetime | None = None
    files: dict[str, FileMetadata] = Field(default_factory=dict)


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    files_uploaded: int = 0
    files_downloaded: int = 0
    files_deleted: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class FileIndexEntry(BaseModel):
    """Lightweight file index entry for API responses."""

    path: str
    hash: str
    size: int
    modified: datetime


class WorkspaceIndex(BaseModel):
    """Response model for workspace file listing."""

    user_id: str
    files: list[FileIndexEntry]
    total_size: int
