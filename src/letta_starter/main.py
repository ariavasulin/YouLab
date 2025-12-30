"""
LettaStarter - Main entry point.

This module provides:
- Application initialization
- CLI interface
- Example usage patterns
"""

import sys
import uuid
from typing import Any

import structlog

from letta_starter.config.settings import Settings, get_settings
from letta_starter.observability.logging import configure_logging
from letta_starter.observability.tracing import get_tracer, init_tracer


def initialize(settings: Settings | None = None) -> None:
    """
    Initialize the application.

    Sets up logging, tracing, and other infrastructure.

    Args:
        settings: Optional settings (default: load from environment)

    """
    if settings is None:
        settings = get_settings()

    # Configure logging
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json,
        service_name=settings.service_name,
    )

    # Initialize tracing
    init_tracer(
        langfuse_enabled=settings.langfuse_enabled,
        langfuse_public_key=settings.langfuse_public_key,
        langfuse_secret_key=settings.langfuse_secret_key,
        langfuse_host=settings.langfuse_host,
        service_name=settings.service_name,
    )

    logger = structlog.get_logger()
    logger.info(
        "application_initialized",
        log_level=settings.log_level,
        langfuse_enabled=settings.langfuse_enabled,
    )


def create_client(settings: Settings | None = None) -> Any:
    """
    Create a Letta client.

    Args:
        settings: Optional settings

    Returns:
        Configured Letta client

    """
    if settings is None:
        settings = get_settings()

    try:
        from letta import create_client as letta_create_client

        return letta_create_client(base_url=settings.letta_base_url)
    except ImportError as err:
        raise ImportError("letta package not installed. Run: uv add letta") from err


def interactive_session(agent_name: str = "default") -> None:
    """
    Run an interactive chat session with a Letta agent.

    Args:
        agent_name: Name of the agent to use

    """
    settings = get_settings()
    initialize(settings)

    logger = structlog.get_logger()
    tracer = get_tracer()

    try:
        client = create_client(settings)
    except Exception as e:
        print(f"Failed to connect to Letta: {e}")
        print(f"Make sure Letta server is running at: {settings.letta_base_url}")
        sys.exit(1)

    # Import here to avoid circular imports
    from letta_starter.agents.default import create_default_agent

    # Create or get agent
    try:
        agent = create_default_agent(client, name=agent_name, tracer=tracer)
    except Exception as e:
        logger.error("agent_creation_failed", error=str(e))
        print(f"Failed to create agent: {e}")
        sys.exit(1)

    # Start session
    session_id = str(uuid.uuid4())[:8]
    tracer.start_session(session_id)

    print("\nLettaStarter Interactive Session")
    print(f"Agent: {agent.name}")
    print(f"Session: {session_id}")
    print("-" * 40)
    print("Type 'quit' or 'exit' to end the session")
    print("Type '/memory' to see memory summary")
    print("Type '/search <query>' to search archival memory")
    print("-" * 40 + "\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit"):
                break

            if user_input == "/memory":
                summary = agent.get_memory_summary()
                print("\nMemory Summary:")
                for key, value in summary.items():
                    print(f"  {key}: {value}")
                print()
                continue

            if user_input.startswith("/search "):
                query = user_input[8:].strip()
                results = agent.search_memory(query)
                print(f"\nSearch results for '{query}':")
                if results:
                    for i, result in enumerate(results, 1):
                        print(f"  {i}. {result[:100]}...")
                else:
                    print("  No results found")
                print()
                continue

            # Send message to agent
            try:
                response = agent.send_message(user_input, session_id=session_id)
                print(f"\nAssistant: {response}\n")
            except Exception as e:
                logger.error("message_failed", error=str(e))
                print(f"\nError: {e}\n")

    except KeyboardInterrupt:
        print("\n")

    finally:
        tracer.end_session()
        print(f"\nSession {session_id} ended.")


def main() -> None:
    """Main entry point for CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="LettaStarter - Context-engineered Letta agents")
    parser.add_argument(
        "--agent",
        "-a",
        default="default",
        help="Agent name to use (default: default)",
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Output logs as JSON",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Override settings from CLI
    settings = get_settings()
    settings.log_json = args.json_logs
    settings.log_level = args.log_level

    interactive_session(agent_name=args.agent)


if __name__ == "__main__":
    main()
