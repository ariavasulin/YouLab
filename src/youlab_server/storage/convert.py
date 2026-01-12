"""TOML ↔ Markdown conversion for memory blocks."""

from __future__ import annotations

import re
import tomllib
from typing import Any

import tomli_w


def toml_to_markdown(toml_content: str, block_label: str) -> str:
    """
    Convert TOML block to Markdown for user editing.

    Format:
        ---
        block: student
        ---

        ## Profile
        Background, CliftonStrengths, aspirations...

        ## Insights
        Key observations from conversation...

    Args:
        toml_content: TOML string
        block_label: Block label for frontmatter

    Returns:
        Markdown string

    """
    try:
        data = tomllib.loads(toml_content)
    except tomllib.TOMLDecodeError:
        # If invalid TOML, return as-is in code block
        return (
            f"---\nblock: {block_label}\nerror: invalid_toml\n---\n\n```toml\n{toml_content}\n```"
        )

    lines = [
        "---",
        f"block: {block_label}",
        "---",
        "",
    ]

    # Convert each field to a section
    for key, value in data.items():
        # Convert snake_case to Title Case
        title = key.replace("_", " ").title()
        lines.append(f"## {title}")
        lines.append("")

        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        elif isinstance(value, str):
            # Multi-line strings get their own paragraph
            lines.append(value)
        elif isinstance(value, bool):
            lines.append("Yes" if value else "No")
        elif value is None:
            lines.append("*(not set)*")
        else:
            lines.append(str(value))

        lines.append("")

    return "\n".join(lines)


def markdown_to_toml(markdown_content: str) -> tuple[str, dict[str, Any]]:
    """
    Convert Markdown back to TOML.

    Parses sections and reconstructs structured data.

    Args:
        markdown_content: Markdown string

    Returns:
        Tuple of (toml_string, metadata_dict)

    """
    lines = markdown_content.strip().split("\n")

    # Parse frontmatter
    metadata: dict[str, Any] = {}
    content_start = 0

    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                content_start = i + 1
                break
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

    # Parse sections
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_content: list[str] = []
    current_is_list = False

    for line in lines[content_start:]:
        # New section header
        if line.startswith("## "):
            # Save previous section
            if current_section is not None:
                data[current_section] = _finalize_section(current_content, current_is_list)

            # Start new section
            title = line[3:].strip()
            current_section = _title_to_key(title)
            current_content = []
            current_is_list = False
        elif current_section is not None:
            stripped = line.strip()
            if stripped.startswith("- "):
                current_is_list = True
                current_content.append(stripped[2:])
            elif stripped and stripped != "*(not set)*":
                current_content.append(line)

    # Save last section
    if current_section is not None:
        data[current_section] = _finalize_section(current_content, current_is_list)

    toml_str = tomli_w.dumps(data)
    return toml_str, metadata


def _title_to_key(title: str) -> str:
    """Convert Title Case to snake_case."""
    return re.sub(r"\s+", "_", title.lower())


def _finalize_section(content: list[str], is_list: bool) -> str | list[str]:
    """Finalize section content."""
    if is_list:
        return content
    # Join non-list content as paragraphs
    text = "\n".join(content).strip()
    return text if text else ""
