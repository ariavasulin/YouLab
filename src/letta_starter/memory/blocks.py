"""
Memory block schemas and serialization.

This is the heart of context engineering - structured, validated memory blocks
that maximize the utility of every token in the LLM's context window.
"""

import contextlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    """Current state of the agent session."""

    IDLE = "idle"
    ACTIVE_TASK = "active_task"
    WAITING_INPUT = "waiting_input"
    THINKING = "thinking"
    ERROR_RECOVERY = "error_recovery"


class PersonaBlock(BaseModel):
    """
    Schema for agent persona memory block.

    The persona defines WHO the agent is - its identity, capabilities,
    communication style, and behavioral constraints.

    This block should be relatively stable across sessions.
    """

    # Identity
    name: str = Field(
        default="Assistant",
        description="Agent's name",
    )
    role: str = Field(
        description="Agent's primary role/purpose",
    )

    # Capabilities (what the agent can do)
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of agent capabilities",
    )

    # Communication style
    tone: str = Field(
        default="professional",
        description="Communication tone: professional, friendly, formal, casual",
    )
    verbosity: str = Field(
        default="concise",
        description="Response length: concise, detailed, adaptive",
    )

    # Behavioral constraints
    constraints: list[str] = Field(
        default_factory=list,
        description="Things the agent should NOT do",
    )

    # Domain expertise
    expertise: list[str] = Field(
        default_factory=list,
        description="Areas of expertise",
    )

    def to_memory_string(self, max_chars: int = 1500) -> str:
        """
        Serialize to compact memory format.

        Uses a structured but token-efficient format that the LLM
        can easily parse and reference.
        """
        lines = [
            f"[IDENTITY] {self.name} | {self.role}",
        ]

        if self.capabilities:
            caps = ", ".join(self.capabilities[:5])
            lines.append(f"[CAPABILITIES] {caps}")

        if self.expertise:
            exp = ", ".join(self.expertise[:4])
            lines.append(f"[EXPERTISE] {exp}")

        lines.append(f"[STYLE] {self.tone}, {self.verbosity}")

        if self.constraints:
            const = "; ".join(self.constraints[:3])
            lines.append(f"[CONSTRAINTS] {const}")

        result = "\n".join(lines)
        return result[:max_chars]

    @classmethod
    def from_memory_string(cls, memory_str: str) -> "PersonaBlock":
        """Parse a memory string back into a PersonaBlock (best effort)."""
        data: dict[str, Any] = {"role": "Assistant"}

        for line in memory_str.strip().split("\n"):
            if line.startswith("[IDENTITY]"):
                parts = line.replace("[IDENTITY]", "").strip().split("|")
                if len(parts) >= 1:
                    data["name"] = parts[0].strip()
                if len(parts) >= 2:
                    data["role"] = parts[1].strip()
            elif line.startswith("[CAPABILITIES]"):
                caps = line.replace("[CAPABILITIES]", "").strip()
                data["capabilities"] = [c.strip() for c in caps.split(",")]
            elif line.startswith("[EXPERTISE]"):
                exp = line.replace("[EXPERTISE]", "").strip()
                data["expertise"] = [e.strip() for e in exp.split(",")]
            elif line.startswith("[STYLE]"):
                style = line.replace("[STYLE]", "").strip().split(",")
                if len(style) >= 1:
                    data["tone"] = style[0].strip()
                if len(style) >= 2:
                    data["verbosity"] = style[1].strip()
            elif line.startswith("[CONSTRAINTS]"):
                const = line.replace("[CONSTRAINTS]", "").strip()
                data["constraints"] = [c.strip() for c in const.split(";")]

        return cls(**data)


class HumanBlock(BaseModel):
    """
    Schema for human/user context memory block.

    The human block stores information about the current user and session.
    This block is dynamic and updated frequently during conversations.
    """

    # User identity (optional, learned over time)
    name: str | None = Field(
        default=None,
        description="User's name",
    )
    role: str | None = Field(
        default=None,
        description="User's role/profession",
    )

    # Current session
    current_task: str | None = Field(
        default=None,
        description="What the user is currently working on",
    )
    session_state: SessionState = Field(
        default=SessionState.IDLE,
        description="Current session state",
    )

    # Preferences (learned over time)
    preferences: list[str] = Field(
        default_factory=list,
        description="User preferences discovered during conversation",
    )

    # Dynamic context (updated frequently)
    context_notes: list[str] = Field(
        default_factory=list,
        description="Recent context notes, most recent last",
    )

    # Important facts
    facts: list[str] = Field(
        default_factory=list,
        description="Important facts about the user",
    )

    def to_memory_string(self, max_chars: int = 1500) -> str:
        """
        Serialize to compact memory format.

        Prioritizes recent and relevant information.
        """
        lines = []

        # User identity
        if self.name or self.role:
            identity = f"{self.name or 'Unknown'}"
            if self.role:
                identity += f" | {self.role}"
            lines.append(f"[USER] {identity}")

        # Current task and state
        if self.current_task:
            lines.append(f"[TASK] {self.current_task}")
            lines.append(f"[STATE] {self.session_state.value}")

        # Preferences (most important ones)
        if self.preferences:
            prefs = "; ".join(self.preferences[:4])
            lines.append(f"[PREFS] {prefs}")

        # Facts
        if self.facts:
            facts = "; ".join(self.facts[:3])
            lines.append(f"[FACTS] {facts}")

        # Recent context (last 3 notes)
        if self.context_notes:
            notes = "; ".join(self.context_notes[-3:])
            lines.append(f"[CONTEXT] {notes}")

        result = "\n".join(lines)
        return result[:max_chars]

    def add_context_note(self, note: str, max_notes: int = 10) -> None:
        """Add a context note, maintaining a rolling window."""
        self.context_notes.append(note)
        if len(self.context_notes) > max_notes:
            self.context_notes = self.context_notes[-max_notes:]

    def add_preference(self, preference: str) -> None:
        """Add a learned preference if not already present."""
        if preference not in self.preferences:
            self.preferences.append(preference)

    def add_fact(self, fact: str) -> None:
        """Add a fact about the user if not already present."""
        if fact not in self.facts:
            self.facts.append(fact)

    def set_task(self, task: str) -> None:
        """Set the current task and update state."""
        self.current_task = task
        self.session_state = SessionState.ACTIVE_TASK

    def clear_task(self) -> None:
        """Clear current task and return to idle."""
        self.current_task = None
        self.session_state = SessionState.IDLE

    @classmethod
    def from_memory_string(cls, memory_str: str) -> "HumanBlock":
        """Parse a memory string back into a HumanBlock (best effort)."""
        data: dict[str, Any] = {}

        for line in memory_str.strip().split("\n"):
            if line.startswith("[USER]"):
                parts = line.replace("[USER]", "").strip().split("|")
                if len(parts) >= 1:
                    name = parts[0].strip()
                    if name != "Unknown":
                        data["name"] = name
                if len(parts) >= 2:
                    data["role"] = parts[1].strip()
            elif line.startswith("[TASK]"):
                data["current_task"] = line.replace("[TASK]", "").strip()
            elif line.startswith("[STATE]"):
                state_str = line.replace("[STATE]", "").strip()
                with contextlib.suppress(ValueError):
                    data["session_state"] = SessionState(state_str)
            elif line.startswith("[PREFS]"):
                prefs = line.replace("[PREFS]", "").strip()
                data["preferences"] = [p.strip() for p in prefs.split(";")]
            elif line.startswith("[FACTS]"):
                facts = line.replace("[FACTS]", "").strip()
                data["facts"] = [f.strip() for f in facts.split(";")]
            elif line.startswith("[CONTEXT]"):
                ctx = line.replace("[CONTEXT]", "").strip()
                data["context_notes"] = [c.strip() for c in ctx.split(";")]

        return cls(**data)


# Pre-configured personas for common use cases
DEFAULT_PERSONA = PersonaBlock(
    name="Assistant",
    role="General-purpose AI assistant",
    capabilities=[
        "Answer questions",
        "Help with tasks",
        "Provide explanations",
        "Have conversations",
    ],
    tone="friendly",
    verbosity="adaptive",
)

CODING_ASSISTANT_PERSONA = PersonaBlock(
    name="CodeHelper",
    role="Software development assistant",
    capabilities=[
        "Write and review code",
        "Debug issues",
        "Explain technical concepts",
        "Suggest best practices",
    ],
    expertise=["Python", "JavaScript", "System design", "Testing"],
    tone="professional",
    verbosity="detailed",
    constraints=[
        "Always include error handling in code",
        "Prefer readability over cleverness",
    ],
)

RESEARCH_ASSISTANT_PERSONA = PersonaBlock(
    name="Researcher",
    role="Research and analysis assistant",
    capabilities=[
        "Synthesize information",
        "Compare options",
        "Identify patterns",
        "Summarize findings",
    ],
    expertise=["Research methodology", "Data analysis", "Critical thinking"],
    tone="professional",
    verbosity="detailed",
)
