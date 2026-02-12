"""Memory block loading for agent instructions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ralph.dolt import DoltClient

log = structlog.get_logger()

# Welcome course block templates (from welcome.toml)
WELCOME_BLOCK_TEMPLATES: list[dict[str, str]] = [
    {
        "label": "origin_story",
        "title": "Origin Story",
        "template": (
            "## Who I Am At My Best\n\n"
            "[Moments when they feel most alive, capable, energized]\n\n"
            "## What I'm Building Toward\n\n"
            "[6-12 month vision, concrete goals, why these matter]\n\n"
            "## My Superpowers\n\n"
            "[Natural strengths, what comes easily, what others come to them for]\n\n"
            "## My Kryptonite\n\n"
            "[What drains them, patterns they fight against, blind spots]\n"
        ),
    },
    {
        "label": "tech_relationship",
        "title": "Tech Relationship",
        "template": (
            "## Current State\n\n"
            "[How they use technology now\u2014the good, the bad, the ugly]\n\n"
            "## Where Technology Serves Me\n\n"
            "[Tools, apps, patterns that genuinely help]\n\n"
            "## Where I Get Hijacked\n\n"
            "[Distraction patterns, default behaviors, time sinks]\n\n"
            "## My Scrolling Triggers\n\n"
            "[Emotional states, situations, times when they reach for the phone]\n\n"
            "## What Intentional Would Look Like\n\n"
            "[Their vision of technology serving their goals]\n"
        ),
    },
    {
        "label": "ai_partnership",
        "title": "AI Partnership",
        "template": (
            "## What AI Should Help Me With\n\n"
            "[Specific use cases aligned with their goals and strengths]\n\n"
            "## What AI Should Never Do For Me\n\n"
            "[Protected areas\u2014judgment, relationships, creative voice, etc.]\n\n"
            "## My Definition of Superhuman\n\n"
            '[What "becoming more fully themselves, amplified" means for them]\n\n'
            "## Guardrails\n\n"
            "[Signs that AI use is becoming unhealthy or dependency-forming]\n"
        ),
    },
    {
        "label": "onboarding_progress",
        "title": "Current Progress",
        "template": (
            "## Status\n\n"
            "User is working their way through the Welcome module:\n\n"
            "[ ] Phase 1: Presence (Who are you?)\n"
            "[ ] Phase 2: Patterns (How do you relate to tech?)\n"
            "[ ] Phase 3: Possibilities (How might AI serve you?)\n"
            "[ ] Graduated\n\n"
            "## Key Moments\n\n"
            "[Breakthrough insights, memorable exchanges, turning points]\n\n"
            "## Open Threads\n\n"
            "[Questions still being explored, topics to return to]\n"
        ),
    },
]


async def ensure_welcome_blocks(dolt: DoltClient, user_id: str) -> bool:
    """
    Initialize welcome course memory blocks for a user if they have none.

    Returns True if blocks were created (new user), False if they already existed.
    """
    existing = await dolt.list_blocks(user_id)
    if existing:
        return False

    log.info("initializing_welcome_blocks", user_id=user_id)
    for tmpl in WELCOME_BLOCK_TEMPLATES:
        await dolt.update_block(
            user_id=user_id,
            label=tmpl["label"],
            body=tmpl["template"],
            title=tmpl["title"],
            author="system",
            message=f"Initialize {tmpl['label']} from welcome template",
        )
    log.info("welcome_blocks_initialized", user_id=user_id, count=len(WELCOME_BLOCK_TEMPLATES))
    return True


async def build_memory_context(
    dolt: DoltClient,
    user_id: str,
    labels: list[str] | None = None,
) -> str:
    """
    Build memory context string for agent instructions.

    Args:
        dolt: DoltClient instance for database access
        user_id: The user ID to fetch memory blocks for
        labels: Optional list of block labels to include (None = all)

    Returns:
        A formatted markdown string with memory blocks, or empty string if none.

    """
    blocks = await dolt.list_blocks(user_id)

    # Filter by labels if specified
    if labels:
        blocks = [b for b in blocks if b.label in labels]

    if not blocks:
        return ""

    sections = ["## Student Memory\n"]

    for block in blocks:
        title = block.title or block.label.replace("_", " ").title()
        body = block.body or "(empty)"
        sections.append(f"### {title} (label: `{block.label}`)\n\n{body}\n")

    return "\n".join(sections)


async def get_block_for_agent(
    dolt: DoltClient,
    user_id: str,
    label: str,
) -> str | None:
    """
    Get a specific block's content for agent use.

    Args:
        dolt: DoltClient instance for database access
        user_id: The user ID to fetch the block for
        label: The block label (e.g., "student", "journey")

    Returns:
        The block body content, or None if not found.

    """
    block = await dolt.get_block(user_id, label)
    if not block:
        return None
    return block.body
