"""
LLM call tracing with optional Langfuse integration.

Provides a simple, consistent interface for tracing LLM calls
that works standalone or with external tracing backends.
"""

import contextlib
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import structlog

from letta_starter.observability.metrics import get_metrics_collector

logger = structlog.get_logger()


@dataclass
class LLMCallMetrics:
    """
    Mutable metrics object for tracking a single LLM call.

    Used within trace_llm_call context manager to accumulate metrics.
    """

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0
    cost_usd: float = 0
    success: bool = True
    error: str | None = None

    # Additional metadata
    agent_name: str | None = None
    session_id: str | None = None


class Tracer:
    """
    LLM call tracer with optional Langfuse integration.

    Provides:
    - Context manager for tracing LLM calls
    - Automatic metrics collection
    - Optional Langfuse integration for production tracing
    """

    def __init__(
        self,
        langfuse_client: Any | None = None,
        service_name: str = "letta-starter",
    ):
        """
        Initialize the tracer.

        Args:
            langfuse_client: Optional Langfuse client for external tracing
            service_name: Service name for trace metadata
        """
        self.langfuse = langfuse_client
        self.service_name = service_name
        self._current_trace: Any | None = None
        self._current_session_id: str | None = None
        self.logger = logger.bind(component="tracer")

    def start_session(self, session_id: str, user_id: str | None = None) -> None:
        """
        Start a new tracing session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
        """
        self._current_session_id = session_id

        # Start metrics session
        collector = get_metrics_collector()
        collector.start_session(session_id)

        # Start Langfuse trace if available
        if self.langfuse:
            try:
                self._current_trace = self.langfuse.trace(
                    name=f"session-{session_id}",
                    session_id=session_id,
                    user_id=user_id,
                    metadata={"service": self.service_name},
                )
            except Exception as e:
                self.logger.warning("langfuse_trace_failed", error=str(e))

        self.logger.info(
            "tracing_session_started",
            session_id=session_id,
            user_id=user_id,
        )

    def end_session(self) -> None:
        """End the current tracing session."""
        if not self._current_session_id:
            return

        # End metrics session
        collector = get_metrics_collector()
        session = collector.end_session(self._current_session_id)

        if session:
            self.logger.info(
                "tracing_session_ended",
                session_id=self._current_session_id,
                total_calls=session.total_calls,
                total_tokens=session.total_tokens,
                total_cost_usd=round(session.total_cost_usd, 6),
            )

        # Flush Langfuse if available
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception as e:
                self.logger.warning("langfuse_flush_failed", error=str(e))

        self._current_trace = None
        self._current_session_id = None

    @contextmanager
    def trace_llm_call(
        self,
        model: str,
        agent_name: str = "default",
        operation: str = "chat",
    ) -> Generator[LLMCallMetrics, None, None]:
        """
        Context manager for tracing an LLM call.

        Usage:
            with tracer.trace_llm_call("gpt-4", "my_agent") as metrics:
                response = make_llm_call(...)
                metrics.prompt_tokens = response.usage.prompt_tokens
                metrics.completion_tokens = response.usage.completion_tokens

        Args:
            model: Model name being called
            agent_name: Name of the agent making the call
            operation: Operation type (chat, completion, embedding)

        Yields:
            LLMCallMetrics object to populate with results
        """
        metrics = LLMCallMetrics(
            model=model,
            agent_name=agent_name,
            session_id=self._current_session_id,
        )

        start_time = time.time()

        # Start Langfuse generation if available
        generation = None
        if self.langfuse and self._current_trace:
            with contextlib.suppress(Exception):
                generation = self._current_trace.generation(
                    name=f"{agent_name}-{operation}",
                    model=model,
                    metadata={"agent": agent_name, "operation": operation},
                )

        try:
            yield metrics
            metrics.success = True
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            raise
        finally:
            metrics.latency_ms = (time.time() - start_time) * 1000

            # Record to metrics collector
            collector = get_metrics_collector()
            record = collector.record_call(
                model=model,
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                latency_ms=metrics.latency_ms,
                success=metrics.success,
                error=metrics.error,
                session_id=self._current_session_id,
            )
            metrics.cost_usd = record.cost_usd

            # Complete Langfuse generation
            if generation:
                with contextlib.suppress(Exception):
                    generation.end(
                        usage={
                            "prompt_tokens": metrics.prompt_tokens,
                            "completion_tokens": metrics.completion_tokens,
                            "total_tokens": metrics.prompt_tokens + metrics.completion_tokens,
                        },
                        metadata={
                            "latency_ms": metrics.latency_ms,
                            "success": metrics.success,
                            "error": metrics.error,
                        },
                    )

            # Log the call
            self.logger.info(
                "llm_call_traced",
                model=model,
                agent=agent_name,
                operation=operation,
                prompt_tokens=metrics.prompt_tokens,
                completion_tokens=metrics.completion_tokens,
                latency_ms=round(metrics.latency_ms, 2),
                cost_usd=round(metrics.cost_usd, 6),
                success=metrics.success,
                error=metrics.error,
                session_id=self._current_session_id,
            )

    def trace_memory_operation(
        self,
        operation: str,
        block_type: str,
        chars: int,
        agent_id: str,
    ) -> None:
        """
        Trace a memory operation.

        Args:
            operation: Operation type (read, write, rotate, archive)
            block_type: Memory block type (persona, human, archival)
            chars: Characters involved
            agent_id: Agent ID
        """
        self.logger.info(
            "memory_operation_traced",
            operation=operation,
            block_type=block_type,
            chars=chars,
            agent_id=agent_id,
            session_id=self._current_session_id,
        )

        # Add to Langfuse span if available
        if self.langfuse and self._current_trace:
            with contextlib.suppress(Exception):
                self._current_trace.span(
                    name=f"memory-{operation}",
                    metadata={
                        "block_type": block_type,
                        "chars": chars,
                        "agent_id": agent_id,
                    },
                )


# Global tracer instance
_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def init_tracer(
    langfuse_enabled: bool = False,
    langfuse_public_key: str | None = None,
    langfuse_secret_key: str | None = None,
    langfuse_host: str = "https://cloud.langfuse.com",
    service_name: str = "letta-starter",
) -> Tracer:
    """
    Initialize the global tracer with configuration.

    Args:
        langfuse_enabled: Whether to enable Langfuse
        langfuse_public_key: Langfuse public key
        langfuse_secret_key: Langfuse secret key
        langfuse_host: Langfuse host URL
        service_name: Service name for traces

    Returns:
        Configured Tracer instance
    """
    global _tracer

    langfuse_client = None
    if langfuse_enabled and langfuse_public_key and langfuse_secret_key:
        try:
            from langfuse import Langfuse

            langfuse_client = Langfuse(
                public_key=langfuse_public_key,
                secret_key=langfuse_secret_key,
                host=langfuse_host,
            )
            logger.info("langfuse_initialized", host=langfuse_host)
        except ImportError:
            logger.warning("langfuse_not_installed")
        except Exception as e:
            logger.error("langfuse_init_failed", error=str(e))

    _tracer = Tracer(langfuse_client=langfuse_client, service_name=service_name)
    return _tracer
