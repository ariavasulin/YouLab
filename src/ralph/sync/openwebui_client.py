"""
OpenWebUI API client for knowledge base management.

Based on patterns from openwebui-content-sync but implemented in Python.
"""

from __future__ import annotations

import io
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

# Default timeout for API calls
DEFAULT_TIMEOUT = 60.0

# HTTP 204 No Content status code
HTTP_NO_CONTENT = 204


class OpenWebUIError(Exception):
    """Error from OpenWebUI API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenWebUIClient:
    """
    HTTP client for OpenWebUI API.

    Supports file upload/download and knowledge base management.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize client.

        Args:
            base_url: OpenWebUI base URL (e.g., https://openwebui.example.com).
            api_key: API key for authentication.
            timeout: Request timeout in seconds.

        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make HTTP request and handle errors."""
        client = await self._get_client()

        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()

            # Some endpoints return empty response
            if response.status_code == HTTP_NO_CONTENT or not response.content:
                return None

            return response.json()

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(error_data))
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else ""

            log.error(
                "openwebui_api_error",
                method=method,
                path=path,
                status_code=e.response.status_code,
                detail=error_detail,
            )
            raise OpenWebUIError(
                f"API error: {error_detail or e.response.reason_phrase}",
                status_code=e.response.status_code,
            ) from e

        except httpx.TimeoutException as e:
            log.error("openwebui_timeout", method=method, path=path)
            raise OpenWebUIError("Request timed out") from e

    # File Operations

    async def upload_file(self, filename: str, content: bytes) -> dict[str, Any]:
        """
        Upload a file to OpenWebUI.

        Args:
            filename: Name for the uploaded file.
            content: File content as bytes.

        Returns:
            File metadata including 'id'.

        """
        client = await self._get_client()

        # OpenWebUI expects multipart form data
        files = {"file": (filename, io.BytesIO(content))}

        try:
            response = await client.post("/api/v1/files/", files=files)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text[:200] if e.response.text else ""
            raise OpenWebUIError(
                f"File upload failed: {error_detail}",
                status_code=e.response.status_code,
            ) from e

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """
        Get file metadata.

        Args:
            file_id: OpenWebUI file ID.

        Returns:
            File metadata.

        """
        return await self._request("GET", f"/api/v1/files/{file_id}")  # type: ignore[no-any-return]

    async def get_file_content(self, file_id: str) -> bytes:
        """
        Download file content.

        Args:
            file_id: OpenWebUI file ID.

        Returns:
            File content as bytes.

        """
        client = await self._get_client()

        try:
            response = await client.get(f"/api/v1/files/{file_id}/content")
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise OpenWebUIError(
                f"File download failed: {e.response.reason_phrase}",
                status_code=e.response.status_code,
            ) from e

    async def delete_file(self, file_id: str) -> None:
        """
        Delete a file.

        Args:
            file_id: OpenWebUI file ID.

        """
        await self._request("DELETE", f"/api/v1/files/{file_id}")

    # Knowledge Base Operations

    async def list_knowledge(self) -> list[dict[str, Any]]:
        """
        List all knowledge bases.

        Returns:
            List of knowledge base metadata.

        """
        return await self._request("GET", "/api/v1/knowledge/")  # type: ignore[no-any-return]

    async def create_knowledge(self, name: str, description: str = "") -> dict[str, Any]:
        """
        Create a new knowledge base.

        Args:
            name: Knowledge base name.
            description: Optional description.

        Returns:
            Knowledge base metadata including 'id'.

        """
        return await self._request(  # type: ignore[no-any-return]
            "POST",
            "/api/v1/knowledge/create",
            json={"name": name, "description": description},
        )

    async def get_or_create_knowledge(self, name: str) -> dict[str, Any]:
        """
        Get existing knowledge base by name or create new.

        Args:
            name: Knowledge base name.

        Returns:
            Knowledge base metadata.

        """
        # List existing
        kbs = await self.list_knowledge()
        for kb in kbs:
            if kb.get("name") == name:
                return kb

        # Create new
        log.info("creating_knowledge_base", name=name)
        return await self.create_knowledge(name)

    async def get_knowledge_files(self, knowledge_id: str) -> list[dict[str, Any]]:
        """
        Get files in a knowledge base.

        Args:
            knowledge_id: Knowledge base ID.

        Returns:
            List of file metadata.

        """
        kb = await self._request("GET", f"/api/v1/knowledge/{knowledge_id}")
        # Files are nested under 'files' key
        return kb.get("files", [])  # type: ignore[no-any-return]

    async def add_file_to_knowledge(self, knowledge_id: str, file_id: str) -> None:
        """
        Add a file to a knowledge base.

        Args:
            knowledge_id: Knowledge base ID.
            file_id: File ID to add.

        """
        await self._request(
            "POST",
            f"/api/v1/knowledge/{knowledge_id}/file/add",
            json={"file_id": file_id},
        )

    async def remove_file_from_knowledge(self, knowledge_id: str, file_id: str) -> None:
        """
        Remove a file from a knowledge base.

        Args:
            knowledge_id: Knowledge base ID.
            file_id: File ID to remove.

        """
        await self._request(
            "POST",
            f"/api/v1/knowledge/{knowledge_id}/file/remove",
            json={"file_id": file_id},
        )
