"""
Memory management strategies for context optimization.

These strategies determine when and how to rotate context from
core memory to archival memory, optimizing the context window usage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ContextMetrics:
    """Metrics about current memory usage."""

    persona_chars: int
    human_chars: int
    persona_max: int
    human_max: int

    @property
    def persona_usage(self) -> float:
        """Persona block usage as percentage (0-1)."""
        return self.persona_chars / self.persona_max if self.persona_max > 0 else 0

    @property
    def human_usage(self) -> float:
        """Human block usage as percentage (0-1)."""
        return self.human_chars / self.human_max if self.human_max > 0 else 0

    @property
    def total_chars(self) -> int:
        """Total characters in core memory."""
        return self.persona_chars + self.human_chars

    @property
    def total_max(self) -> int:
        """Maximum total characters allowed."""
        return self.persona_max + self.human_max

    @property
    def total_usage(self) -> float:
        """Total usage as percentage (0-1)."""
        return self.total_chars / self.total_max if self.total_max > 0 else 0


class ContextStrategy(Protocol):
    """
    Protocol for context management strategies.

    Strategies implement policies for:
    - When to rotate context to archival
    - How to compress content when needed
    - What to prioritize keeping in core memory
    """

    def should_rotate(self, metrics: ContextMetrics) -> bool:
        """
        Determine if context should be rotated to archival.

        Returns True if the current context should be moved to
        archival memory to free up space in core memory.
        """
        ...

    def compress(self, content: str, target_chars: int) -> str:
        """
        Compress content while preserving semantics.

        Args:
            content: The content to compress
            target_chars: Target character count

        Returns:
            Compressed content
        """
        ...


class AggressiveRotation:
    """
    Rotate frequently to keep core memory lean.

    Best for:
    - Long-running sessions
    - Many short tasks
    - When archival search is fast
    """

    threshold: float = 0.7  # Rotate at 70% capacity

    def should_rotate(self, metrics: ContextMetrics) -> bool:
        """Rotate when human block exceeds threshold."""
        return metrics.human_usage > self.threshold

    def compress(self, content: str, target_chars: int) -> str:
        """Aggressively truncate to target length."""
        if len(content) <= target_chars:
            return content

        # Keep the most recent content (end of string)
        return "..." + content[-(target_chars - 3) :]


class PreservativeRotation:
    """
    Preserve more in core, rotate only when necessary.

    Best for:
    - Complex multi-step tasks
    - When context continuity is critical
    - Shorter sessions
    """

    threshold: float = 0.9  # Rotate at 90% capacity

    def should_rotate(self, metrics: ContextMetrics) -> bool:
        """Rotate only when approaching capacity."""
        return metrics.human_usage > self.threshold

    def compress(self, content: str, target_chars: int) -> str:
        """Preserve structure while reducing length."""
        if len(content) <= target_chars:
            return content

        lines = content.split("\n")
        result_lines = []
        current_chars = 0

        # Prioritize lines with markers (structured content)
        priority_lines = [l for l in lines if l.startswith("[")]
        other_lines = [l for l in lines if not l.startswith("[")]

        # Add priority lines first
        for line in priority_lines:
            if current_chars + len(line) + 1 <= target_chars:
                result_lines.append(line)
                current_chars += len(line) + 1

        # Add other lines if space remains
        for line in other_lines:
            if current_chars + len(line) + 1 <= target_chars:
                result_lines.append(line)
                current_chars += len(line) + 1

        return "\n".join(result_lines)


class AdaptiveRotation:
    """
    Adapt rotation based on session dynamics.

    Learns from usage patterns to optimize rotation timing.
    """

    base_threshold: float = 0.8
    recent_rotations: list[float] = []

    def __init__(self):
        self.recent_rotations = []

    def should_rotate(self, metrics: ContextMetrics) -> bool:
        """
        Adapt threshold based on recent rotation frequency.

        If rotating too often, increase threshold.
        If rarely rotating, decrease threshold.
        """
        # Start with base threshold
        threshold = self.base_threshold

        # Adjust based on recent rotation history
        if len(self.recent_rotations) >= 5:
            avg_interval = sum(self.recent_rotations[-5:]) / 5
            if avg_interval < 0.5:  # Rotating too often
                threshold = min(0.95, threshold + 0.05)
            elif avg_interval > 0.9:  # Rarely rotating
                threshold = max(0.6, threshold - 0.05)

        return metrics.human_usage > threshold

    def record_rotation(self, usage_at_rotation: float) -> None:
        """Record a rotation event for adaptive learning."""
        self.recent_rotations.append(usage_at_rotation)
        # Keep only last 20 rotations
        if len(self.recent_rotations) > 20:
            self.recent_rotations = self.recent_rotations[-20:]

    def compress(self, content: str, target_chars: int) -> str:
        """Balanced compression preserving key information."""
        if len(content) <= target_chars:
            return content

        lines = content.split("\n")

        # Score lines by importance
        scored_lines = []
        for line in lines:
            score = 0
            if line.startswith("[TASK]"):
                score = 100  # Current task is critical
            elif line.startswith("[USER]"):
                score = 90  # User identity is important
            elif line.startswith("[CONTEXT]"):
                score = 80  # Recent context matters
            elif line.startswith("["):
                score = 50  # Other structured content
            else:
                score = 10  # Unstructured content

            scored_lines.append((score, line))

        # Sort by score (highest first) and rebuild
        scored_lines.sort(key=lambda x: -x[0])

        result_lines = []
        current_chars = 0

        for _, line in scored_lines:
            if current_chars + len(line) + 1 <= target_chars:
                result_lines.append(line)
                current_chars += len(line) + 1

        return "\n".join(result_lines)


# Default strategy
DEFAULT_STRATEGY = AdaptiveRotation()
