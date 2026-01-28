"""Background task data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class TriggerType(str, Enum):
    """Trigger types for background tasks."""

    CRON = "cron"
    IDLE = "idle"


@dataclass
class CronTrigger:
    """Cron-style trigger configuration."""

    schedule: str  # Cron expression, e.g., "0 3 * * *" (3 AM daily)


@dataclass
class IdleTrigger:
    """Idle-based trigger configuration."""

    idle_minutes: int  # Minutes after last message to trigger
    cooldown_minutes: int = 60  # Minimum minutes between runs per user


@dataclass
class BackgroundTask:
    """Definition of a background task."""

    name: str
    system_prompt: str
    tools: list[str]  # Tool names to include (e.g., ["query_honcho", "edit_memory_block"])
    memory_blocks: list[str]  # Block labels to include in context
    trigger: CronTrigger | IdleTrigger
    user_ids: list[str]  # Explicit list of users to process
    batch_size: int = 5  # Number of users to process concurrently
    max_turns: int = 10  # Maximum agent turns per user
    enabled: bool = True


class RunStatus(str, Enum):
    """Status of a task run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some users succeeded, some failed


@dataclass
class UserRunResult:
    """Result of running a task for a single user."""

    user_id: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    turns_used: int = 0
    error: str | None = None
    proposals_created: int = 0


@dataclass
class TaskRun:
    """Record of a task execution."""

    id: str  # UUID
    task_name: str
    trigger_type: TriggerType
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    user_results: list[UserRunResult] = field(default_factory=list)
    error: str | None = None  # Top-level error (e.g., task not found)


@dataclass
class UserActivity:
    """Tracks user activity for idle triggers."""

    user_id: str
    last_message_at: datetime
    last_task_run_at: dict[str, datetime] = field(default_factory=dict)  # task_name -> last_run
