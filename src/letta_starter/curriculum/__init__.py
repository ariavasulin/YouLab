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
    LessonAgent,
    LessonCompletion,
    LessonConfig,
    MergeStrategy,
    MessagesConfig,
    ModuleConfig,
    QueryConfig,
    SessionScope,
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
        self._loader = CurriculumLoader()
        self._block_registries: dict[str, dict[str, type[DynamicBlock]]] = {}

    def list_courses(self) -> list[str]:
        """List available course IDs."""
        return self._loader.list_courses()

    def get(self, course_id: str) -> CourseConfig | None:
        """Get a course config, returning None if not found."""
        return self._loader.get(course_id)

    def load(self, course_id: str, force: bool = False) -> CourseConfig:
        """Load a course configuration."""
        return self._loader.load_course(course_id, force=force)

    def reload(self) -> int:
        """Reload all courses, clearing all caches. Returns count loaded."""
        self._block_registries.clear()
        return self._loader.reload()

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
    "LessonAgent",
    "LessonCompletion",
    "LessonConfig",
    "MergeStrategy",
    "MessagesConfig",
    "ModuleConfig",
    "QueryConfig",
    "SessionScope",
    "TaskConfig",
    "ToolConfig",
    "ToolRuleType",
    "ToolRules",
    "Triggers",
    "create_block_model",
    "create_block_registry",
    "curriculum",
]
