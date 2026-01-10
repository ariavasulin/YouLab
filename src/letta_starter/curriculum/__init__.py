"""
Curriculum management package.

This package provides TOML-based course configuration loading and management.

Usage:
    from letta_starter.curriculum import curriculum

    # List available courses
    courses = curriculum.list_courses()

    # Load a course
    config = curriculum.get("college-essay")

    # Access course properties
    print(config.id, config.name)

    # Get block model classes for dynamic instantiation
    registry = curriculum.get_block_registry("college-essay")
    PersonaBlock = registry["persona"]
    block = PersonaBlock(name="Custom Name")
"""

from pathlib import Path

from letta_starter.curriculum.blocks import (
    DynamicBlock,
    create_block_model,
    create_block_registry,
)
from letta_starter.curriculum.loader import CurriculumLoader
from letta_starter.curriculum.schema import (
    AgentConfig,
    BackgroundAgentConfig,
    BlockSchema,
    CourseConfig,
    DialecticQuery,
    FieldSchema,
    FieldType,
    IdleTrigger,
    MergeStrategy,
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


class Curriculum:
    """
    Curriculum singleton for managing course configurations.

    This class wraps CurriculumLoader and provides additional functionality
    like block registry caching.
    """

    def __init__(self) -> None:
        self._loader: CurriculumLoader | None = None
        self._block_registries: dict[str, dict[str, type[DynamicBlock]]] = {}

    def initialize(self, config_dir: Path | str) -> None:
        """
        Initialize the curriculum with a config directory.

        Args:
            config_dir: Base directory for course configs.

        """
        self._loader = CurriculumLoader(config_dir)

    def _ensure_loader(self) -> CurriculumLoader:
        """Ensure loader is initialized, creating with defaults if needed."""
        if self._loader is None:
            self._loader = CurriculumLoader()
        return self._loader

    def list_courses(self) -> list[str]:
        """List available course IDs."""
        return self._ensure_loader().list_courses()

    def get(self, course_id: str) -> CourseConfig | None:
        """Get a course config, returning None if not found."""
        return self._ensure_loader().get(course_id)

    def load(self, course_id: str, force: bool = False) -> CourseConfig:
        """Load a course configuration."""
        return self._ensure_loader().load_course(course_id, force=force)

    def load_all(self) -> list[str]:
        """Load all available courses. Returns list of course IDs loaded."""
        loader = self._ensure_loader()
        courses = loader.list_courses()
        for course_id in courses:
            loader.load_course(course_id)
        return courses

    def reload(self) -> int:
        """Reload all courses, clearing all caches. Returns count loaded."""
        self._block_registries.clear()
        return self._ensure_loader().reload()

    def get_block_registry(self, course_id: str) -> dict[str, type[DynamicBlock]] | None:
        """
        Get the block model registry for a course.

        Returns a dict mapping block names to Pydantic model classes
        that can be instantiated to create memory blocks.
        """
        if course_id in self._block_registries:
            return self._block_registries[course_id]

        config = self.get(course_id)
        if config is None:
            return None

        registry = create_block_registry(config.blocks)
        self._block_registries[course_id] = registry
        return registry


# Singleton instance
curriculum = Curriculum()


__all__ = [
    "AgentConfig",
    "BackgroundAgentConfig",
    "BlockSchema",
    "CourseConfig",
    "Curriculum",
    "CurriculumLoader",
    "DialecticQuery",
    "DynamicBlock",
    "FieldSchema",
    "FieldType",
    "IdleTrigger",
    "MergeStrategy",
    "MessagesConfig",
    "ModuleConfig",
    "QueryConfig",
    "SessionScope",
    "StepAgent",
    "StepCompletion",
    "StepConfig",
    "TaskConfig",
    "ToolConfig",
    "ToolRuleType",
    "ToolRules",
    "Triggers",
    "create_block_model",
    "create_block_registry",
    "curriculum",
]
