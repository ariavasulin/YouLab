"""Curriculum management HTTP endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from letta_starter.curriculum import curriculum

log = structlog.get_logger()

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class CourseListResponse(BaseModel):
    """Response for course list."""

    courses: list[str]
    count: int


class ModuleSummary(BaseModel):
    """Summary of a module."""

    id: str
    name: str
    order: int
    lesson_count: int


class BlockSummary(BaseModel):
    """Summary of a memory block."""

    name: str
    label: str
    field_count: int
    fields: list[str]


class CourseDetailResponse(BaseModel):
    """Detailed course information."""

    id: str
    name: str
    version: str
    description: str
    modules: list[ModuleSummary]
    blocks: list[BlockSummary]
    background_agents: list[str]
    tool_count: int


class ReloadResponse(BaseModel):
    """Response for config reload."""

    success: bool
    courses_loaded: int
    courses: list[str]
    message: str


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/courses", response_model=CourseListResponse)
async def list_courses() -> CourseListResponse:
    """List all available courses."""
    courses = curriculum.list_courses()
    return CourseListResponse(courses=courses, count=len(courses))


@router.get("/courses/{course_id}", response_model=CourseDetailResponse)
async def get_course(course_id: str) -> CourseDetailResponse:
    """Get detailed course configuration."""
    course = curriculum.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")

    modules = [
        ModuleSummary(
            id=m.id,
            name=m.name,
            order=m.order,
            lesson_count=len(m.lessons),
        )
        for m in course.loaded_modules
    ]

    blocks = [
        BlockSummary(
            name=name,
            label=schema.label,
            field_count=len(schema.fields),
            fields=list(schema.fields.keys()),
        )
        for name, schema in course.blocks.items()
    ]

    return CourseDetailResponse(
        id=course.id,
        name=course.name,
        version=course.version,
        description=course.description,
        modules=modules,
        blocks=blocks,
        background_agents=list(course.background.keys()),
        tool_count=len(course.agent.tools),
    )


@router.get("/courses/{course_id}/full")
async def get_course_full(course_id: str) -> dict[str, Any]:
    """
    Get complete course configuration as JSON.

    This returns the full parsed configuration, useful for debugging
    or building UI editors.
    """
    course = curriculum.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")

    # Return full config (Pydantic handles serialization)
    return course.model_dump(exclude={"loaded_modules"})


@router.get("/courses/{course_id}/modules")
async def get_course_modules(course_id: str) -> list[dict[str, Any]]:
    """Get all modules for a course with full lesson details."""
    course = curriculum.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")

    return [m.model_dump() for m in course.loaded_modules]


@router.post("/reload", response_model=ReloadResponse)
async def reload_curriculum() -> ReloadResponse:
    """
    Reload all curriculum configurations from disk.

    This allows updating course configurations without restarting the server.
    """
    try:
        count = curriculum.reload()
        courses = curriculum.list_courses()

        log.info("curriculum_reloaded", courses=count)

        return ReloadResponse(
            success=True,
            courses_loaded=count,
            courses=courses,
            message=f"Successfully reloaded {count} course(s)",
        )
    except Exception as e:
        log.error("curriculum_reload_failed", error=str(e))
        return ReloadResponse(
            success=False,
            courses_loaded=0,
            courses=[],
            message=f"Reload failed: {e}",
        )
