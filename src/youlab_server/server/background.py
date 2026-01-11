"""Background agent management endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path

    from youlab_server.curriculum.schema import BackgroundAgentConfig
    from youlab_server.honcho.client import HonchoClient

from youlab_server.background.runner import BackgroundAgentRunner
from youlab_server.curriculum import curriculum

log = structlog.get_logger()

router = APIRouter(prefix="/background", tags=["background"])

# Global state
_runner: BackgroundAgentRunner | None = None
_initialized: bool = False

# Limit for errors in response
MAX_ERRORS_IN_RESPONSE = 10


def initialize_background(
    letta_client: Any,
    honcho_client: HonchoClient | None,
    config_dir: Path,
) -> None:
    """
    Initialize background agent system.

    Args:
        letta_client: Letta client instance
        honcho_client: Honcho client (optional)
        config_dir: Directory containing course configs (unused, curriculum is pre-initialized)

    """
    global _runner, _initialized

    _runner = BackgroundAgentRunner(letta_client, honcho_client)

    # Curriculum is already initialized by server startup
    # Background agents are accessed via curriculum.get(course_id).background

    _initialized = True
    log.info("background_system_initialized")


class RunRequest(BaseModel):
    """Request to run a background agent."""

    user_ids: list[str] | None = None  # None = all users


class RunResponse(BaseModel):
    """Response from background agent run."""

    agent_id: str
    started_at: str
    completed_at: str | None
    users_processed: int
    queries_executed: int
    enrichments_applied: int
    error_count: int
    errors: list[str]


class ReloadResponse(BaseModel):
    """Response from config reload."""

    success: bool
    courses_loaded: int
    course_ids: list[str]
    message: str


class AgentInfo(BaseModel):
    """Background agent information."""

    id: str
    name: str
    course_id: str
    enabled: bool
    triggers: dict[str, Any]
    query_count: int


@router.post("/{agent_id}/run", response_model=RunResponse)
async def run_background_agent(
    agent_id: str,
    request: RunRequest | None = None,
) -> RunResponse:
    """
    Manually trigger a background agent run.

    Args:
        agent_id: ID of the background agent to run
        request: Optional user filtering

    Returns:
        Execution result summary

    """
    if not _initialized or _runner is None:
        raise HTTPException(status_code=503, detail="Background system not initialized")

    # Find the agent config across all courses
    agent_config: BackgroundAgentConfig | None = None
    for course_id in curriculum.list_courses():
        course = curriculum.get(course_id)
        if course and agent_id in course.background:
            agent_config = course.background[agent_id]
            break

    if agent_config is None:
        raise HTTPException(status_code=404, detail=f"Background agent not found: {agent_id}")

    user_ids = request.user_ids if request else None
    result = await _runner.run_agent(agent_config, user_ids, agent_id=agent_id)

    return RunResponse(
        agent_id=result.agent_id,
        started_at=result.started_at.isoformat(),
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        users_processed=result.users_processed,
        queries_executed=result.queries_executed,
        enrichments_applied=result.enrichments_applied,
        error_count=len(result.errors),
        errors=result.errors[:MAX_ERRORS_IN_RESPONSE],
    )


@router.get("/agents", response_model=list[AgentInfo])
async def list_background_agents() -> list[AgentInfo]:
    """List all configured background agents."""
    agents = []
    for course_id in curriculum.list_courses():
        course = curriculum.get(course_id)
        if course:
            for agent_id, config in course.background.items():
                agents.append(
                    AgentInfo(
                        id=agent_id,
                        name=agent_id,
                        course_id=course_id,
                        enabled=config.enabled,
                        triggers={
                            "schedule": config.triggers.schedule,
                            "idle_enabled": config.triggers.idle.enabled,
                            "manual": config.triggers.manual,
                        },
                        query_count=len(config.queries),
                    )
                )
    return agents


@router.post("/config/reload", response_model=ReloadResponse)
async def reload_config(config_dir: str | None = None) -> ReloadResponse:
    """
    Reload TOML configuration files.

    Args:
        config_dir: Optional path override (unused, curriculum uses its own base dir)

    Returns:
        Reload status

    """
    try:
        count = curriculum.reload()
        course_ids = curriculum.list_courses()

        log.info(
            "config_reloaded",
            courses_loaded=count,
            course_ids=course_ids,
        )

        return ReloadResponse(
            success=True,
            courses_loaded=count,
            course_ids=course_ids,
            message="Configuration reloaded successfully",
        )
    except Exception as e:
        log.error("config_reload_failed", error=str(e))
        return ReloadResponse(
            success=False,
            courses_loaded=len(curriculum.list_courses()),
            course_ids=curriculum.list_courses(),
            message=f"Reload failed: {e}",
        )
