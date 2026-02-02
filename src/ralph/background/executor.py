"""Background agent executor."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from ralph.background.models import (
    BackgroundTask,
    RunStatus,
    TaskRun,
    TriggerType,
    UserRunResult,
)
from ralph.background.tools import create_tools_for_task
from ralph.config import get_settings
from ralph.memory import build_memory_context

if TYPE_CHECKING:
    from ralph.dolt import DoltClient

log = structlog.get_logger()


class BackgroundExecutor:
    """Executes background tasks for users."""

    def __init__(self, dolt: DoltClient) -> None:
        self._dolt = dolt
        self._settings = get_settings()

    async def execute_task(
        self,
        task: BackgroundTask,
        trigger_type: TriggerType,
        user_ids: list[str] | None = None,
    ) -> TaskRun:
        """
        Execute a background task for specified users.

        Args:
            task: The task definition
            trigger_type: What triggered this run
            user_ids: Override user list (defaults to task.user_ids)

        Returns:
            TaskRun with results for all users

        """
        run_id = str(uuid.uuid4())
        users_to_process = user_ids or task.user_ids

        run = TaskRun(
            id=run_id,
            task_name=task.name,
            trigger_type=trigger_type,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            user_results=[],
        )

        # Persist initial run record
        await self._dolt.create_task_run(run)

        log.info(
            "task_run_started",
            run_id=run_id,
            task_name=task.name,
            user_count=len(users_to_process),
            batch_size=task.batch_size,
        )

        try:
            # Process users in batches
            for i in range(0, len(users_to_process), task.batch_size):
                batch = users_to_process[i : i + task.batch_size]
                batch_results = await self._process_batch(task, batch)
                run.user_results.extend(batch_results)

                # Update run record after each batch
                await self._dolt.update_task_run(run)

            # Determine final status
            statuses = {r.status for r in run.user_results}
            if statuses == {RunStatus.SUCCESS}:
                run.status = RunStatus.SUCCESS
            elif statuses == {RunStatus.FAILED}:
                run.status = RunStatus.FAILED
            else:
                run.status = RunStatus.PARTIAL

        except Exception as e:
            log.exception("task_run_failed", run_id=run_id, error=str(e))
            run.status = RunStatus.FAILED
            run.error = str(e)

        run.completed_at = datetime.now(UTC)
        await self._dolt.update_task_run(run)

        log.info(
            "task_run_completed",
            run_id=run_id,
            task_name=task.name,
            status=run.status.value,
            duration_seconds=(run.completed_at - run.started_at).total_seconds(),
        )

        return run

    async def _process_batch(
        self,
        task: BackgroundTask,
        user_ids: list[str],
    ) -> list[UserRunResult]:
        """Process a batch of users concurrently."""
        tasks = [self._run_for_user(task, user_id) for user_id in user_ids]
        return await asyncio.gather(*tasks)

    async def _run_for_user(
        self,
        task: BackgroundTask,
        user_id: str,
    ) -> UserRunResult:
        """Run a background task for a single user."""
        started_at = datetime.now(UTC)
        log.info("user_run_started", task_name=task.name, user_id=user_id)

        try:
            # Build memory context for this user
            memory_context = ""
            if task.memory_blocks:
                memory_context = await build_memory_context(
                    self._dolt, user_id, labels=task.memory_blocks
                )

            # Build instructions
            instructions = task.system_prompt
            if memory_context:
                instructions += f"\n\n---\n\n# Student Context\n\n{memory_context}"

            # Create tools for this user
            tools = create_tools_for_task(task.tools, user_id)

            # Create agent
            agent = Agent(
                model=OpenRouter(
                    id=self._settings.openrouter_model,
                    api_key=self._settings.openrouter_api_key,
                ),
                tools=tools,
                instructions=instructions,
                markdown=True,
            )

            # Run agent (streaming, let it iterate)
            # The agent will make tool calls and reason through the task
            turns_used = 0
            async for _chunk in agent.arun(
                "Execute your background task now. Review the student context and take "
                "appropriate action.",
                stream=True,
            ):
                turns_used += 1
                if turns_used >= task.max_turns:
                    log.warning(
                        "user_run_max_turns",
                        task_name=task.name,
                        user_id=user_id,
                        max_turns=task.max_turns,
                    )
                    break

            # Record that this task ran for this user
            await self._dolt.record_task_run_for_user(user_id, task.name, datetime.now(UTC))

            log.info(
                "user_run_completed",
                task_name=task.name,
                user_id=user_id,
                turns_used=turns_used,
            )

            return UserRunResult(
                user_id=user_id,
                status=RunStatus.SUCCESS,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                turns_used=turns_used,
                proposals_created=0,  # TODO: Track this when edit_memory_block tool exists
            )

        except Exception as e:
            log.exception("user_run_failed", task_name=task.name, user_id=user_id, error=str(e))
            return UserRunResult(
                user_id=user_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )
