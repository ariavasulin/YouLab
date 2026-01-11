"""Curriculum navigation tools for Letta agents."""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger()

# Global references set by service initialization
_letta_client: Any = None
_agent_course_map: dict[str, str] = {}  # agent_id -> course_id mapping


def set_letta_client(client: Any) -> None:
    """Set the global Letta client for tool use."""
    global _letta_client
    _letta_client = client


def set_agent_course(agent_id: str, course_id: str) -> None:
    """Set course context for an agent (called after agent creation/lookup)."""
    _agent_course_map[agent_id] = course_id


def advance_lesson(
    reason: str,
    agent_state: dict[str, Any] | None = None,
) -> str:
    """
    Request advancement to the next lesson in the curriculum.

    Call this when you believe the student has met the current lesson's
    objectives and is ready to progress. The system will:
    1. Update your journey block with the new lesson
    2. Return the opening message for the next lesson

    Args:
        reason: Why you believe the student is ready to advance.
                Be specific about which objectives were met.
        agent_state: Agent state injected by Letta (contains agent_id)

    Returns:
        The opening message for the next lesson, or a message indicating
        the current lesson if at the end of the course.

    """
    if _letta_client is None:
        return "Curriculum system unavailable. Cannot advance lesson."

    agent_id = agent_state.get("agent_id") if agent_state else None
    if not agent_id:
        return "Unable to identify agent. Cannot advance lesson."

    # Get course_id from agent context or metadata
    course_id = _agent_course_map.get(agent_id)
    if not course_id:
        # Try to get from agent metadata
        course_id = _get_course_id_from_agent(agent_id)
        if course_id:
            _agent_course_map[agent_id] = course_id

    if not course_id:
        return "Unable to determine course. Cannot advance lesson."

    try:
        result = _do_advance_lesson(agent_id, course_id, reason)
        log.info(
            "lesson_advanced",
            agent_id=agent_id,
            course_id=course_id,
            reason=reason[:100],
            result=result[:100] if result else None,
        )
        return result
    except Exception as e:
        log.error(
            "advance_lesson_failed",
            agent_id=agent_id,
            course_id=course_id,
            error=str(e),
        )
        return f"Failed to advance lesson: {e}"


def _get_course_id_from_agent(agent_id: str) -> str | None:
    """Get course_id from agent metadata."""
    try:
        agent = _letta_client.agents.retrieve(agent_id)
        metadata = agent.metadata or {}
        return metadata.get("course_id")
    except Exception:
        return None


def _do_advance_lesson(agent_id: str, course_id: str, reason: str) -> str:
    """Execute the lesson advancement logic."""
    from youlab_server.curriculum import curriculum

    # Get course config
    course = curriculum.get(course_id)
    if course is None:
        return f"Course '{course_id}' not found."

    if not course.loaded_modules:
        return "No modules defined in this course."

    # Get current journey state from agent memory
    journey_data = _get_journey_block(agent_id)
    current_module_id = journey_data.get("module_id", "")
    current_lesson_id = journey_data.get("lesson_id", "")

    if not current_module_id or not current_lesson_id:
        return _advance_to_first_lesson(agent_id, course, reason)

    # Find current position
    current_module, current_module_idx = _find_module(course, current_module_id)
    if current_module is None:
        return f"Current module '{current_module_id}' not found in course."

    current_lesson_idx = _find_lesson_idx(current_module, current_lesson_id)
    if current_lesson_idx == -1:
        return f"Current lesson '{current_lesson_id}' not found in module."

    # Determine and advance to next lesson
    return _advance_to_next(
        agent_id, course, current_module, current_module_idx, current_lesson_idx, reason
    )


def _advance_to_first_lesson(agent_id: str, course: Any, reason: str) -> str:
    """Advance to the first lesson of the first module."""
    first_module = course.loaded_modules[0]
    if not first_module.lessons:
        return "First module has no lessons."
    return _set_journey_and_get_opening(
        agent_id,
        first_module.id,
        first_module.lessons[0].id,
        reason,
        first_module.lessons[0],
    )


def _find_module(course: Any, module_id: str) -> tuple[Any, int]:
    """Find a module by ID, returning (module, index) or (None, -1)."""
    for idx, module in enumerate(course.loaded_modules):
        if module.id == module_id:
            return module, idx
    return None, -1


def _find_lesson_idx(module: Any, lesson_id: str) -> int:
    """Find a lesson index by ID, returning -1 if not found."""
    for idx, lesson in enumerate(module.lessons):
        if lesson.id == lesson_id:
            return idx
    return -1


def _advance_to_next(
    agent_id: str,
    course: Any,
    current_module: Any,
    current_module_idx: int,
    current_lesson_idx: int,
    reason: str,
) -> str:
    """Determine and advance to the next lesson."""
    # Next lesson in same module
    if current_lesson_idx + 1 < len(current_module.lessons):
        next_lesson = current_module.lessons[current_lesson_idx + 1]
        return _set_journey_and_get_opening(
            agent_id, current_module.id, next_lesson.id, reason, next_lesson
        )

    # First lesson of next module
    if current_module_idx + 1 < len(course.loaded_modules):
        next_module = course.loaded_modules[current_module_idx + 1]
        if not next_module.lessons:
            return f"Next module '{next_module.id}' has no lessons."
        next_lesson = next_module.lessons[0]
        return _set_journey_and_get_opening(
            agent_id, next_module.id, next_lesson.id, reason, next_lesson
        )

    # At end of course
    return (
        "You've reached the end of the curriculum! "
        f"Current position: {current_module.id}/{current_module.lessons[current_lesson_idx].id}. "
        "Continue supporting the student with their essays."
    )


def _get_journey_block(agent_id: str) -> dict[str, Any]:
    """Get journey block data from agent memory."""
    try:
        # Get all blocks for the agent
        blocks = _letta_client.agents.blocks.list(agent_id=agent_id)
        for block in blocks:
            if getattr(block, "label", None) == "journey":
                value = getattr(block, "value", "")
                return _parse_block_value(value)
    except Exception as e:
        log.warning("failed_to_get_journey_block", agent_id=agent_id, error=str(e))
    return {}


def _parse_block_value(content: str) -> dict[str, Any]:
    """Parse YAML-like block value into dict."""
    data: dict[str, Any] = {}
    current_field: str | None = None
    current_list: list[str] | None = None

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("- "):
            # List item
            if current_list is not None:
                current_list.append(line[2:])
        elif ":" in line:
            # Field definition
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Save previous list if any
            if current_field and current_list is not None:
                data[current_field] = current_list

            if value:
                # Simple field with value
                data[key] = value
                current_field = None
                current_list = None
            else:
                # Start of list field
                current_field = key
                current_list = []

    # Save final list
    if current_field and current_list is not None:
        data[current_field] = current_list

    return data


def _serialize_block_value(data: dict[str, Any]) -> str:
    """Serialize dict to YAML-like block value."""
    lines: list[str] = []
    for field_name, value in data.items():
        if isinstance(value, list):
            lines.append(f"{field_name}:")
            lines.extend(f"- {item}" for item in value)
        elif value:  # Only include non-empty values
            lines.append(f"{field_name}: {value}")
    return "\n".join(lines)


def _set_journey_and_get_opening(
    agent_id: str,
    module_id: str,
    lesson_id: str,
    reason: str,
    lesson: Any,
) -> str:
    """Update journey block and return lesson opening."""
    from youlab_server.curriculum.schema import LessonConfig

    # Update journey block
    journey_data = _get_journey_block(agent_id)

    # Add milestone for completed lesson
    milestones = journey_data.get("milestones", [])
    if isinstance(milestones, list):
        old_module = journey_data.get("module_id", "")
        old_lesson = journey_data.get("lesson_id", "")
        if old_module and old_lesson:
            milestone = f"{old_module}/{old_lesson}"
            if milestone not in milestones:
                milestones.append(milestone)

    # Update to new lesson
    journey_data["module_id"] = module_id
    journey_data["lesson_id"] = lesson_id
    journey_data["status"] = "in_progress"
    journey_data["grader_notes"] = ""  # Clear grader notes for new lesson
    journey_data["blockers"] = ""
    journey_data["milestones"] = milestones

    # Save updated journey
    _update_journey_block(agent_id, journey_data)

    # Get opening message
    if isinstance(lesson, LessonConfig) and lesson.agent.opening:
        return f"Advancing to {lesson.name}.\n\n{lesson.agent.opening}"
    return f"Advanced to lesson: {module_id}/{lesson_id}"


def _update_journey_block(agent_id: str, data: dict[str, Any]) -> None:
    """Update the journey block in agent memory."""
    try:
        blocks = _letta_client.agents.blocks.list(agent_id=agent_id)
        for block in blocks:
            if getattr(block, "label", None) == "journey":
                new_value = _serialize_block_value(data)
                _letta_client.agents.blocks.update(
                    agent_id=agent_id,
                    block_id=block.id,
                    value=new_value,
                )
                log.debug(
                    "journey_block_updated",
                    agent_id=agent_id,
                    module_id=data.get("module_id"),
                    lesson_id=data.get("lesson_id"),
                )
                return
    except Exception as e:
        log.error("failed_to_update_journey_block", agent_id=agent_id, error=str(e))
        raise
