"""FastAPI HTTP service for LettaStarter."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

from letta_starter.config.settings import ServiceSettings
from letta_starter.honcho import HonchoClient
from letta_starter.honcho.client import create_persist_task
from letta_starter.server.agents import AgentManager
from letta_starter.server.schemas import (
    AgentListResponse,
    AgentResponse,
    ChatRequest,
    ChatResponse,
    CreateAgentRequest,
    HealthResponse,
    StreamChatRequest,
)
from letta_starter.server.strategy import init_strategy_manager
from letta_starter.server.strategy import router as strategy_router
from letta_starter.server.tracing import trace_chat, trace_generation

log = structlog.get_logger()
settings = ServiceSettings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    # Startup
    log.info("starting_service", host=settings.host, port=settings.port)
    app.state.agent_manager = AgentManager(letta_base_url=settings.letta_base_url)
    init_strategy_manager(letta_base_url=settings.letta_base_url)

    # Initialize Honcho client (if enabled)
    if settings.honcho_enabled:
        app.state.honcho_client = HonchoClient(
            workspace_id=settings.honcho_workspace_id,
            api_key=settings.honcho_api_key,
            environment=settings.honcho_environment,
        )
        honcho_ok = app.state.honcho_client.check_connection()
        log.info("honcho_initialized", connected=honcho_ok)
    else:
        app.state.honcho_client = None
        log.info("honcho_disabled")

    # Rebuild cache from Letta
    try:
        count = await app.state.agent_manager.rebuild_cache()
        log.info("startup_complete", cached_agents=count)
    except Exception as e:
        log.warning("letta_not_available_at_startup", error=str(e))

    yield

    # Shutdown
    log.info("shutting_down_service")


app = FastAPI(
    title="LettaStarter Service",
    description="HTTP service for YouLab AI tutoring",
    version="0.1.0",
    lifespan=lifespan,
)

# Include strategy router
app.include_router(strategy_router, prefix="/strategy", tags=["strategy"])


def get_agent_manager() -> AgentManager:
    """Get the agent manager from app state."""
    return app.state.agent_manager


def get_honcho_client() -> HonchoClient | None:
    """Get the Honcho client from app state (may be None if disabled)."""
    return getattr(app.state, "honcho_client", None)


# Health endpoint
@app.get("/health")
async def health() -> HealthResponse:
    """Check service health."""
    manager = get_agent_manager()
    honcho = get_honcho_client()

    letta_ok = manager.check_letta_connection()
    honcho_ok = honcho.check_connection() if honcho else False

    # Service is "ok" if Letta works, "degraded" otherwise
    # Honcho status is informational (not required for core function)
    health_status = "ok" if letta_ok else "degraded"

    return HealthResponse(
        status=health_status,
        letta_connected=letta_ok,
        honcho_connected=honcho_ok,
    )


# Agent endpoints
@app.post("/agents", status_code=status.HTTP_201_CREATED)
async def create_agent(request: CreateAgentRequest) -> AgentResponse:
    """Create a new agent for a user."""
    manager = get_agent_manager()

    try:
        agent_id = manager.create_agent(
            user_id=request.user_id,
            agent_type=request.agent_type,
            user_name=request.user_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
    except Exception as e:
        log.exception("agent_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to create agent - Letta may be unavailable",
        ) from None

    info = manager.get_agent_info(agent_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent created but info retrieval failed",
        )
    return AgentResponse(**info)


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentResponse:
    """Get agent information by ID."""
    manager = get_agent_manager()
    info = manager.get_agent_info(agent_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )
    return AgentResponse(**info)


@app.get("/agents")
async def list_agents(user_id: str | None = None) -> AgentListResponse:
    """List agents, optionally filtered by user_id."""
    manager = get_agent_manager()

    if user_id:
        agents = manager.list_user_agents(user_id)
    else:
        # List all YouLab agents (admin use)
        agents = []
        for agent in manager.client.agents.list():
            if agent.name and agent.name.startswith("youlab_"):
                meta = agent.metadata or {}
                agents.append(
                    {
                        "agent_id": agent.id,
                        "user_id": meta.get("youlab_user_id", ""),
                        "agent_type": meta.get("youlab_agent_type", "tutor"),
                        "agent_name": agent.name,
                        "created_at": getattr(agent, "created_at", None),
                    }
                )

    return AgentListResponse(agents=[AgentResponse(**a) for a in agents])


# Chat endpoint
@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a message to an agent."""
    manager = get_agent_manager()
    honcho = get_honcho_client()

    # Verify agent exists
    info = manager.get_agent_info(request.agent_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {request.agent_id}",
        )

    user_id = info.get("user_id", "unknown")
    agent_type = info.get("agent_type", "tutor")

    # Persist user message to Honcho (fire-and-forget)
    if request.chat_id:
        create_persist_task(
            honcho_client=honcho,
            user_id=user_id,
            chat_id=request.chat_id,
            message=request.message,
            is_user=True,
            chat_title=request.chat_title,
            agent_type=agent_type,
        )

    with trace_chat(
        user_id=user_id,
        agent_id=request.agent_id,
        chat_id=request.chat_id,
        metadata={"chat_title": request.chat_title},
    ) as trace_ctx:
        try:
            log.info(
                "chat_request",
                trace_id=trace_ctx.get("trace_id"),
                agent_id=request.agent_id,
                chat_id=request.chat_id,
                chat_title=request.chat_title,
                message_length=len(request.message),
            )

            response_text = manager.send_message(request.agent_id, request.message)

            # Record generation in Langfuse
            trace_generation(
                trace_ctx,
                name="agent_response",
                input_text=request.message,
                output_text=response_text,
            )

            # Persist agent response to Honcho (fire-and-forget)
            if request.chat_id and response_text:
                create_persist_task(
                    honcho_client=honcho,
                    user_id=user_id,
                    chat_id=request.chat_id,
                    message=response_text,
                    is_user=False,
                    chat_title=request.chat_title,
                    agent_type=agent_type,
                )

            return ChatResponse(
                response=response_text if response_text else "No response from agent.",
                agent_id=request.agent_id,
            )
        except Exception as e:
            log.exception(
                "chat_failed",
                trace_id=trace_ctx.get("trace_id"),
                agent_id=request.agent_id,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to communicate with agent",
            ) from None


@app.post("/chat/stream")
async def chat_stream(request: StreamChatRequest) -> StreamingResponse:
    """Send a message to an agent with streaming response (SSE)."""
    import json

    manager = get_agent_manager()
    honcho = get_honcho_client()

    # Verify agent exists
    info = manager.get_agent_info(request.agent_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {request.agent_id}",
        )

    user_id = info.get("user_id", "unknown")
    agent_type = info.get("agent_type", "tutor")

    # Persist user message to Honcho (fire-and-forget)
    if request.chat_id:
        create_persist_task(
            honcho_client=honcho,
            user_id=user_id,
            chat_id=request.chat_id,
            message=request.message,
            is_user=True,
            chat_title=request.chat_title,
            agent_type=agent_type,
        )

    def stream_with_persistence() -> Iterator[str]:
        """Wrap streaming to capture full response for Honcho."""
        full_response: list[str] = []

        for chunk in manager.stream_message(
            agent_id=request.agent_id,
            message=request.message,
            enable_thinking=request.enable_thinking,
        ):
            # Capture message content for persistence
            if chunk and '"type": "message"' in chunk:
                try:
                    # Extract content from SSE data
                    sse_prefix = "data: "
                    prefix_pos = chunk.find(sse_prefix)
                    data_end = chunk.find("\n\n")
                    if prefix_pos >= 0 and data_end > prefix_pos:
                        data_start = prefix_pos + len(sse_prefix)
                        data = json.loads(chunk[data_start:data_end])
                        if data.get("type") == "message" and data.get("content"):
                            full_response.append(data["content"])
                except (json.JSONDecodeError, KeyError):
                    pass
            yield chunk

        # Persist complete response after stream ends
        if request.chat_id and full_response:
            create_persist_task(
                honcho_client=honcho,
                user_id=user_id,
                chat_id=request.chat_id,
                message="".join(full_response),
                is_user=False,
                chat_title=request.chat_title,
                agent_type=agent_type,
            )

    return StreamingResponse(
        stream_with_persistence(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
