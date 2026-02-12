"""Background task registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ralph.background.models import BackgroundTask, CronTrigger, IdleTrigger

if TYPE_CHECKING:
    from ralph.dolt import DoltClient

log = structlog.get_logger()


class TaskRegistry:
    """In-memory registry of background tasks with Dolt persistence."""

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._dolt: DoltClient | None = None

    async def initialize(self, dolt: DoltClient) -> None:
        """Initialize registry and load tasks from database."""
        self._dolt = dolt
        await self._load_from_database()

    async def _load_from_database(self) -> None:
        """Load all tasks from Dolt."""
        if not self._dolt:
            return
        tasks = await self._dolt.list_tasks()
        for task in tasks:
            self._tasks[task.name] = task
            log.info("task_loaded", name=task.name, enabled=task.enabled)

    async def register(self, task: BackgroundTask, persist: bool = True) -> None:
        """
        Register a background task.

        Args:
            task: The task definition
            persist: If True, save to Dolt database

        """
        self._tasks[task.name] = task
        log.info(
            "task_registered",
            name=task.name,
            trigger_type="cron" if isinstance(task.trigger, CronTrigger) else "idle",
            user_count=len(task.user_ids),
            enabled=task.enabled,
        )

        if persist and self._dolt:
            await self._dolt.create_task(task)
            log.info("task_persisted", name=task.name)

    async def unregister(self, name: str, persist: bool = True) -> bool:
        """
        Unregister a background task.

        Returns True if task existed and was removed.
        """
        if name not in self._tasks:
            return False

        del self._tasks[name]
        log.info("task_unregistered", name=name)

        if persist and self._dolt:
            await self._dolt.delete_task(name)

        return True

    def get(self, name: str) -> BackgroundTask | None:
        """Get a task by name."""
        return self._tasks.get(name)

    def list_all(self) -> list[BackgroundTask]:
        """List all registered tasks."""
        return list(self._tasks.values())

    def list_enabled(self) -> list[BackgroundTask]:
        """List only enabled tasks."""
        return [t for t in self._tasks.values() if t.enabled]

    def list_cron_tasks(self) -> list[BackgroundTask]:
        """List enabled tasks with cron triggers."""
        return [t for t in self._tasks.values() if t.enabled and isinstance(t.trigger, CronTrigger)]

    def list_idle_tasks(self) -> list[BackgroundTask]:
        """List enabled tasks with idle triggers."""
        return [t for t in self._tasks.values() if t.enabled and isinstance(t.trigger, IdleTrigger)]

    async def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a task. Returns False if task not found."""
        task = self._tasks.get(name)
        if not task:
            return False

        # Create new task with updated enabled status
        updated_task = BackgroundTask(
            name=task.name,
            system_prompt=task.system_prompt,
            tools=task.tools,
            memory_blocks=task.memory_blocks,
            trigger=task.trigger,
            user_ids=task.user_ids,
            batch_size=task.batch_size,
            max_turns=task.max_turns,
            enabled=enabled,
        )
        await self.register(updated_task, persist=True)
        return True


# Module-level singleton
_registry: TaskRegistry | None = None


def get_registry() -> TaskRegistry:
    """Get the task registry singleton."""
    global _registry
    if _registry is None:
        _registry = TaskRegistry()
    return _registry
