"""Background agent management endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from letta_starter.honcho.client import HonchoClient

from letta_starter.background.runner import BackgroundAgentRunner
from letta_starter.background.schema import CourseConfig, load_all_course_configs

log = structlog.get_logger()

router = APIRouter(prefix="/background", tags=["background"])

# Global state
_configs: dict[str, CourseConfig] = {}
_runner: BackgroundAgentRunner | None = None

# Limit for errors in response
MAX_ERRORS_IN_RESPONSE = 10


def initialize_background(
    letta_client: Any,
    honcho_client: HonchoClient | None,
    config_dir: Path,
) -> None:
    """Initialize background agent system."""
    global _configs, _runner

    _runner = BackgroundAgentRunner(letta_client, honcho_client)
    _configs = load_all_course_configs(config_dir)

    log.info(
        "background_system_initialized",
        courses_loaded=len(_configs),
        course_ids=list(_configs.keys()),
    )


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
    if _runner is None:
        raise HTTPException(status_code=500, detail="Background system not initialized")

    # Find agent config across all courses
    agent_config = None
    for course in _configs.values():
        for agent in course.background_agents:
            if agent.id == agent_id:
                agent_config = agent
                break
        if agent_config:
            break

    if agent_config is None:
        raise HTTPException(status_code=404, detail=f"Background agent '{agent_id}' not found")

    user_ids = request.user_ids if request else None
    result = await _runner.run_agent(agent_config, user_ids)

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
    return [
        AgentInfo(
            id=agent.id,
            name=agent.name,
            course_id=course.id,
            enabled=agent.enabled,
            triggers={
                "schedule": agent.triggers.schedule,
                "idle_enabled": agent.triggers.idle.enabled,
                "manual": agent.triggers.manual,
            },
            query_count=len(agent.queries),
        )
        for course in _configs.values()
        for agent in course.background_agents
    ]


@router.post("/config/reload", response_model=ReloadResponse)
async def reload_config(config_dir: str | None = None) -> ReloadResponse:
    """
    Reload TOML configuration files.

    Args:
        config_dir: Optional path override

    Returns:
        Reload status

    """
    global _configs

    try:
        path = Path(config_dir) if config_dir else Path("config/courses")
        _configs = load_all_course_configs(path)

        log.info(
            "config_reloaded",
            courses_loaded=len(_configs),
            course_ids=list(_configs.keys()),
        )

        return ReloadResponse(
            success=True,
            courses_loaded=len(_configs),
            course_ids=list(_configs.keys()),
            message="Configuration reloaded successfully",
        )
    except Exception as e:
        log.error("config_reload_failed", error=str(e))
        return ReloadResponse(
            success=False,
            courses_loaded=len(_configs),
            course_ids=list(_configs.keys()),
            message=f"Reload failed: {e}",
        )
