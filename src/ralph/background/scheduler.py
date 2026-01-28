"""Background task scheduler."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from croniter import croniter

from ralph.background.models import CronTrigger, IdleTrigger, TriggerType

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    from ralph.background.executor import BackgroundExecutor
    from ralph.background.registry import TaskRegistry
    from ralph.dolt import DoltClient

log = structlog.get_logger()


class BackgroundScheduler:
    """
    Async scheduler for background tasks.

    Monitors cron and idle triggers and dispatches executions.
    Designed to run within FastAPI lifespan context.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        executor: BackgroundExecutor,
        dolt: DoltClient,
        check_interval_seconds: int = 60,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._dolt = dolt
        self._check_interval = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_cron_check: dict[str, datetime] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            log.warning("scheduler_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("scheduler_started", check_interval=self._check_interval)

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        log.info("scheduler_stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_triggers()
            except Exception:
                log.exception("scheduler_check_failed")

            await asyncio.sleep(self._check_interval)

    def _create_tracked_task(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Create a task and track it for cleanup."""
        bg_task = asyncio.create_task(coro)  # type: ignore[arg-type]
        self._background_tasks.add(bg_task)
        bg_task.add_done_callback(self._background_tasks.discard)

    async def _check_triggers(self) -> None:
        """Check all triggers and dispatch tasks as needed."""
        now = datetime.now(UTC)

        # Check cron tasks
        for task in self._registry.list_cron_tasks():
            if await self._should_run_cron(task.name, task.trigger, now):  # type: ignore[arg-type]
                log.info("cron_trigger_fired", task_name=task.name)
                self._create_tracked_task(
                    self._executor.execute_task(task, TriggerType.CRON)  # type: ignore[arg-type]
                )
                self._last_cron_check[task.name] = now

        # Check idle tasks
        for task in self._registry.list_idle_tasks():
            trigger = task.trigger
            if not isinstance(trigger, IdleTrigger):
                continue

            # Find users who are idle and not in cooldown
            # Only consider users in the task's user_ids list
            idle_users = await self._dolt.get_users_idle_for(
                minutes=trigger.idle_minutes,
                task_name=task.name,
                cooldown_minutes=trigger.cooldown_minutes,
            )

            # Filter to only users in this task's list
            eligible_users = [u for u in idle_users if u in task.user_ids]

            if eligible_users:
                log.info(
                    "idle_trigger_fired",
                    task_name=task.name,
                    user_count=len(eligible_users),
                )
                self._create_tracked_task(
                    self._executor.execute_task(  # type: ignore[arg-type]
                        task, TriggerType.IDLE, user_ids=eligible_users
                    )
                )

    async def _should_run_cron(
        self,
        task_name: str,
        trigger: CronTrigger,
        now: datetime,
    ) -> bool:
        """Check if a cron task should run now."""
        last_check = self._last_cron_check.get(task_name)

        if last_check is None:
            # First check - initialize but don't run immediately
            self._last_cron_check[task_name] = now
            return False

        # Check if cron would have fired between last check and now
        cron = croniter(trigger.schedule, last_check)
        next_run = cron.get_next(datetime)

        return next_run <= now

    async def run_task_now(self, task_name: str) -> str | None:
        """
        Manually trigger a task to run immediately.

        Returns the run ID if task found, None otherwise.
        """
        task = self._registry.get(task_name)
        if not task:
            log.warning("manual_trigger_task_not_found", task_name=task_name)
            return None

        log.info("manual_trigger_fired", task_name=task_name)
        run = await self._executor.execute_task(task, TriggerType.CRON)  # Use CRON for manual
        return run.id


# Module-level singleton
_scheduler: BackgroundScheduler | None = None


async def get_scheduler(
    registry: TaskRegistry,
    executor: BackgroundExecutor,
    dolt: DoltClient,
) -> BackgroundScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(registry, executor, dolt)
    return _scheduler


async def stop_scheduler() -> None:
    """Stop and clear the scheduler singleton."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
