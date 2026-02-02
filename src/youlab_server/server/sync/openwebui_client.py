"""OpenWebUI API client for file sync."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

# Threshold to distinguish nanosecond timestamps from second timestamps
# Nanosecond timestamps are > 1e18, regular timestamps are ~1e9
_NANOSECOND_THRESHOLD = 1e15


@dataclass
class OpenWebUINote:
    """A note from OpenWebUI."""

    id: str
    user_id: str
    title: str
    content: str  # markdown from data.content.md
    access_control: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


@dataclass
class OpenWebUIFile:
    """A file within a knowledge collection."""

    id: str
    user_id: str
    filename: str
    content_type: str
    size: int
    created_at: datetime
    updated_at: datetime


@dataclass
class OpenWebUIKnowledge:
    """A knowledge collection from OpenWebUI."""

    id: str
    user_id: str
    name: str
    description: str
    files: list[OpenWebUIFile]
    access_control: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


class OpenWebUIClient:
    """
    Client for OpenWebUI API.

    Provides access to Notes and Knowledge collections for syncing to Letta.
    """

    def __init__(self, base_url: str, api_key: str | None) -> None:
        """
        Initialize OpenWebUI client.

        Args:
            base_url: OpenWebUI server URL.
            api_key: API key for authentication.

        """
        self.base_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )

    async def list_notes(self, page: int = 1) -> list[OpenWebUINote]:
        """
        List all notes (paginated, 60/page).

        Args:
            page: Page number for pagination.

        Returns:
            List of notes from OpenWebUI.

        """
        resp = await self.client.get("/api/v1/notes/", params={"page": page})
        resp.raise_for_status()
        return [
            OpenWebUINote(
                id=item["id"],
                user_id=item.get("user", {}).get("id", ""),
                title=item["title"],
                content=item.get("data", {}).get("content", {}).get("md", ""),
                access_control=item.get("access_control"),
                created_at=_parse_datetime(item.get("created_at")),
                updated_at=_parse_datetime(item.get("updated_at")),
            )
            for item in resp.json()
        ]

    async def get_note(self, note_id: str) -> OpenWebUINote:
        """
        Get note with content.

        Args:
            note_id: The note ID.

        Returns:
            The note details.

        """
        resp = await self.client.get(f"/api/v1/notes/{note_id}")
        resp.raise_for_status()
        item = resp.json()
        return OpenWebUINote(
            id=item["id"],
            user_id=item.get("user", {}).get("id", ""),
            title=item["title"],
            content=item.get("data", {}).get("content", {}).get("md", ""),
            access_control=item.get("access_control"),
            created_at=_parse_datetime(item.get("created_at")),
            updated_at=_parse_datetime(item.get("updated_at")),
        )

    async def list_knowledge(self) -> list[OpenWebUIKnowledge]:
        """
        List all knowledge collections with their files.

        Returns:
            List of knowledge collections from OpenWebUI.

        """
        resp = await self.client.get("/api/v1/knowledge/")
        resp.raise_for_status()
        data = resp.json()

        # Handle paginated response format
        items = data.get("items", data) if isinstance(data, dict) else data

        collections = []
        for item in items:
            # Fetch files for this collection (list endpoint doesn't include them)
            files = await self._get_knowledge_files(item["id"], item["user_id"])

            collections.append(
                OpenWebUIKnowledge(
                    id=item["id"],
                    user_id=item["user_id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    files=files,
                    access_control=item.get("access_control"),
                    created_at=_parse_datetime(item.get("created_at")),
                    updated_at=_parse_datetime(item.get("updated_at")),
                )
            )
        return collections

    async def _get_knowledge_files(self, knowledge_id: str, user_id: str) -> list[OpenWebUIFile]:
        """
        Get files for a specific knowledge collection.

        Args:
            knowledge_id: The knowledge collection ID.
            user_id: The user ID.

        Returns:
            List of files in the collection.

        """
        resp = await self.client.get(f"/api/v1/knowledge/{knowledge_id}/files")
        resp.raise_for_status()
        data = resp.json()

        # Handle paginated response format
        items = data.get("items", data) if isinstance(data, dict) else data

        return [
            OpenWebUIFile(
                id=f["id"],
                user_id=user_id,
                filename=f["filename"],
                content_type=f.get("meta", {}).get("content_type", ""),
                size=f.get("meta", {}).get("size", 0),
                created_at=_parse_datetime(f.get("created_at")),
                updated_at=_parse_datetime(f.get("updated_at")),
            )
            for f in items
        ]

    async def get_file_content(self, file_id: str) -> bytes:
        """
        Download file content.

        Args:
            file_id: The file ID.

        Returns:
            Raw file bytes.

        """
        resp = await self.client.get(f"/api/v1/files/{file_id}/content")
        resp.raise_for_status()
        return resp.content

    async def create_knowledge(
        self,
        name: str,
        description: str = "",
        access_control: dict[str, object] | None = None,
    ) -> str:
        """
        Create a knowledge collection in OpenWebUI.

        Args:
            name: Collection name (will match Letta folder name).
            description: Optional description.
            access_control: Access control settings.

        Returns:
            Knowledge collection ID.

        """
        resp = await self.client.post(
            "/api/v1/knowledge/create",
            json={
                "name": name,
                "description": description,
                "data": {},
                "access_control": access_control or {},
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str = "text/markdown",
    ) -> str:
        """
        Upload a file to OpenWebUI.

        Args:
            filename: Name of the file.
            content: File content as bytes.
            content_type: MIME type of the file.

        Returns:
            File ID.

        """
        files = {"file": (filename, content, content_type)}
        resp = await self.client.post("/api/v1/files/", files=files)
        resp.raise_for_status()
        return resp.json()["id"]

    async def add_file_to_knowledge(self, knowledge_id: str, file_id: str) -> None:
        """
        Add an uploaded file to a knowledge collection.

        Args:
            knowledge_id: Knowledge collection ID.
            file_id: File ID to add.

        """
        resp = await self.client.post(
            f"/api/v1/knowledge/{knowledge_id}/file/add",
            json={"file_id": file_id},
        )
        resp.raise_for_status()

    async def delete_file(self, file_id: str) -> None:
        """
        Delete a file from OpenWebUI.

        Args:
            file_id: File ID to delete.

        """
        resp = await self.client.delete(f"/api/v1/files/{file_id}")
        resp.raise_for_status()

    async def delete_knowledge(self, knowledge_id: str) -> None:
        """
        Delete a knowledge collection.

        Args:
            knowledge_id: Knowledge collection ID to delete.

        """
        resp = await self.client.delete(f"/api/v1/knowledge/{knowledge_id}")
        resp.raise_for_status()

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    # Folder and Chat management methods for background agent threads

    async def list_folders(self) -> list[dict[str, Any]]:
        """List all folders for the current user."""
        resp = await self.client.get("/api/folders/")
        resp.raise_for_status()
        return resp.json()

    async def create_folder(self, name: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new folder."""
        resp = await self.client.post(
            "/api/folders/",
            json={"name": name, "meta": meta or {}},
        )
        resp.raise_for_status()
        return resp.json()

    async def ensure_folder(self, name: str, meta: dict[str, Any] | None = None) -> str:
        """Ensure a folder exists, creating it if needed. Returns folder ID."""
        folders = await self.list_folders()
        existing = next((f for f in folders if f["name"] == name), None)
        if existing:
            return existing["id"]
        new_folder = await self.create_folder(name, meta)
        return new_folder["id"]

    async def get_chats_by_folder(self, folder_id: str, page: int = 1) -> list[dict[str, Any]]:
        """Get chats in a folder, sorted by updated_at desc."""
        resp = await self.client.get(
            f"/api/chats/folder/{folder_id}/list",
            params={"page": page},
        )
        resp.raise_for_status()
        return resp.json()

    async def create_chat(
        self, chat_data: dict[str, Any], folder_id: str | None = None
    ) -> dict[str, Any]:
        """Create a new chat."""
        resp = await self.client.post(
            "/api/chats/new",
            json={"chat": chat_data, "folder_id": folder_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def update_chat(self, chat_id: str, chat_data: dict[str, Any]) -> dict[str, Any]:
        """Update a chat's data (title, etc)."""
        resp = await self.client.post(
            f"/api/chats/{chat_id}",
            json={"chat": chat_data},
        )
        resp.raise_for_status()
        return resp.json()

    async def update_chat_folder(self, chat_id: str, folder_id: str) -> dict[str, Any]:
        """Move a chat to a folder."""
        resp = await self.client.post(
            f"/api/chats/{chat_id}/folder",
            json={"folder_id": folder_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def archive_chat(self, chat_id: str) -> dict[str, Any]:
        """Archive a chat."""
        resp = await self.client.post(f"/api/chats/{chat_id}/archive")
        resp.raise_for_status()
        return resp.json()


def _parse_datetime(value: str | int | None) -> datetime:
    """Parse datetime from ISO string or Unix timestamp."""
    if value is None:
        return datetime.now()
    if isinstance(value, int):
        # Handle both seconds and nanoseconds timestamps
        # Nanosecond timestamps are > 1e18, regular timestamps are ~1e9
        if value > _NANOSECOND_THRESHOLD:
            value = value // 1_000_000_000  # Convert nanoseconds to seconds
        return datetime.fromtimestamp(value)
    # value is str at this point
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()
