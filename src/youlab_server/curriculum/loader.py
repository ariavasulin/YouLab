"""
TOML course configuration loader.

This module handles loading and caching course configurations from TOML files.
Supports both v1 (separate [course] + [agent]) and v2 (merged [agent]) schemas.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import structlog

from youlab_server.curriculum.schema import (
    AgentConfig,
    BackgroundAgentConfig,
    BlockSchema,
    CourseConfig,
    DialecticQuery,
    FieldSchema,
    FieldType,
    IdleTrigger,
    MessagesConfig,
    ModuleConfig,
    QueryConfig,
    SessionScope,
    StepAgent,
    StepCompletion,
    StepConfig,
    TaskConfig,
    ToolConfig,
    ToolRules,
    ToolRuleType,
    Triggers,
)

log = structlog.get_logger()


class CurriculumLoader:
    """Loads and caches course configurations from TOML files."""

    def __init__(self, config_dir: Path | str | None = None) -> None:
        """
        Initialize the curriculum loader.

        Args:
            config_dir: Base directory for course configs.
                       Defaults to config/courses relative to project root.

        """
        if config_dir is None:
            # Default to config/courses from project root
            config_dir = Path(__file__).parent.parent.parent.parent / "config" / "courses"
        self.config_dir = Path(config_dir)
        self._cache: dict[str, CourseConfig] = {}

    def list_courses(self) -> list[str]:
        """List available course IDs."""
        if not self.config_dir.exists():
            return []
        return sorted(
            path.name
            for path in self.config_dir.iterdir()
            if path.is_dir() and (path / "course.toml").exists()
        )

    def load_course(self, course_id: str, force: bool = False) -> CourseConfig:
        """
        Load a course configuration.

        Args:
            course_id: Course identifier (directory name)
            force: Force reload even if cached

        Returns:
            CourseConfig instance

        Raises:
            FileNotFoundError: If course.toml doesn't exist
            ValueError: If TOML is invalid

        """
        if not force and course_id in self._cache:
            return self._cache[course_id]

        course_dir = self.config_dir / course_id
        course_file = course_dir / "course.toml"

        if not course_file.exists():
            raise FileNotFoundError(f"Course not found: {course_file}")

        # Load main course.toml
        data = self._load_toml(course_file)

        # Parse course config
        config = self._parse_course_config(data)

        # Load modules
        config.loaded_modules = self._load_modules(course_dir, config.agent.modules)

        self._cache[course_id] = config

        log.debug(
            "course_loaded",
            course_id=course_id,
            blocks=len(config.blocks),
            modules=len(config.loaded_modules),
        )

        return config

    def get(self, course_id: str) -> CourseConfig | None:
        """Get a course config, returning None if not found."""
        try:
            return self.load_course(course_id)
        except FileNotFoundError:
            return None

    def reload(self) -> int:
        """Reload all courses, clearing the cache. Returns count loaded."""
        self._cache.clear()
        count = 0
        for course_id in self.list_courses():
            try:
                self.load_course(course_id)
                count += 1
            except Exception as e:
                log.warning("course_reload_failed", course_id=course_id, error=str(e))
        return count

    def _load_toml(self, path: Path) -> dict[str, Any]:
        """Load a TOML file."""
        with path.open("rb") as f:
            return tomllib.load(f)

    def _parse_course_config(self, data: dict[str, Any]) -> CourseConfig:
        """Parse TOML data, supporting both v1 and v2 schemas."""
        # Detect schema version
        has_v2_agent = "agent" in data and "id" in data.get("agent", {})
        has_v1_course = "course" in data
        has_v2_blocks = "block" in data
        has_v1_blocks = "blocks" in data

        # Parse agent config
        if has_v2_agent:
            # v2: [agent] contains everything
            agent_data = data["agent"]
            agent = self._parse_agent_config(agent_data, is_v2=True)
        elif has_v1_course:
            # v1: [course] + [agent] separate
            course_data = data.get("course", {})
            agent_data = data.get("agent", {})
            # Merge course metadata into agent
            merged = {**agent_data}
            merged["id"] = course_data.get("id", "")
            merged["name"] = course_data.get("name", "")
            merged["version"] = course_data.get("version", "1.0.0")
            merged["description"] = course_data.get("description", "")
            merged["modules"] = course_data.get("modules", [])
            agent = self._parse_agent_config(merged, is_v2=False)
        else:
            raise ValueError("Config must have [agent] or [course] section")

        # Parse blocks
        if has_v2_blocks:
            blocks = self._parse_blocks_v2(data["block"])
        elif has_v1_blocks:
            blocks = self._parse_blocks_v1(data["blocks"])
        else:
            blocks = {}

        # Parse background agents (v1) or tasks (v2)
        background = self._parse_background(data.get("background", {}))
        tasks = self._parse_tasks(data.get("task", []))

        # Parse messages
        messages_data = data.get("messages", {})
        messages = MessagesConfig(**messages_data)

        return CourseConfig(
            agent=agent,
            blocks=blocks,
            background=background,
            tasks=tasks,
            messages=messages,
        )

    def _parse_agent_config(self, data: dict[str, Any], is_v2: bool) -> AgentConfig:
        """Parse agent configuration."""
        # Handle tools
        tools_data = data.get("tools", [])
        if is_v2 and isinstance(tools_data, list) and tools_data:
            # v2: simple list of strings with optional :rule suffix
            if isinstance(tools_data[0], str):
                tools = self._parse_tools_v2(tools_data)
            else:
                # Still v1 format [[agent.tools]]
                tools = self._parse_tools_v1(tools_data)
        else:
            # v1: [[agent.tools]] array of objects
            tools = self._parse_tools_v1(tools_data)

        return AgentConfig(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            modules=data.get("modules", []),
            model=data.get("model", "anthropic/claude-sonnet-4-20250514"),
            embedding=data.get("embedding", "openai/text-embedding-3-small"),
            context_window=data.get("context_window", 128000),
            max_response_tokens=data.get("max_response_tokens", 4096),
            system=data.get("system", ""),
            tools=tools,
        )

    def _parse_tools_v1(self, tools_data: list[dict[str, Any]]) -> list[ToolConfig]:
        """Parse v1 [[agent.tools]] format."""
        tools = []
        for tool_data in tools_data:
            rules_data = tool_data.get("rules")
            rules = None
            if rules_data:
                rule_type = rules_data.get("type", "continue_loop")
                rules = ToolRules(
                    type=ToolRuleType(rule_type),
                    max_count=rules_data.get("max_count"),
                )
            tools.append(
                ToolConfig(
                    id=tool_data["id"],
                    enabled=tool_data.get("enabled", True),
                    rules=rules,
                )
            )
        return tools

    def _parse_tools_v2(self, tools_data: list[str]) -> list[ToolConfig]:
        """Parse v2 tools = ["name", "name:rule"] format."""
        from youlab_server.tools import ToolRule, get_tool_rule

        tools = []
        for spec in tools_data:
            tool_id, rule = get_tool_rule(spec)

            # Map ToolRule to ToolRuleType
            rule_map = {
                ToolRule.EXIT_LOOP: ToolRuleType.EXIT_LOOP,
                ToolRule.CONTINUE_LOOP: ToolRuleType.CONTINUE_LOOP,
                ToolRule.RUN_FIRST: ToolRuleType.RUN_FIRST,
            }

            tools.append(
                ToolConfig(
                    id=tool_id,
                    enabled=True,
                    rules=ToolRules(type=rule_map[rule]),
                )
            )
        return tools

    def _parse_blocks_v1(self, blocks_data: dict[str, Any]) -> dict[str, BlockSchema]:
        """Parse v1 [blocks.x.fields] format."""
        blocks = {}
        for block_name, block_data in blocks_data.items():
            fields_data = block_data.get("fields", {})
            fields = {}
            for field_name, field_data in fields_data.items():
                fields[field_name] = FieldSchema(
                    type=FieldType(field_data.get("type", "string")),
                    default=field_data.get("default"),
                    options=field_data.get("options"),
                    max=field_data.get("max"),
                    description=field_data.get("description"),
                    required=field_data.get("required", False),
                )
            blocks[block_name] = BlockSchema(
                label=block_data.get("label", block_name),
                description=block_data.get("description", ""),
                shared=block_data.get("shared", False),
                fields=fields,
            )
        return blocks

    def _parse_blocks_v2(self, blocks_data: dict[str, Any]) -> dict[str, BlockSchema]:
        """
        Parse v2 [block.x] with field.* dotted keys format.

        In TOML, `field.name = {...}` is parsed as `{"field": {"name": {...}}}`.
        This method extracts the nested `field` dict to get field definitions.
        """
        blocks = {}
        for block_name, block_data in blocks_data.items():
            fields = {}

            # TOML parses field.name as {"field": {"name": {...}}}
            field_dict = block_data.get("field", {})
            for field_name, field_value in field_dict.items():
                fields[field_name] = FieldSchema(
                    type=FieldType(field_value.get("type", "string")),
                    default=field_value.get("default"),
                    options=field_value.get("options"),
                    max=field_value.get("max"),
                    description=field_value.get("description"),
                    required=field_value.get("required", False),
                )

            blocks[block_name] = BlockSchema(
                label=block_data.get("label", block_name),
                description=block_data.get("description", ""),
                shared=block_data.get("shared", False),
                fields=fields,
            )
        return blocks

    def _parse_background(
        self, background_data: dict[str, Any]
    ) -> dict[str, BackgroundAgentConfig]:
        """Parse [background.x] configurations."""
        configs = {}
        for name, data in background_data.items():
            triggers_data = data.get("triggers", {})
            idle_data = triggers_data.get("idle", {})

            triggers = Triggers(
                schedule=triggers_data.get("schedule"),
                manual=triggers_data.get("manual", True),
                after_messages=triggers_data.get("after_messages"),
                idle=IdleTrigger(
                    enabled=idle_data.get("enabled", False),
                    threshold_minutes=idle_data.get("threshold_minutes", 30),
                    cooldown_minutes=idle_data.get("cooldown_minutes", 60),
                ),
            )

            queries = [
                DialecticQuery(
                    id=q_data.get("id", ""),
                    question=q_data.get("question", ""),
                    session_scope=SessionScope(q_data.get("session_scope", "all")),
                    recent_limit=q_data.get("recent_limit", 5),
                    target_block=q_data.get("target_block", ""),
                    target_field=q_data.get("target_field", ""),
                    merge_strategy=q_data.get("merge_strategy", "append"),
                )
                for q_data in data.get("queries", [])
            ]

            configs[name] = BackgroundAgentConfig(
                enabled=data.get("enabled", True),
                agent_types=data.get("agent_types", ["tutor"]),
                user_filter=data.get("user_filter", "all"),
                batch_size=data.get("batch_size", 50),
                triggers=triggers,
                queries=queries,
            )

        return configs

    def _parse_tasks(self, tasks_data: list[dict[str, Any]]) -> list[TaskConfig]:
        """Parse [[task]] array."""
        tasks = []
        for task_data in tasks_data:
            queries = [
                QueryConfig(
                    target=q_data.get("target", ""),
                    question=q_data.get("question", ""),
                    scope=SessionScope(q_data.get("scope", "all")),
                    recent_limit=q_data.get("recent_limit", 5),
                    merge=q_data.get("merge", "append"),
                )
                for q_data in task_data.get("queries", [])
            ]

            tasks.append(
                TaskConfig(
                    schedule=task_data.get("schedule"),
                    manual=task_data.get("manual", True),
                    on_idle=task_data.get("on_idle", False),
                    idle_threshold_minutes=task_data.get("idle_threshold_minutes", 30),
                    idle_cooldown_minutes=task_data.get("idle_cooldown_minutes", 60),
                    agent_types=task_data.get("agent_types", ["tutor"]),
                    user_filter=task_data.get("user_filter", "all"),
                    batch_size=task_data.get("batch_size", 50),
                    queries=queries,
                    system=task_data.get("system"),
                    tools=task_data.get("tools", []),
                )
            )

        return tasks

    def _load_modules(self, course_dir: Path, module_names: list[str]) -> list[ModuleConfig]:
        """Load module configurations."""
        modules = []
        modules_dir = course_dir / "modules"

        for module_name in module_names:
            module_file = modules_dir / f"{module_name}.toml"
            if not module_file.exists():
                log.warning("module_not_found", module=module_name)
                continue

            data = self._load_toml(module_file)
            module_data = data.get("module", {})

            steps = []
            for step_data in data.get("steps", []):
                completion_data = step_data.get("completion", {})
                agent_data = step_data.get("agent", {})

                steps.append(
                    StepConfig(
                        id=step_data.get("id", ""),
                        name=step_data.get("name", ""),
                        order=step_data.get("order", 0),
                        description=step_data.get("description", ""),
                        objectives=step_data.get("objectives", []),
                        completion=StepCompletion(
                            required_fields=completion_data.get("required_fields", []),
                            min_turns=completion_data.get("min_turns"),
                            min_list_length=completion_data.get("min_list_length", {}),
                            auto_advance=completion_data.get("auto_advance", False),
                        ),
                        agent=StepAgent(
                            opening=agent_data.get("opening"),
                            focus=agent_data.get("focus", []),
                            guidance=agent_data.get("guidance", []),
                            persona_overrides=agent_data.get("persona_overrides", {}),
                            disabled_tools=agent_data.get("disabled_tools", []),
                        ),
                    )
                )

            modules.append(
                ModuleConfig(
                    id=module_data.get("id", module_name),
                    name=module_data.get("name", module_name),
                    order=module_data.get("order", 0),
                    description=module_data.get("description", ""),
                    steps=steps,
                    disabled_tools=module_data.get("disabled_tools", []),
                )
            )

        return modules
