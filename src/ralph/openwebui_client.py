"""OpenWebUI API client for chat operations."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
import structlog

from ralph.config import get_settings

log = structlog.get_logger()


class OpenWebUIClient:
    """Async client for OpenWebUI chat API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.openwebui_url
        self._api_key = settings.openwebui_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def create_chat(
        self,
        user_id: str,
        title: str,
        role: str,
        content: str,
        model: str = "ralph-wiggum",
        archived: bool = False,
    ) -> dict[str, str]:
        """Create a new chat with an initial message. Returns {chat_id, message_id}."""
        msg_id = str(uuid.uuid4())
        now = int(time.time())

        chat_data: dict[str, Any] = {
            "title": title,
            "models": [model],
            "tags": [],
            "history": {
                "messages": {
                    msg_id: {
                        "id": msg_id,
                        "parentId": None,
                        "childrenIds": [],
                        "role": role,
                        "content": content,
                        "timestamp": now,
                    }
                },
                "currentId": msg_id,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/chats/new",
                headers=self._headers(),
                json={
                    "chat": chat_data,
                    "user_id": user_id,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            chat_id = result["id"]

        # Archive if requested (separate call since ChatForm doesn't have archived)
        if archived:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{self._base_url}/api/v1/chats/{chat_id}/archive",
                    headers=self._headers(),
                )

        log.info("openwebui_chat_created", chat_id=chat_id, user_id=user_id)
        return {"chat_id": chat_id, "message_id": msg_id}

    async def append_message(
        self,
        chat_id: str,
        role: str,
        content: str,
    ) -> dict[str, str]:
        """Append a message to an existing chat. Returns {chat_id, message_id}."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # GET current chat
            resp = await client.get(
                f"{self._base_url}/api/v1/chats/{chat_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            chat_obj = resp.json()

        chat_data = chat_obj["chat"]
        history = chat_data.get("history", {"messages": {}, "currentId": None})
        current_id = history.get("currentId")

        # Build new message
        msg_id = str(uuid.uuid4())
        now = int(time.time())
        new_msg: dict[str, Any] = {
            "id": msg_id,
            "parentId": current_id,
            "childrenIds": [],
            "role": role,
            "content": content,
            "timestamp": now,
        }

        # Link parent -> child
        if current_id and current_id in history["messages"]:
            history["messages"][current_id]["childrenIds"].append(msg_id)

        # Add message and update pointer
        history["messages"][msg_id] = new_msg
        history["currentId"] = msg_id
        chat_data["history"] = history

        # POST updated chat
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/v1/chats/{chat_id}",
                headers=self._headers(),
                json={"chat": chat_data},
            )
            resp.raise_for_status()

        log.info("openwebui_message_appended", chat_id=chat_id, message_id=msg_id)
        return {"chat_id": chat_id, "message_id": msg_id}
