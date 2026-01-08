"""TOML configuration schema for background agents."""

from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path  # noqa: TC003 - needed at runtime for Path operations

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()


class SessionScope(str, Enum):
    """Session scope for dialectic queries."""

    ALL = "all"
    RECENT = "recent"
    CURRENT = "current"
    SPECIFIC = "specific"


class MergeStrategy(str, Enum):
    """Strategy for merging content into memory blocks."""

    APPEND = "append"
    REPLACE = "replace"
    LLM_DIFF = "llm_diff"


class IdleTrigger(BaseModel):
    """Idle-based trigger configuration."""

    enabled: bool = False
    threshold_minutes: int = 30
    cooldown_minutes: int = 60


class Triggers(BaseModel):
    """Trigger configuration for background agent."""

    schedule: str | None = None  # Cron expression
    idle: IdleTrigger = Field(default_factory=IdleTrigger)
    manual: bool = True


class DialecticQuery(BaseModel):
    """Single dialectic query configuration."""

    id: str
    question: str
    session_scope: SessionScope = SessionScope.ALL
    recent_limit: int = 5
    target_block: str  # "human" or "persona"
    target_field: str  # "context_notes", "facts", etc.
    merge_strategy: MergeStrategy = MergeStrategy.APPEND


class BackgroundAgentConfig(BaseModel):
    """Configuration for a single background agent."""

    id: str
    name: str
    enabled: bool = True
    triggers: Triggers = Field(default_factory=Triggers)
    agent_types: list[str] = Field(default_factory=lambda: ["tutor"])
    user_filter: str = "all"  # "all" or specific user_ids
    batch_size: int = 50
    queries: list[DialecticQuery] = Field(default_factory=list)


class CourseConfig(BaseModel):
    """Course-level configuration including background agents."""

    id: str
    name: str
    background_agents: list[BackgroundAgentConfig] = Field(default_factory=list)


def load_course_config(path: Path) -> CourseConfig:
    """
    Load course configuration from TOML file.

    Args:
        path: Path to the TOML file

    Returns:
        Parsed CourseConfig

    Raises:
        FileNotFoundError: If the file doesn't exist
        tomllib.TOMLDecodeError: If the TOML is invalid
        pydantic.ValidationError: If the schema doesn't match

    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    return CourseConfig(**data)


def load_all_course_configs(directory: Path) -> dict[str, CourseConfig]:
    """
    Load all course configs from a directory.

    Args:
        directory: Path to directory containing TOML files

    Returns:
        Dictionary mapping course_id to CourseConfig

    """
    configs: dict[str, CourseConfig] = {}

    if not directory.exists():
        return configs

    for toml_file in directory.glob("*.toml"):
        try:
            config = load_course_config(toml_file)
            configs[config.id] = config
        except Exception as e:
            log.warning(
                "course_config_load_failed",
                file=str(toml_file),
                error=str(e),
            )
            continue

    return configs
