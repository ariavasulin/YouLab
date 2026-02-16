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

DEFAULT_TIMEOUT = 60.0

HTTP_NO_CONTENT = 204


class OpenWebUIError(Exception):
    """Error from OpenWebUI API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


_TEXT_EXTENSIONS = {
    ".tex",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".py",
    ".rb",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
    ".r",
    ".m",
    ".jl",
    ".lua",
    ".pl",
    ".swift",
    ".kt",
    ".scala",
    ".ex",
    ".exs",
    ".hs",
    ".ml",
    ".rst",
    ".org",
    ".adoc",
    ".bib",
}


def _guess_content_type(filename: str) -> str:
    """Guess MIME type, defaulting text-like extensions to text/plain."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _TEXT_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


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

    async def upload_file(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> dict[str, Any]:
        """Upload a file to OpenWebUI. Returns file metadata including 'id'."""
        client = await self._get_client()

        if content_type is None:
            content_type = _guess_content_type(filename)

        files = {"file": (filename, io.BytesIO(content), content_type)}

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

    async def get_file_content(self, file_id: str) -> bytes:
        """Download file content by ID."""
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
        """Delete a file by ID."""
        await self._request("DELETE", f"/api/v1/files/{file_id}")

    async def list_knowledge(self) -> list[dict[str, Any]]:
        """List all knowledge bases."""
        result = await self._request("GET", "/api/v1/knowledge/")
        # OpenWebUI wraps the list in {"items": [...]}
        if isinstance(result, dict) and "items" in result:
            return result["items"]  # type: ignore[no-any-return]
        return result  # type: ignore[no-any-return]

    async def create_knowledge(self, name: str, description: str = "") -> dict[str, Any]:
        """Create a new knowledge base."""
        return await self._request(  # type: ignore[no-any-return]
            "POST",
            "/api/v1/knowledge/create",
            json={"name": name, "description": description},
        )

    async def get_or_create_knowledge(self, name: str) -> dict[str, Any]:
        """Get existing knowledge base by name or create new."""
        kbs = await self.list_knowledge()
        for kb in kbs:
            if kb.get("name") == name:
                return kb

        log.info("creating_knowledge_base", name=name)
        return await self.create_knowledge(name)

    async def get_knowledge_files(self, knowledge_id: str) -> list[dict[str, Any]]:
        """Get files in a knowledge base."""
        kb = await self._request("GET", f"/api/v1/knowledge/{knowledge_id}")
        # Files are nested under 'files' key (can be None)
        return kb.get("files") or []  # type: ignore[no-any-return]

    async def add_file_to_knowledge(self, knowledge_id: str, file_id: str) -> None:
        """Add a file to a knowledge base."""
        await self._request(
            "POST",
            f"/api/v1/knowledge/{knowledge_id}/file/add",
            json={"file_id": file_id},
        )

    async def remove_file_from_knowledge(self, knowledge_id: str, file_id: str) -> None:
        """Remove a file from a knowledge base."""
        await self._request(
            "POST",
            f"/api/v1/knowledge/{knowledge_id}/file/remove",
            json={"file_id": file_id},
        )
