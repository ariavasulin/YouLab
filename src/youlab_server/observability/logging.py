"""
Structured logging configuration using structlog.

Provides consistent, parseable JSON logging that integrates well with
log aggregation systems (ELK, CloudWatch, Datadog, etc.).
"""

import logging
import sys
from collections.abc import Callable
from typing import Any, cast

import structlog


def add_service_context(
    service_name: str,
) -> Callable[[Any, str, dict[str, Any]], dict[str, Any]]:
    """Create a processor that adds service context to all log entries."""

    def processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        event_dict["service"] = service_name
        return event_dict

    return processor


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    service_name: str = "youlab",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON logs (for production).
                    If False, output pretty console logs (for development).
        service_name: Service name to include in all log entries

    """
    # Base processors that run for all log entries
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_service_context(service_name),
    ]

    # Output format based on environment
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to match
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level),
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (optional, used for context)

    Returns:
        Bound structlog logger

    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger_name=name)
    return cast("structlog.BoundLogger", logger)


# Convenience functions for common log patterns
def log_llm_call(
    logger: structlog.BoundLogger,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    cost_usd: float = 0.0,
    success: bool = True,
    error: str | None = None,
    **extra: Any,
) -> None:
    """
    Log an LLM call with standard fields.

    Args:
        logger: Logger instance
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        latency_ms: Latency in milliseconds
        cost_usd: Estimated cost in USD
        success: Whether the call succeeded
        error: Error message if failed
        **extra: Additional fields to log

    """
    logger.info(
        "llm_call",
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=round(latency_ms, 2),
        cost_usd=round(cost_usd, 6),
        success=success,
        error=error,
        **extra,
    )


def log_agent_message(
    logger: structlog.BoundLogger,
    agent_name: str,
    direction: str,  # "inbound" or "outbound"
    message_length: int,
    session_id: str | None = None,
    **extra: Any,
) -> None:
    """
    Log an agent message.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        direction: "inbound" (user->agent) or "outbound" (agent->user)
        message_length: Length of the message
        session_id: Session identifier
        **extra: Additional fields to log

    """
    logger.info(
        "agent_message",
        agent=agent_name,
        direction=direction,
        message_length=message_length,
        session_id=session_id,
        **extra,
    )


def log_memory_operation(
    logger: structlog.BoundLogger,
    operation: str,  # "read", "write", "rotate", "archive"
    block_type: str,  # "persona", "human", "archival"
    chars: int,
    agent_id: str,
    **extra: Any,
) -> None:
    """
    Log a memory operation.

    Args:
        logger: Logger instance
        operation: Type of operation
        block_type: Memory block type
        chars: Characters involved
        agent_id: Agent ID
        **extra: Additional fields to log

    """
    logger.info(
        "memory_operation",
        operation=operation,
        block_type=block_type,
        chars=chars,
        agent_id=agent_id,
        **extra,
    )
