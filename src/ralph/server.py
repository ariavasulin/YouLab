"""
Ralph HTTP Backend Service.

Streams Agno agent events to OpenWebUI in real-time.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
import uvicorn
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.shell import ShellTools
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from agno.tools.toolkit import Toolkit

from pathlib import Path

from ralph.api.background import router as background_router
from ralph.api.blocks import router as blocks_router
from ralph.api.chats import router as chats_router
from ralph.api.notes_adapter import router as notes_router
from ralph.api.workspace import router as workspace_router
from ralph.background import BackgroundExecutor, get_registry
from ralph.background.scheduler import get_scheduler, stop_scheduler
from ralph.config import get_settings
from ralph.dolt import close_dolt_client, get_dolt_client
from ralph.honcho import persist_message_fire_and_forget
from ralph.memory import build_memory_context, ensure_welcome_blocks
from ralph.tools import HonchoTools, MemoryBlockTools
from ralph.tools.hooked_file_tools import HookedFileTools

log = structlog.get_logger()


def get_workspace_path(user_id: str) -> Path:
    """Get workspace directory - shared or per-user."""
    settings = get_settings()
    if settings.agent_workspace:
        # Shared workspace (e.g., a codebase)
        workspace = Path(settings.agent_workspace)
    else:
        # Per-user isolated workspace
        workspace = Path(settings.user_data_dir) / user_id / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def read_claude_md(workspace: Path) -> str | None:
    """Read CLAUDE.md from workspace if it exists."""
    claude_md = workspace / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text()
    return None


def strip_agno_fields(toolkit: Toolkit) -> Toolkit:
    """Strip Agno-specific fields that Mistral doesn't accept."""
    for func in toolkit.functions.values():
        # These fields cause Mistral to reject the request
        func.requires_confirmation = None  # type: ignore[assignment]
        func.external_execution = None  # type: ignore[assignment]
    return toolkit


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for /chat/stream endpoint."""

    user_id: str
    chat_id: str
    messages: list[ChatMessage]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    settings = get_settings()
    log.info("ralph_server_starting", model=settings.openrouter_model)

    # Initialize Dolt connection pool
    dolt = None
    try:
        dolt = await get_dolt_client()
        log.info("dolt_client_connected")
    except Exception as e:
        log.warning("dolt_client_connection_failed", error=str(e))
        # Continue without Dolt - blocks API will fail but chat will work

    # Initialize background task system
    if dolt:
        try:
            registry = get_registry()
            await registry.initialize(dolt)

            executor = BackgroundExecutor(dolt)
            scheduler = await get_scheduler(registry, executor, dolt)
            await scheduler.start()
            log.info("background_scheduler_started")
        except Exception as e:
            log.warning("background_scheduler_failed", error=str(e))

    yield

    # Shutdown
    await stop_scheduler()
    log.info("background_scheduler_stopped")

    await close_dolt_client()
    log.info("dolt_client_disconnected")
    log.info("ralph_server_stopped")


app = FastAPI(
    title="Ralph Backend",
    description="HTTP backend for Ralph OpenWebUI pipe",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - allow OpenWebUI frontend to call Ralph API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:3000",
        "https://theyoulab.org",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the blocks API router
app.include_router(blocks_router)

# Include the background tasks API router
app.include_router(background_router)

# Include the notes adapter at /api prefix for OpenWebUI compatibility
# OpenWebUI calls /api/you/notes/* endpoints
app.include_router(notes_router, prefix="/api")

# Include the workspace sync API router
app.include_router(workspace_router)

# Include the chat injection API router
app.include_router(chats_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "ralph"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """Stream chat events via SSE."""

    async def generate() -> AsyncGenerator[dict[str, Any], None]:
        """Generate SSE events from Agno agent."""
        settings = get_settings()

        # Get user's workspace directory
        workspace = get_workspace_path(request.user_id)
        log.info("using_workspace", user_id=request.user_id, workspace=str(workspace))

        # Read CLAUDE.md for project-specific instructions
        claude_md = read_claude_md(workspace)
        if claude_md:
            log.info("claude_md_loaded", workspace=str(workspace), length=len(claude_md))
        else:
            log.info("claude_md_not_found", workspace=str(workspace))

        # Extract system message from OpenWebUI (per-chat system prompt)
        system_message = ""
        chat_messages = list(request.messages)
        if chat_messages and chat_messages[0].role == "system":
            system_message = chat_messages.pop(0).content
            log.info("system_message_extracted", length=len(system_message))

        # Build base instructions — use per-chat system prompt if provided,
        # otherwise fall back to the default generic prompt
        if system_message:
            base_instructions = system_message
        else:
            base_instructions = (
                "You are a helpful AI tutor assistant. "
                "Always be helpful, encouraging, and focused on the student's learning goals."
            )

        # Append tool usage instructions regardless of system prompt source
        tool_instructions = f"""
## Tool Usage

Your workspace is: {workspace}
You can read and write files, and execute shell commands within this workspace.

### Memory Blocks

You have access to memory blocks that contain persistent information about the student.
These blocks are shown below in "Student Context" when available.

To update memory blocks, use the memory block tools:
1. First, use `read_memory_block` to see the exact current content
2. Then, use `propose_memory_edit` with exact string matching to suggest changes
3. Your edits will be submitted as proposals that require user approval

Important: The `old_string` in your edit must match the block content exactly,
including whitespace and newlines. If the string appears multiple times,
provide more surrounding context to make it unique, or use `replace_all=True`.

### Creating Notes

You can create professional PDF notes by writing LaTeX files in the workspace.

How to use:
1. Create or edit a .tex file using save_file (e.g., "lecture-notes.tex")
2. The PDF will automatically compile and appear in the student's artifact panel
3. Each time you save the .tex file, the PDF updates automatically

Write complete LaTeX documents with \\documentclass, \\begin{{document}}, etc.
Use sections, math environments, theorems, and all standard LaTeX features.
The student never sees LaTeX — they only see the beautiful PDF result."""

        # Initialize welcome blocks for new users + build memory context
        memory_context = ""
        is_new_user = False
        try:
            dolt = await get_dolt_client()
            is_new_user = await ensure_welcome_blocks(dolt, request.user_id)
            memory_context = await build_memory_context(dolt, request.user_id)
            if memory_context:
                log.info(
                    "memory_context_loaded",
                    user_id=request.user_id,
                    block_count=len(memory_context.split("###")) - 1,
                    is_new_user=is_new_user,
                )
        except Exception as e:
            log.warning("memory_context_load_failed", user_id=request.user_id, error=str(e))

        # Compose final instructions
        instructions_parts = [base_instructions, tool_instructions]

        if claude_md:
            instructions_parts.append(f"""---

# Project Instructions (from CLAUDE.md)

{claude_md}""")

        if memory_context:
            instructions_parts.append(f"""---

# Student Context

The following information has been recorded about this student. Use this to personalize your tutoring approach.

{memory_context}""")

        instructions = "\n\n".join(instructions_parts)

        # Build the agent with tools (strip Agno fields Mistral doesn't accept)
        agent = Agent(
            model=OpenRouter(
                id=settings.openrouter_model,
                api_key=settings.openrouter_api_key,
            ),
            tools=[
                strip_agno_fields(ShellTools(base_dir=workspace)),
                strip_agno_fields(
                    HookedFileTools(
                        base_dir=workspace,
                        user_id=request.user_id,
                        chat_id=request.chat_id,
                    )
                ),
                strip_agno_fields(HonchoTools()),  # Honcho query tool
                strip_agno_fields(MemoryBlockTools()),  # Memory block tools
            ],
            instructions=instructions,
            markdown=True,
        )

        # Format messages for Agno (using chat_messages with system message stripped)
        if len(chat_messages) <= 1:
            prompt = chat_messages[-1].content if chat_messages else ""
        else:
            # Build context from previous messages
            history_parts = []
            for msg in chat_messages[:-1]:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role_label}: {msg.content}")

            history = "\n\n".join(history_parts)
            current_message = chat_messages[-1].content

            prompt = f"""Here is our conversation so far:

{history}

---

Now, the user says:
{current_message}"""

        # Persist user message to Honcho (fire-and-forget)
        last_user_message = chat_messages[-1].content if chat_messages else ""
        persist_message_fire_and_forget(
            user_id=request.user_id,
            chat_id=request.chat_id,
            message=last_user_message,
            is_user=True,
        )

        try:
            yield {
                "event": "message",
                "data": json.dumps({"type": "status", "content": "Thinking..."}),
            }

            # Accumulate response for persistence
            response_chunks: list[str] = []

            # Stream the response (pass user context for HonchoTools)
            async for chunk in agent.arun(
                prompt,
                stream=True,
                user_id=request.user_id,
                session_id=request.chat_id,
                dependencies={
                    "user_id": request.user_id,
                    "chat_id": request.chat_id,
                },
            ):
                # Emit tool call and reasoning events as status updates
                event_type = getattr(chunk, "event", None)
                log.info("stream_chunk", event_type=event_type, has_content=bool(chunk.content))

                # Skip terminal/summary events — they contain duplicate full content
                if event_type in (
                    "RunCompleted",
                    "RunStarted",
                    "RunContentCompleted",
                ):
                    continue

                if event_type == "ToolCallStarted":
                    tool = getattr(chunk, "tool", None)
                    if tool:
                        tool_name = getattr(tool, "tool_name", None) or "tool"
                        yield {
                            "event": "message",
                            "data": json.dumps(
                                {"type": "tool_call", "name": tool_name, "status": "started"}
                            ),
                        }
                elif event_type == "ToolCallCompleted":
                    tool = getattr(chunk, "tool", None)
                    if tool:
                        tool_name = getattr(tool, "tool_name", None) or "tool"
                        yield {
                            "event": "message",
                            "data": json.dumps(
                                {"type": "tool_call", "name": tool_name, "status": "completed"}
                            ),
                        }
                elif event_type == "ReasoningContentDelta":
                    reasoning = getattr(chunk, "reasoning_content", None)
                    if reasoning:
                        yield {
                            "event": "message",
                            "data": json.dumps({"type": "reasoning", "content": reasoning}),
                        }

                content = chunk.content
                if content:
                    response_chunks.append(content)
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "message", "content": content}),
                    }

            yield {"event": "message", "data": json.dumps({"type": "done"})}

            # Persist assistant response to Honcho (fire-and-forget)
            full_response = "".join(response_chunks)
            if full_response:
                persist_message_fire_and_forget(
                    user_id=request.user_id,
                    chat_id=request.chat_id,
                    message=full_response,
                    is_user=False,
                )

            # Track user activity for idle triggers
            try:
                dolt_client = await get_dolt_client()
                await dolt_client.update_user_activity(request.user_id, datetime.now(UTC))
            except Exception as activity_err:
                log.warning(
                    "activity_tracking_failed", user_id=request.user_id, error=str(activity_err)
                )

        except Exception as e:
            log.exception("chat_stream_error", error=str(e))
            yield {"event": "message", "data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(generate())


def main() -> None:
    """Run the server."""
    log.info("starting_ralph_server", port=8200)
    uvicorn.run(app, host="0.0.0.0", port=8200)  # noqa: S104


if __name__ == "__main__":
    main()
