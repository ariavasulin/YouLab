"""HTTP API for background task management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ralph.background import (
    BackgroundExecutor,
    BackgroundTask,
    CronTrigger,
    IdleTrigger,
    TriggerType,
    get_registry,
)
from ralph.dolt import get_dolt_client

log = structlog.get_logger()

router = APIRouter(prefix="/background", tags=["background"])


# Request/Response Models


class CronTriggerRequest(BaseModel):
    """Cron trigger configuration."""

    type: str = "cron"
    schedule: str  # Cron expression


class IdleTriggerRequest(BaseModel):
    """Idle trigger configuration."""

    type: str = "idle"
    idle_minutes: int
    cooldown_minutes: int = 60


class CreateTaskRequest(BaseModel):
    """Request to create a background task."""

    name: str
    system_prompt: str
    tools: list[str]
    memory_blocks: list[str]
    trigger: CronTriggerRequest | IdleTriggerRequest
    user_ids: list[str]
    batch_size: int = 5
    max_turns: int = 10
    enabled: bool = True


class TaskResponse(BaseModel):
    """Background task response."""

    name: str
    system_prompt: str
    tools: list[str]
    memory_blocks: list[str]
    trigger_type: str
    trigger_config: dict[str, Any]
    user_ids: list[str]
    batch_size: int
    max_turns: int
    enabled: bool


class UserRunResultResponse(BaseModel):
    """Result for a single user in a task run."""

    user_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    turns_used: int
    error: str | None
    proposals_created: int


class TaskRunResponse(BaseModel):
    """Task run response."""

    id: str
    task_name: str
    trigger_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    user_results: list[UserRunResultResponse]
    error: str | None


class RunTaskResponse(BaseModel):
    """Response from manually triggering a task."""

    run_id: str
    message: str


# Helper functions


def task_to_response(task: BackgroundTask) -> TaskResponse:
    """Convert BackgroundTask to response model."""
    if isinstance(task.trigger, CronTrigger):
        trigger_type = "cron"
        trigger_config: dict[str, Any] = {"schedule": task.trigger.schedule}
    else:
        trigger_type = "idle"
        trigger_config = {
            "idle_minutes": task.trigger.idle_minutes,
            "cooldown_minutes": task.trigger.cooldown_minutes,
        }

    return TaskResponse(
        name=task.name,
        system_prompt=task.system_prompt,
        tools=task.tools,
        memory_blocks=task.memory_blocks,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        user_ids=task.user_ids,
        batch_size=task.batch_size,
        max_turns=task.max_turns,
        enabled=task.enabled,
    )


# Endpoints


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks() -> list[TaskResponse]:
    """List all registered background tasks."""
    registry = get_registry()
    return [task_to_response(t) for t in registry.list_all()]


@router.get("/tasks/{name}", response_model=TaskResponse)
async def get_task(name: str) -> TaskResponse:
    """Get a background task by name."""
    registry = get_registry()
    task = registry.get(name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    return task_to_response(task)


@router.post("/tasks", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    """Create or update a background task."""
    # Convert trigger
    trigger: CronTrigger | IdleTrigger
    if request.trigger.type == "cron":
        if not isinstance(request.trigger, CronTriggerRequest):
            raise HTTPException(status_code=400, detail="Invalid cron trigger format")
        trigger = CronTrigger(schedule=request.trigger.schedule)
    else:
        if not isinstance(request.trigger, IdleTriggerRequest):
            raise HTTPException(status_code=400, detail="Invalid idle trigger format")
        trigger = IdleTrigger(
            idle_minutes=request.trigger.idle_minutes,
            cooldown_minutes=request.trigger.cooldown_minutes,
        )

    task = BackgroundTask(
        name=request.name,
        system_prompt=request.system_prompt,
        tools=request.tools,
        memory_blocks=request.memory_blocks,
        trigger=trigger,
        user_ids=request.user_ids,
        batch_size=request.batch_size,
        max_turns=request.max_turns,
        enabled=request.enabled,
    )

    registry = get_registry()
    await registry.register(task)

    log.info("task_created_via_api", name=task.name)
    return task_to_response(task)


@router.delete("/tasks/{name}")
async def delete_task(name: str) -> dict[str, bool]:
    """Delete a background task."""
    registry = get_registry()
    deleted = await registry.unregister(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    return {"deleted": True}


@router.post("/tasks/{name}/enable", response_model=TaskResponse)
async def enable_task(name: str) -> TaskResponse:
    """Enable a background task."""
    registry = get_registry()
    if not await registry.set_enabled(name, enabled=True):
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    task = registry.get(name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    return task_to_response(task)


@router.post("/tasks/{name}/disable", response_model=TaskResponse)
async def disable_task(name: str) -> TaskResponse:
    """Disable a background task."""
    registry = get_registry()
    if not await registry.set_enabled(name, enabled=False):
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    task = registry.get(name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")
    return task_to_response(task)


@router.post("/tasks/{name}/run", response_model=RunTaskResponse)
async def run_task(name: str) -> RunTaskResponse:
    """Manually trigger a background task to run now."""
    registry = get_registry()
    task = registry.get(name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{name}' not found")

    dolt = await get_dolt_client()
    executor = BackgroundExecutor(dolt)

    # Run synchronously for manual triggers (caller waits for completion)
    run = await executor.execute_task(task, TriggerType.CRON)

    return RunTaskResponse(
        run_id=run.id,
        message=f"Task '{name}' completed with status: {run.status.value}",
    )


@router.get("/tasks/{name}/runs", response_model=list[TaskRunResponse])
async def list_task_runs(name: str, limit: int = 50) -> list[TaskRunResponse]:
    """List execution history for a task."""
    dolt = await get_dolt_client()
    runs = await dolt.list_task_runs(task_name=name, limit=limit)
    return [
        TaskRunResponse(
            id=r.id,
            task_name=r.task_name,
            trigger_type=r.trigger_type.value,
            status=r.status.value,
            started_at=r.started_at,
            completed_at=r.completed_at,
            user_results=[
                UserRunResultResponse(
                    user_id=ur.user_id,
                    status=ur.status.value,
                    started_at=ur.started_at,
                    completed_at=ur.completed_at,
                    turns_used=ur.turns_used,
                    error=ur.error,
                    proposals_created=ur.proposals_created,
                )
                for ur in r.user_results
            ],
            error=r.error,
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=TaskRunResponse)
async def get_task_run(run_id: str) -> TaskRunResponse:
    """Get details of a specific task run."""
    dolt = await get_dolt_client()
    run = await dolt.get_task_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return TaskRunResponse(
        id=run.id,
        task_name=run.task_name,
        trigger_type=run.trigger_type.value,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        user_results=[
            UserRunResultResponse(
                user_id=ur.user_id,
                status=ur.status.value,
                started_at=ur.started_at,
                completed_at=ur.completed_at,
                turns_used=ur.turns_used,
                error=ur.error,
                proposals_created=ur.proposals_created,
            )
            for ur in run.user_results
        ],
        error=run.error,
    )
