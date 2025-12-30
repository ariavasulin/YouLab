"""FastAPI HTTP service for LettaStarter."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, status

from letta_starter.config.settings import ServiceSettings
from letta_starter.server.agents import AgentManager
from letta_starter.server.schemas import (
    AgentListResponse,
    AgentResponse,
    ChatRequest,
    ChatResponse,
    CreateAgentRequest,
    HealthResponse,
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


# Health endpoint
@app.get("/health")
async def health() -> HealthResponse:
    """Check service health."""
    manager = get_agent_manager()
    letta_ok = manager.check_letta_connection()
    return HealthResponse(
        status="ok" if letta_ok else "degraded",
        letta_connected=letta_ok,
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
        for agent in manager.client.list_agents():
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

    # Verify agent exists
    info = manager.get_agent_info(request.agent_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {request.agent_id}",
        )

    user_id = info.get("user_id", "unknown")

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
