"""
Metrics collection for LLM usage tracking.

Provides lightweight, in-process metrics that can be exported
or used for monitoring without external dependencies.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime

import structlog

logger = structlog.get_logger()


@dataclass
class LLMCallRecord:
    """Record of a single LLM call."""

    timestamp: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    success: bool
    error: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class SessionMetrics:
    """Aggregated metrics for a session."""

    session_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    calls: list[LLMCallRecord] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def successful_calls(self) -> int:
        return sum(1 for c in self.calls if c.success)

    @property
    def failed_calls(self) -> int:
        return sum(1 for c in self.calls if not c.success)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def avg_latency_ms(self) -> float:
        if not self.calls:
            return 0
        return sum(c.latency_ms for c in self.calls) / len(self.calls)

    @property
    def error_rate(self) -> float:
        if not self.calls:
            return 0
        return self.failed_calls / len(self.calls)

    def to_dict(self) -> dict[str, object]:
        """Export metrics as dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "error_rate": round(self.error_rate, 4),
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


class MetricsCollector:
    """
    Collects and manages metrics across sessions.

    Provides:
    - Session-scoped metrics tracking
    - Aggregated statistics
    - Cost estimation
    - Export capabilities
    """

    # Approximate cost per 1K tokens by model (as of late 2024)
    MODEL_COSTS: dict[str, dict[str, float]] = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        "claude-3.5-sonnet": {"input": 0.003, "output": 0.015},
    }

    def __init__(self) -> None:
        self.sessions: dict[str, SessionMetrics] = {}
        self.current_session: SessionMetrics | None = None
        self._all_time_calls: list[LLMCallRecord] = []

    def start_session(self, session_id: str) -> SessionMetrics:
        """
        Start a new metrics session.

        Args:
            session_id: Unique session identifier

        Returns:
            New SessionMetrics instance
        """
        session = SessionMetrics(session_id=session_id)
        self.sessions[session_id] = session
        self.current_session = session

        logger.info("metrics_session_started", session_id=session_id)
        return session

    def end_session(self, session_id: str | None = None) -> SessionMetrics | None:
        """
        End a metrics session.

        Args:
            session_id: Session to end (default: current session)

        Returns:
            The ended session metrics
        """
        session = self.sessions.get(session_id) if session_id else self.current_session

        if session:
            session.end_time = time.time()
            logger.info(
                "metrics_session_ended",
                session_id=session.session_id,
                **session.to_dict(),
            )

            if session == self.current_session:
                self.current_session = None

        return session

    def record_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        success: bool = True,
        error: str | None = None,
        session_id: str | None = None,
    ) -> LLMCallRecord:
        """
        Record an LLM call.

        Args:
            model: Model name
            prompt_tokens: Prompt token count
            completion_tokens: Completion token count
            latency_ms: Call latency in ms
            success: Whether call succeeded
            error: Error message if failed
            session_id: Session to record to (default: current)

        Returns:
            The recorded call
        """
        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)

        record = LLMCallRecord(
            timestamp=time.time(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost,
            success=success,
            error=error,
        )

        # Add to session
        session = None
        if session_id:
            session = self.sessions.get(session_id)
        elif self.current_session:
            session = self.current_session

        if session:
            session.calls.append(record)

        # Always track in all-time
        self._all_time_calls.append(record)

        return record

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for an LLM call."""
        # Find matching model costs
        model_lower = model.lower()
        costs = None

        for model_name, model_costs in self.MODEL_COSTS.items():
            if model_name in model_lower:
                costs = model_costs
                break

        if not costs:
            # Default fallback (GPT-4 prices as conservative estimate)
            costs = {"input": 0.03, "output": 0.06}

        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (completion_tokens / 1000) * costs["output"]

        return input_cost + output_cost

    def get_session(self, session_id: str) -> SessionMetrics | None:
        """Get metrics for a specific session."""
        return self.sessions.get(session_id)

    def get_current_session(self) -> SessionMetrics | None:
        """Get current session metrics."""
        return self.current_session

    def get_all_time_stats(self) -> dict[str, object]:
        """Get all-time aggregated statistics."""
        if not self._all_time_calls:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
            }

        total_tokens = sum(c.total_tokens for c in self._all_time_calls)
        total_cost = sum(c.cost_usd for c in self._all_time_calls)
        failed = sum(1 for c in self._all_time_calls if not c.success)

        return {
            "total_calls": len(self._all_time_calls),
            "total_sessions": len(self.sessions),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "failed_calls": failed,
            "error_rate": round(failed / len(self._all_time_calls), 4),
            "avg_latency_ms": round(
                sum(c.latency_ms for c in self._all_time_calls) / len(self._all_time_calls),
                2,
            ),
        }


# Global collector instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
