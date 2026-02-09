"""
Workspace sync service with file indexing.

Handles synchronization between Ralph workspace and OpenWebUI knowledge base.
Uses SHA256 hashing for change detection (same approach as openwebui-content-sync).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import structlog

from ralph.sync.models import FileIndexEntry, FileMetadata, SyncResult, SyncState

if TYPE_CHECKING:
    from ralph.sync.openwebui_client import OpenWebUIClient

log = structlog.get_logger()

# File size limit (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Default ignore patterns
DEFAULT_IGNORE_PATTERNS = {
    ".git",
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".env",
    ".env.*",
    "node_modules",
    "*.tmp",
    "*.swp",
    ".sync_state.json",
}


def compute_hash(content: bytes) -> str:
    """Compute SHA256 hash of content with prefix."""
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{digest}"


def should_ignore(path: Path, ignore_patterns: set[str]) -> bool:
    """Check if a path should be ignored based on patterns."""
    name = path.name
    for pattern in ignore_patterns:
        if pattern.startswith("*"):
            # Suffix match
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
        # Check if any parent matches
        for parent in path.parents:
            if parent.name in ignore_patterns:
                return True
    return False


class WorkspaceSync:
    """Service for syncing workspace files with OpenWebUI knowledge base."""

    def __init__(
        self,
        workspace_path: Path,
        user_id: str,
        openwebui_client: OpenWebUIClient | None = None,
        ignore_patterns: set[str] | None = None,
    ) -> None:
        self.workspace_path = workspace_path
        self.user_id = user_id
        self.openwebui_client = openwebui_client
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        self._state: SyncState | None = None

    @property
    def state_path(self) -> Path:
        """Path to sync state file."""
        return self.workspace_path / ".sync_state.json"

    async def load_state(self) -> SyncState:
        """Load sync state from disk or create new."""
        if self._state is not None:
            return self._state

        if self.state_path.exists():
            try:
                async with aiofiles.open(self.state_path) as f:
                    data = await f.read()
                    self._state = SyncState.model_validate_json(data)
            except Exception as e:
                log.warning("sync_state_load_failed", error=str(e), path=str(self.state_path))
                self._state = SyncState(user_id=self.user_id)
        else:
            self._state = SyncState(user_id=self.user_id)

        return self._state

    async def save_state(self) -> None:
        """Persist sync state to disk."""
        if self._state is None:
            return

        self.workspace_path.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(self.state_path, "w") as f:
            await f.write(self._state.model_dump_json(indent=2))

    async def scan_workspace(self) -> dict[str, FileMetadata]:
        """
        Scan workspace and compute file hashes.

        Returns a dict of relative path -> FileMetadata.
        """
        files: dict[str, FileMetadata] = {}

        if not self.workspace_path.exists():
            return files

        for file_path in self.workspace_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = file_path.relative_to(self.workspace_path)

            # Skip ignored files
            if should_ignore(rel_path, self.ignore_patterns):
                continue

            # Skip files that are too large
            stat = file_path.stat()
            if stat.st_size > MAX_FILE_SIZE:
                log.warning(
                    "file_too_large",
                    path=str(rel_path),
                    size=stat.st_size,
                    max_size=MAX_FILE_SIZE,
                )
                continue

            # Read and hash file
            try:
                async with aiofiles.open(file_path, "rb") as f:
                    content = await f.read()
                    file_hash = compute_hash(content)
            except OSError as e:
                log.warning("file_read_failed", path=str(rel_path), error=str(e))
                continue

            files[str(rel_path)] = FileMetadata(
                path=str(rel_path),
                hash=file_hash,
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                source="ralph",
            )

        return files

    def get_file_index(self) -> list[FileIndexEntry]:
        """
        Get current file index from state.

        This is a synchronous method for API responses.
        Requires state to be loaded first.
        """
        if self._state is None:
            return []

        return [
            FileIndexEntry(
                path=meta.path,
                hash=meta.hash,
                size=meta.size,
                modified=meta.modified,
            )
            for meta in self._state.files.values()
        ]

    async def refresh_index(self) -> list[FileIndexEntry]:
        """Scan workspace and update index. Returns current index."""
        state = await self.load_state()
        current_files = await self.scan_workspace()

        # Update state with current files
        # Preserve openwebui_file_id for files that haven't changed
        for path, meta in current_files.items():
            existing = state.files.get(path)
            if existing and existing.hash == meta.hash:
                # File unchanged, preserve OpenWebUI ID
                meta.openwebui_file_id = existing.openwebui_file_id
                meta.synced_at = existing.synced_at
            state.files[path] = meta

        # Remove files that no longer exist
        for path in list(state.files.keys()):
            if path not in current_files:
                del state.files[path]

        await self.save_state()
        return self.get_file_index()

    async def read_file(self, rel_path: str) -> bytes:
        """
        Read file content from workspace.

        Args:
            rel_path: Relative path within workspace.

        Returns:
            File content as bytes.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If path escapes workspace.

        """
        # Validate path doesn't escape workspace
        full_path = self.workspace_path / rel_path
        try:
            full_path.resolve().relative_to(self.workspace_path.resolve())
        except ValueError as e:
            raise ValueError(f"Path escapes workspace: {rel_path}") from e

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {rel_path}")

        if not full_path.is_file():
            raise ValueError(f"Not a file: {rel_path}")

        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def write_file(self, rel_path: str, content: bytes) -> FileMetadata:
        """
        Write file to workspace.

        Args:
            rel_path: Relative path within workspace.
            content: File content.

        Returns:
            Updated file metadata.

        Raises:
            ValueError: If path escapes workspace or file too large.

        """
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

        # Validate path doesn't escape workspace
        full_path = self.workspace_path / rel_path
        try:
            full_path.resolve().relative_to(self.workspace_path.resolve())
        except ValueError as e:
            raise ValueError(f"Path escapes workspace: {rel_path}") from e

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

        # Update state
        state = await self.load_state()
        file_hash = compute_hash(content)
        now = datetime.now(UTC)

        metadata = FileMetadata(
            path=rel_path,
            hash=file_hash,
            size=len(content),
            modified=now,
            source="ralph",
        )
        state.files[rel_path] = metadata
        await self.save_state()

        return metadata

    async def delete_file(self, rel_path: str) -> bool:
        """
        Delete file from workspace.

        Args:
            rel_path: Relative path within workspace.

        Returns:
            True if file was deleted.

        Raises:
            ValueError: If path escapes workspace.

        """
        # Validate path doesn't escape workspace
        full_path = self.workspace_path / rel_path
        try:
            full_path.resolve().relative_to(self.workspace_path.resolve())
        except ValueError as e:
            raise ValueError(f"Path escapes workspace: {rel_path}") from e

        if not full_path.exists():
            return False

        full_path.unlink()

        # Update state
        state = await self.load_state()
        if rel_path in state.files:
            del state.files[rel_path]
            await self.save_state()

        return True

    async def sync_to_openwebui(self) -> SyncResult:
        """
        Sync workspace files to OpenWebUI knowledge base.

        Returns:
            SyncResult with counts and any errors.

        """
        if self.openwebui_client is None:
            return SyncResult(success=False, errors=["OpenWebUI client not configured"])

        start_time = datetime.now(UTC)
        result = SyncResult(success=True)

        try:
            state = await self.load_state()
            current_files = await self.scan_workspace()

            # Ensure knowledge base exists
            if not state.knowledge_id:
                kb = await self.openwebui_client.get_or_create_knowledge(
                    f"workspace-{self.user_id}"
                )
                state.knowledge_id = kb["id"]

            # Sync each file
            for path, meta in current_files.items():
                existing = state.files.get(path)

                # Skip if unchanged and already synced
                if (
                    existing
                    and existing.hash == meta.hash
                    and existing.openwebui_file_id
                    and existing.synced_at
                ):
                    continue

                try:
                    # Read file content
                    content = await self.read_file(path)

                    # If file was previously synced but changed, delete old version
                    if existing and existing.openwebui_file_id:
                        await self.openwebui_client.delete_file(existing.openwebui_file_id)

                    # Upload new version
                    file_info = await self.openwebui_client.upload_file(
                        filename=Path(path).name,
                        content=content,
                    )
                    file_id = file_info["id"]

                    # Add to knowledge base
                    await self.openwebui_client.add_file_to_knowledge(
                        state.knowledge_id,  # type: ignore[arg-type]
                        file_id,
                    )

                    # Update metadata
                    meta.openwebui_file_id = file_id
                    meta.synced_at = datetime.now(UTC)
                    state.files[path] = meta
                    result.files_uploaded += 1

                except Exception as e:
                    log.error("sync_file_failed", path=path, error=str(e))
                    result.errors.append(f"{path}: {e}")

            # Handle deleted files
            for path, meta in list(state.files.items()):
                if path not in current_files and meta.openwebui_file_id:
                    try:
                        await self.openwebui_client.delete_file(meta.openwebui_file_id)
                        del state.files[path]
                        result.files_deleted += 1
                    except Exception as e:
                        log.error("delete_file_failed", path=path, error=str(e))
                        result.errors.append(f"delete {path}: {e}")

            state.last_sync = datetime.now(UTC)
            await self.save_state()

        except Exception as e:
            log.exception("sync_to_openwebui_failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        end_time = datetime.now(UTC)
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    async def sync_from_openwebui(self) -> SyncResult:
        """
        Sync files from OpenWebUI knowledge base to workspace.

        Returns:
            SyncResult with counts and any errors.

        """
        if self.openwebui_client is None:
            return SyncResult(success=False, errors=["OpenWebUI client not configured"])

        start_time = datetime.now(UTC)
        result = SyncResult(success=True)

        try:
            state = await self.load_state()

            if not state.knowledge_id:
                # No KB configured, nothing to sync
                return SyncResult(success=True)

            # Get files from knowledge base
            kb_files = await self.openwebui_client.get_knowledge_files(state.knowledge_id)

            for file_info in kb_files:
                file_id = file_info["id"]
                filename = file_info.get("meta", {}).get("name", file_info.get("filename", ""))

                if not filename:
                    continue

                # Find if we already have this file
                existing_path = None
                for path, meta in state.files.items():
                    if meta.openwebui_file_id == file_id:
                        existing_path = path
                        break

                # Use filename as path if new file
                target_path = existing_path or filename

                try:
                    # Download content
                    content = await self.openwebui_client.get_file_content(file_id)
                    new_hash = compute_hash(content)

                    # Check if local file is different
                    existing = state.files.get(target_path)
                    if existing and existing.hash == new_hash:
                        # No change needed
                        continue

                    # Write to workspace
                    await self.write_file(target_path, content)

                    # Update metadata
                    state.files[target_path] = FileMetadata(
                        path=target_path,
                        hash=new_hash,
                        size=len(content),
                        modified=datetime.now(UTC),
                        source="openwebui",
                        openwebui_file_id=file_id,
                        synced_at=datetime.now(UTC),
                    )
                    result.files_downloaded += 1

                except Exception as e:
                    log.error("download_file_failed", file_id=file_id, error=str(e))
                    result.errors.append(f"download {filename}: {e}")

            state.last_sync = datetime.now(UTC)
            await self.save_state()

        except Exception as e:
            log.exception("sync_from_openwebui_failed", error=str(e))
            result.success = False
            result.errors.append(str(e))

        end_time = datetime.now(UTC)
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return result
