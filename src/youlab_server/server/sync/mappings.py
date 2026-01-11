"""Mapping storage for sync state."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NoteMapping:
    """Mapping for a synced note."""

    openwebui_note_id: str
    letta_folder_id: str
    letta_file_id: str | None
    title: str
    content_hash: str
    last_synced: str  # ISO format for JSON serialization
    status: str  # synced, pending, error


@dataclass
class FileMapping:
    """Mapping for a synced file."""

    openwebui_file_id: str
    openwebui_knowledge_id: str
    letta_folder_id: str
    letta_file_id: str | None
    filename: str
    content_hash: str
    last_synced: str
    status: str


@dataclass
class FolderMapping:
    """Tracks Letta folder ↔ OpenWebUI Knowledge mapping."""

    letta_folder_id: str
    letta_folder_name: str
    openwebui_knowledge_id: str
    last_synced: str  # ISO format
    status: str  # synced, pending, error


class SyncMappingStore:
    """
    Persistent storage for sync mappings.

    Stores mappings between OpenWebUI notes/files and Letta folder files.
    Uses JSON file for persistence.
    """

    def __init__(self, storage_path: Path) -> None:
        """
        Initialize mapping store.

        Args:
            storage_path: Path to JSON file for persistence.

        """
        self.storage_path = storage_path
        self.note_mappings: dict[str, NoteMapping] = {}
        self.file_mappings: dict[str, FileMapping] = {}
        self.folder_mappings: dict[str, FolderMapping] = {}  # keyed by letta_folder_id
        self._load()

    def _load(self) -> None:
        """Load mappings from disk."""
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            for note_id, m in data.get("notes", {}).items():
                self.note_mappings[note_id] = NoteMapping(**m)
            for file_id, m in data.get("files", {}).items():
                self.file_mappings[file_id] = FileMapping(**m)
            for folder_id, m in data.get("folders", {}).items():
                self.folder_mappings[folder_id] = FolderMapping(**m)
            logger.debug(
                "Loaded sync mappings",
                extra={
                    "notes": len(self.note_mappings),
                    "files": len(self.file_mappings),
                    "folders": len(self.folder_mappings),
                },
            )
        except Exception as e:
            logger.warning("Failed to load sync mappings: %s", e)

    def _save(self) -> None:
        """Persist mappings to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "notes": {k: asdict(v) for k, v in self.note_mappings.items()},
            "files": {k: asdict(v) for k, v in self.file_mappings.items()},
            "folders": {k: asdict(v) for k, v in self.folder_mappings.items()},
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def get_note_mapping(self, openwebui_note_id: str) -> NoteMapping | None:
        """Get mapping for a note by OpenWebUI ID."""
        return self.note_mappings.get(openwebui_note_id)

    def set_note_mapping(self, mapping: NoteMapping) -> None:
        """Save or update a note mapping."""
        self.note_mappings[mapping.openwebui_note_id] = mapping
        self._save()

    def delete_note_mapping(self, openwebui_note_id: str) -> None:
        """Delete a note mapping."""
        if openwebui_note_id in self.note_mappings:
            del self.note_mappings[openwebui_note_id]
            self._save()

    def get_file_mapping(self, openwebui_file_id: str) -> FileMapping | None:
        """Get mapping for a file by OpenWebUI ID."""
        return self.file_mappings.get(openwebui_file_id)

    def set_file_mapping(self, mapping: FileMapping) -> None:
        """Save or update a file mapping."""
        self.file_mappings[mapping.openwebui_file_id] = mapping
        self._save()

    def delete_file_mapping(self, openwebui_file_id: str) -> None:
        """Delete a file mapping."""
        if openwebui_file_id in self.file_mappings:
            del self.file_mappings[openwebui_file_id]
            self._save()

    def get_folder_mapping(self, letta_folder_id: str) -> FolderMapping | None:
        """Get mapping for a folder by Letta folder ID."""
        return self.folder_mappings.get(letta_folder_id)

    def get_folder_mapping_by_name(self, folder_name: str) -> FolderMapping | None:
        """Get mapping for a folder by folder name."""
        for m in self.folder_mappings.values():
            if m.letta_folder_name == folder_name:
                return m
        return None

    def set_folder_mapping(self, mapping: FolderMapping) -> None:
        """Save or update a folder mapping."""
        self.folder_mappings[mapping.letta_folder_id] = mapping
        self._save()

    def delete_folder_mapping(self, letta_folder_id: str) -> None:
        """Delete a folder mapping."""
        if letta_folder_id in self.folder_mappings:
            del self.folder_mappings[letta_folder_id]
            self._save()

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        """
        Compute content hash for change detection.

        Args:
            content: String or bytes to hash.

        Returns:
            Truncated SHA256 hash (16 chars).

        """
        if isinstance(content, str):
            content = content.encode()
        return hashlib.sha256(content).hexdigest()[:16]
