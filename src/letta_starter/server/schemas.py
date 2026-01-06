"""
Request and response schemas for the HTTP service.

This is a minimal stub for TDD. Tests should fail until implementation is complete.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# Agent schemas
class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""

    user_id: str = Field(..., description="OpenWebUI user ID")
    agent_type: str = Field(default="tutor", description="Agent template type")
    user_name: str | None = Field(default=None, description="User's display name")


class AgentResponse(BaseModel):
    """Agent information response."""

    agent_id: str
    user_id: str
    agent_type: str
    agent_name: str
    created_at: datetime | int | None = None


class AgentListResponse(BaseModel):
    """List of agents response."""

    agents: list[AgentResponse]


# Chat schemas
class ChatRequest(BaseModel):
    """Request to send a message."""

    agent_id: str = Field(..., description="Letta agent ID")
    message: str = Field(..., description="User message content")
    chat_id: str | None = Field(default=None, description="OpenWebUI chat ID")
    chat_title: str | None = Field(default=None, description="OpenWebUI chat title")


class StreamChatRequest(BaseModel):
    """Request to send a message with streaming response."""

    agent_id: str = Field(..., description="Letta agent ID")
    message: str = Field(..., description="User message content")
    chat_id: str | None = Field(default=None, description="OpenWebUI chat ID")
    chat_title: str | None = Field(default=None, description="OpenWebUI chat title")
    enable_thinking: bool = Field(default=True, description="Include reasoning in stream")


class ChatResponse(BaseModel):
    """Chat response."""

    response: str
    agent_id: str


# Health schemas
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    letta_connected: bool
    honcho_connected: bool = False
    version: str = "0.1.0"
