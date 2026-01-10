"""One-way sync service: OpenWebUI → Letta."""

import asyncio
import contextlib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from letta_client import Letta

from letta_starter.server.sync.mappings import (
    FileMapping,
    NoteMapping,
    SyncMappingStore,
)
from letta_starter.server.sync.openwebui_client import (
    OpenWebUIClient,
    OpenWebUIKnowledge,
    OpenWebUINote,
)

if TYPE_CHECKING:
    from letta_starter.config.settings import ServiceSettings

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    """Statistics from a sync cycle."""

    notes_synced: int = 0
    notes_skipped: int = 0
    notes_failed: int = 0
    files_synced: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    duration_ms: int = 0


@dataclass
class FileSyncService:
    """
    One-way sync: OpenWebUI → Letta.

    Notes and Knowledge files from OpenWebUI are uploaded to Letta folders.
    Letta handles PDF→MD conversion via built-in Mistral OCR.
    """

    settings: "ServiceSettings"
    letta: Letta
    openwebui: OpenWebUIClient = field(init=False)
    mappings: SyncMappingStore = field(init=False)
    _running: bool = field(default=False, init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _last_sync: datetime | None = field(default=None, init=False)
    _last_stats: SyncStats | None = field(default=None, init=False)
    _folder_cache: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Initialize clients after dataclass creation."""
        self.openwebui = OpenWebUIClient(
            base_url=self.settings.openwebui_url,
            api_key=self.settings.openwebui_api_key,
        )
        self.mappings = SyncMappingStore(
            storage_path=Path(self.settings.data_dir) / "sync_mappings.json"
        )

    async def start(self) -> None:
        """Start background sync loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info("File sync service started")

    async def stop(self) -> None:
        """Stop background sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.openwebui.close()
        logger.info("File sync service stopped")

    async def _sync_loop(self) -> None:
        """Background sync loop."""
        while self._running:
            try:
                self._last_stats = await self.sync_all()
                self._last_sync = datetime.now()
            except Exception:
                logger.exception("Sync cycle failed")
            await asyncio.sleep(self.settings.file_sync_interval)

    async def sync_all(self) -> SyncStats:
        """Perform full sync cycle: OpenWebUI → Letta."""
        start = datetime.now()
        stats = SyncStats()

        await self._sync_notes(stats)
        await self._sync_knowledge(stats)

        stats.duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        logger.info(
            "Sync complete",
            extra={
                "notes_synced": stats.notes_synced,
                "notes_skipped": stats.notes_skipped,
                "files_synced": stats.files_synced,
                "files_skipped": stats.files_skipped,
                "duration_ms": stats.duration_ms,
            },
        )
        return stats

    async def _sync_notes(self, stats: SyncStats) -> None:
        """Sync OpenWebUI Notes → Letta folders."""
        try:
            notes = await self.openwebui.list_notes()
        except Exception:
            logger.exception("Failed to list notes")
            return

        for note in notes:
            try:
                await self._sync_single_note(note, stats)
            except Exception:
                logger.exception("Failed to sync note %s", note.id)
                stats.notes_failed += 1

    async def _sync_single_note(self, note: OpenWebUINote, stats: SyncStats) -> None:
        """Sync a single note."""
        mapping = self.mappings.get_note_mapping(note.id)
        content_hash = SyncMappingStore.compute_hash(note.content)

        # Skip if unchanged
        if mapping and mapping.content_hash == content_hash:
            stats.notes_skipped += 1
            return

        # Determine folder based on access_control
        folder_name = self._get_folder_name_for_note(note)
        folder_id = await self.ensure_folder(folder_name)

        # Delete old file if updating
        if mapping and mapping.letta_file_id:
            with contextlib.suppress(Exception):
                self.letta.folders.files.delete(
                    folder_id=mapping.letta_folder_id,
                    file_id=mapping.letta_file_id,
                )

        # Upload to Letta
        file_id = await self._upload_file(
            folder_id=folder_id,
            filename=f"{note.title}.md",
            content=note.content.encode(),
        )

        # Update mapping
        self.mappings.set_note_mapping(
            NoteMapping(
                openwebui_note_id=note.id,
                letta_folder_id=folder_id,
                letta_file_id=file_id,
                title=note.title,
                content_hash=content_hash,
                last_synced=datetime.now().isoformat(),
                status="synced",
            )
        )
        stats.notes_synced += 1
        logger.info("Synced note: %s", note.title)

    async def _sync_knowledge(self, stats: SyncStats) -> None:
        """
        Sync OpenWebUI Knowledge → Letta folders.

        Letta handles PDF→MD conversion via Mistral OCR automatically.
        """
        try:
            collections = await self.openwebui.list_knowledge()
        except Exception:
            logger.exception("Failed to list knowledge")
            return

        for collection in collections:
            await self._sync_collection(collection, stats)

    async def _sync_collection(self, collection: OpenWebUIKnowledge, stats: SyncStats) -> None:
        """Sync a knowledge collection."""
        # Determine folder name based on access_control
        folder_name = self._get_folder_name_for_knowledge(collection)
        folder_id = await self.ensure_folder(folder_name)

        for file in collection.files:
            try:
                await self._sync_single_file(file, collection, folder_id, stats)
            except Exception:
                logger.exception("Failed to sync file %s", file.id)
                stats.files_failed += 1

    async def _sync_single_file(
        self,
        file: Any,  # OpenWebUIFile
        collection: OpenWebUIKnowledge,
        folder_id: str,
        stats: SyncStats,
    ) -> None:
        """Sync a single file from a knowledge collection."""
        mapping = self.mappings.get_file_mapping(file.id)

        # Get file content from OpenWebUI
        content = await self.openwebui.get_file_content(file.id)
        content_hash = SyncMappingStore.compute_hash(content)

        # Skip if unchanged
        if mapping and mapping.content_hash == content_hash:
            stats.files_skipped += 1
            return

        # Delete old file if updating
        if mapping and mapping.letta_file_id:
            with contextlib.suppress(Exception):
                self.letta.folders.files.delete(
                    folder_id=mapping.letta_folder_id,
                    file_id=mapping.letta_file_id,
                )

        # Upload to Letta - Letta handles PDF→MD via Mistral OCR
        file_id = await self._upload_file(
            folder_id=folder_id,
            filename=file.filename,
            content=content,
        )

        # Update mapping
        self.mappings.set_file_mapping(
            FileMapping(
                openwebui_file_id=file.id,
                openwebui_knowledge_id=collection.id,
                letta_folder_id=folder_id,
                letta_file_id=file_id,
                filename=file.filename,
                content_hash=content_hash,
                last_synced=datetime.now().isoformat(),
                status="synced",
            )
        )
        stats.files_synced += 1
        logger.info("Synced file: %s", file.filename)

    def _get_folder_name_for_note(self, note: OpenWebUINote) -> str:
        """
        Determine folder name based on note access control.

        Args:
            note: The OpenWebUI note.

        Returns:
            Folder name for Letta.

        """
        if note.access_control is None:
            return "shared_notes"
        if note.access_control == {}:
            return f"user_{note.user_id}_notes"
        # Granular access → user folder (simplified)
        return f"user_{note.user_id}_notes"

    def _get_folder_name_for_knowledge(self, collection: OpenWebUIKnowledge) -> str:
        """
        Determine folder name based on knowledge access control.

        Args:
            collection: The OpenWebUI knowledge collection.

        Returns:
            Folder name for Letta.

        """
        if collection.access_control is None:
            return f"shared_knowledge_{collection.id[:8]}"
        if collection.access_control == {}:
            return f"user_{collection.user_id}_knowledge"
        return f"user_{collection.user_id}_knowledge"

    async def ensure_folder(self, name: str) -> str:
        """
        Get or create Letta folder by name.

        Args:
            name: Folder name.

        Returns:
            Folder ID.

        """
        if name in self._folder_cache:
            return self._folder_cache[name]

        # Search for existing folder
        folders = self.letta.folders.list(name=name)
        for folder in folders:
            if folder.name == name:
                self._folder_cache[name] = folder.id
                return folder.id

        # Create new folder
        folder = self.letta.folders.create(
            name=name,
            embedding=self.settings.file_sync_embedding_model,
        )
        self._folder_cache[name] = folder.id
        logger.info("Created folder: %s", name)
        return folder.id

    async def _upload_file(
        self,
        folder_id: str,
        filename: str,
        content: bytes,
    ) -> str:
        """
        Upload file to Letta folder and wait for processing.

        Args:
            folder_id: Letta folder ID.
            filename: File name.
            content: File content bytes.

        Returns:
            Letta file ID.

        """
        file_obj = io.BytesIO(content)
        file_obj.name = filename

        # Upload returns a job for async processing
        job = self.letta.folders.files.upload(
            folder_id=folder_id,
            file=file_obj,
        )

        # Wait for processing to complete
        while True:
            job = self.letta.jobs.retrieve(job.id)
            if job.status == "completed":
                break
            if job.status == "failed":
                raise RuntimeError(f"File upload failed: {job.error}")
            await asyncio.sleep(0.5)

        # Find the uploaded file to get its ID
        files = self.letta.folders.files.list(folder_id=folder_id)
        for f in files:
            if filename in (f.file_name, f.original_file_name):
                return f.id

        raise RuntimeError(f"File {filename} not found after upload")

    def get_status(self) -> dict[str, Any]:
        """
        Get sync service status.

        Returns:
            Status dict with running state, last sync time, and stats.

        """
        return {
            "enabled": self.settings.file_sync_enabled,
            "running": self._running,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "last_stats": (
                {
                    "notes_synced": self._last_stats.notes_synced,
                    "notes_skipped": self._last_stats.notes_skipped,
                    "notes_failed": self._last_stats.notes_failed,
                    "files_synced": self._last_stats.files_synced,
                    "files_skipped": self._last_stats.files_skipped,
                    "files_failed": self._last_stats.files_failed,
                    "duration_ms": self._last_stats.duration_ms,
                }
                if self._last_stats
                else None
            ),
        }
