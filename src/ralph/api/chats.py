"""Chat message injection API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ralph.openwebui_client import OpenWebUIClient

router = APIRouter(prefix="/chats", tags=["chats"])


class SendMessageRequest(BaseModel):
    """Request to send a message to a chat."""

    user_id: str
    chat_id: str | None = None  # If omitted, creates new chat
    role: str = "assistant"
    content: str
    title: str = "New Chat"  # Only used when creating
    archived: bool = False  # Only used when creating


class SendMessageResponse(BaseModel):
    """Response from sending a message."""

    chat_id: str
    message_id: str
    created: bool  # True if new chat was created


@router.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest) -> SendMessageResponse:
    """Send a message to a chat. Creates the chat if chat_id is not provided."""
    client = OpenWebUIClient()

    try:
        if request.chat_id:
            result = await client.append_message(
                chat_id=request.chat_id,
                role=request.role,
                content=request.content,
            )
            return SendMessageResponse(**result, created=False)

        result = await client.create_chat(
            user_id=request.user_id,
            title=request.title,
            role=request.role,
            content=request.content,
            archived=request.archived,
        )
        return SendMessageResponse(**result, created=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenWebUI API error: {e}") from e
