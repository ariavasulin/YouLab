"""
Curriculum configuration schema definitions.

This module defines the Pydantic models for parsing TOML course configurations.
Supports both v1 (separate [course] + [agent]) and v2 (merged [agent]) schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# ENUMS
# =============================================================================


class SessionScope(str, Enum):
    """Scope for dialectic queries."""

    ALL = "all"
    RECENT = "recent"
    CURRENT = "current"
    SPECIFIC = "specific"


class MergeStrategy(str, Enum):
    """Strategy for merging insights into memory."""

    APPEND = "append"
    REPLACE = "replace"
    LLM_DIFF = "llm_diff"


class ToolRuleType(str, Enum):
    """Types of tool execution rules."""

    EXIT_LOOP = "exit_loop"
    CONTINUE_LOOP = "continue_loop"
    RUN_FIRST = "run_first"


class FieldType(str, Enum):
    """Types for block schema fields."""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DATETIME = "datetime"


# =============================================================================
# TOOL CONFIGURATION (v1 with v2 defaults)
# =============================================================================


class ToolRules(BaseModel):
    """Rules for tool execution."""

    type: ToolRuleType = ToolRuleType.CONTINUE_LOOP
    max_count: int | None = None


class ToolConfig(BaseModel):
    """Configuration for a single tool (v1 format)."""

    id: str
    enabled: bool = True
    rules: ToolRules | None = None


# =============================================================================
# BACKGROUND AGENT CONFIGURATION
# =============================================================================


class IdleTrigger(BaseModel):
    """Configuration for idle-based triggering."""

    enabled: bool = False
    threshold_minutes: int = 30
    cooldown_minutes: int = 60


class Triggers(BaseModel):
    """Trigger configuration for background agents."""

    schedule: str | None = None
    manual: bool = True
    after_messages: int | None = None
    idle: IdleTrigger = Field(default_factory=IdleTrigger)


class DialecticQuery(BaseModel):
    """A single dialectic query configuration."""

    id: str
    question: str
    session_scope: SessionScope = SessionScope.ALL
    recent_limit: int = 5
    target_block: str
    target_field: str
    merge_strategy: MergeStrategy = MergeStrategy.APPEND


class BackgroundAgentConfig(BaseModel):
    """Configuration for a background agent."""

    enabled: bool = True
    agent_types: list[str] = Field(default_factory=lambda: ["tutor"])
    user_filter: str = "all"
    batch_size: int = 50
    triggers: Triggers = Field(default_factory=Triggers)
    queries: list[DialecticQuery] = Field(default_factory=list)


# =============================================================================
# TASK CONFIGURATION (v2 - replaces background agents)
# =============================================================================


class QueryConfig(BaseModel):
    """Single dialectic query within a task (v2 format)."""

    target: str  # "block.field" format
    question: str
    scope: SessionScope = SessionScope.ALL
    recent_limit: int = 5
    merge: MergeStrategy = MergeStrategy.APPEND

    @property
    def target_block(self) -> str:
        """Extract block name from target."""
        return self.target.split(".")[0]

    @property
    def target_field(self) -> str:
        """Extract field name from target."""
        parts = self.target.split(".")
        return parts[1] if len(parts) > 1 else ""


class TaskConfig(BaseModel):
    """Background task configuration (v2 format)."""

    # Scheduling
    schedule: str | None = None
    manual: bool = True
    on_idle: bool = False
    idle_threshold_minutes: int = 30
    idle_cooldown_minutes: int = 60

    # Scope
    agent_types: list[str] = Field(default_factory=lambda: ["tutor"])
    user_filter: str = "all"
    batch_size: int = 50

    # Simple queries (optional)
    queries: list[QueryConfig] = Field(default_factory=list)

    # Full agent capabilities (optional)
    system: str | None = None
    tools: list[str] = Field(default_factory=list)


# =============================================================================
# FIELD & BLOCK SCHEMA
# =============================================================================


class FieldSchema(BaseModel):
    """Schema for a single field within a memory block."""

    type: FieldType
    default: Any = None
    options: list[str] | None = None
    max: int | None = None
    description: str | None = None
    required: bool = False


class BlockSchema(BaseModel):
    """Schema for a memory block."""

    label: str
    description: str = ""
    shared: bool = False  # v2: for cross-agent sharing
    fields: dict[str, FieldSchema] = Field(default_factory=dict)


# =============================================================================
# STEP & MODULE CONFIGURATION
# =============================================================================


class StepCompletion(BaseModel):
    """Completion criteria for a step."""

    required_fields: list[str] = Field(default_factory=list)
    min_turns: int | None = None
    min_list_length: dict[str, int] = Field(default_factory=dict)
    auto_advance: bool = False


class StepAgent(BaseModel):
    """Step-specific agent configuration."""

    opening: str | None = None
    focus: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    persona_overrides: dict[str, Any] = Field(default_factory=dict)
    disabled_tools: list[str] = Field(default_factory=list)


class StepConfig(BaseModel):
    """Configuration for a single step."""

    id: str
    name: str
    order: int = 0
    description: str = ""
    objectives: list[str] = Field(default_factory=list)
    completion: StepCompletion = Field(default_factory=StepCompletion)
    agent: StepAgent = Field(default_factory=StepAgent)


class ModuleConfig(BaseModel):
    """Configuration for a curriculum module."""

    id: str
    name: str
    order: int = 0
    description: str = ""
    steps: list[StepConfig] = Field(default_factory=list)
    disabled_tools: list[str] = Field(default_factory=list)


# =============================================================================
# MESSAGES CONFIGURATION
# =============================================================================


class MessagesConfig(BaseModel):
    """UI message templates."""

    welcome_first: str = "Hello! How can I help you today?"
    welcome_returning: str = "Welcome back!"
    error_unavailable: str = "I'm temporarily unavailable. Please try again."


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================


class AgentConfig(BaseModel):
    """
    Agent configuration.

    In v2 schema, this also contains course metadata (id, name, etc.).
    In v1 schema, these fields come from [course] section.
    """

    # v2: Course metadata (merged into [agent])
    id: str = ""  # Empty default for v1 compatibility
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    modules: list[str] = Field(default_factory=list)

    # Agent settings
    model: str = "anthropic/claude-sonnet-4-20250514"
    embedding: str = "openai/text-embedding-3-small"
    context_window: int = 128000
    max_response_tokens: int = 4096
    system: str = ""

    # v1: Full tool config with rules
    tools: list[ToolConfig] = Field(default_factory=list)


# =============================================================================
# COURSE CONFIGURATION
# =============================================================================


class CourseConfig(BaseModel):
    """Complete course configuration."""

    agent: AgentConfig = Field(default_factory=AgentConfig)

    # Memory blocks
    blocks: dict[str, BlockSchema] = Field(default_factory=dict)

    # v1: Background agents (deprecated)
    background: dict[str, BackgroundAgentConfig] = Field(default_factory=dict)

    # v2: Tasks (replaces background)
    tasks: list[TaskConfig] = Field(default_factory=list)

    # UI messages
    messages: MessagesConfig = Field(default_factory=MessagesConfig)

    # Loaded modules (populated by loader)
    loaded_modules: list[ModuleConfig] = Field(default_factory=list, exclude=True)

    # Convenience accessors (delegate to agent)
    @property
    def id(self) -> str:
        """Course identifier."""
        return self.agent.id

    @property
    def name(self) -> str:
        """Course display name."""
        return self.agent.name

    @property
    def version(self) -> str:
        """Course version."""
        return self.agent.version

    @property
    def description(self) -> str:
        """Course description."""
        return self.agent.description
