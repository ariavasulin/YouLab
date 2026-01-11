"""OpenWebUI API client for file sync."""

from dataclasses import dataclass
from datetime import datetime

import httpx


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
                user_id=item["user_id"],
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
            user_id=item["user_id"],
            title=item["title"],
            content=item.get("data", {}).get("content", {}).get("md", ""),
            access_control=item.get("access_control"),
            created_at=_parse_datetime(item.get("created_at")),
            updated_at=_parse_datetime(item.get("updated_at")),
        )

    async def list_knowledge(self) -> list[OpenWebUIKnowledge]:
        """
        List all knowledge collections.

        Returns:
            List of knowledge collections from OpenWebUI.

        """
        resp = await self.client.get("/api/v1/knowledge/")
        resp.raise_for_status()
        collections = []
        for item in resp.json():
            files = [
                OpenWebUIFile(
                    id=f["id"],
                    user_id=item["user_id"],
                    filename=f["filename"],
                    content_type=f.get("meta", {}).get("content_type", ""),
                    size=f.get("meta", {}).get("size", 0),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                for f in item.get("files", [])
            ]
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

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


def _parse_datetime(value: str | None) -> datetime:
    """Parse ISO datetime string or return current time."""
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now()
