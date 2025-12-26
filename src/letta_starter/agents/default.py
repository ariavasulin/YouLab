"""
Default agent configuration and factory functions.

Provides pre-configured agents for common use cases.
"""

from typing import Any

from letta_starter.agents.base import BaseAgent
from letta_starter.memory.blocks import (
    CODING_ASSISTANT_PERSONA,
    DEFAULT_PERSONA,
    RESEARCH_ASSISTANT_PERSONA,
    HumanBlock,
    PersonaBlock,
)
from letta_starter.observability.tracing import Tracer


def create_default_agent(
    client: Any,
    name: str = "default",
    tracer: Tracer | None = None,
) -> BaseAgent:
    """
    Create a default general-purpose agent.

    Args:
        client: Letta client
        name: Agent name
        tracer: Optional tracer

    Returns:
        Configured BaseAgent
    """
    return BaseAgent(
        name=name,
        persona=DEFAULT_PERSONA,
        human=HumanBlock(),
        client=client,
        tracer=tracer,
    )


def create_coding_agent(
    client: Any,
    name: str = "coder",
    tracer: Tracer | None = None,
) -> BaseAgent:
    """
    Create a coding assistant agent.

    Args:
        client: Letta client
        name: Agent name
        tracer: Optional tracer

    Returns:
        Configured BaseAgent for coding tasks
    """
    return BaseAgent(
        name=name,
        persona=CODING_ASSISTANT_PERSONA,
        human=HumanBlock(
            preferences=["Type hints in code", "Detailed explanations"],
        ),
        client=client,
        tracer=tracer,
    )


def create_research_agent(
    client: Any,
    name: str = "researcher",
    tracer: Tracer | None = None,
) -> BaseAgent:
    """
    Create a research assistant agent.

    Args:
        client: Letta client
        name: Agent name
        tracer: Optional tracer

    Returns:
        Configured BaseAgent for research tasks
    """
    return BaseAgent(
        name=name,
        persona=RESEARCH_ASSISTANT_PERSONA,
        human=HumanBlock(
            preferences=["Thorough analysis", "Cited sources"],
        ),
        client=client,
        tracer=tracer,
    )


def create_custom_agent(
    client: Any,
    name: str,
    role: str,
    capabilities: list[str],
    expertise: list[str] | None = None,
    tone: str = "professional",
    verbosity: str = "concise",
    constraints: list[str] | None = None,
    user_name: str | None = None,
    user_role: str | None = None,
    tracer: Tracer | None = None,
) -> BaseAgent:
    """
    Create a custom agent with specified configuration.

    Args:
        client: Letta client
        name: Agent name
        role: Agent's primary role
        capabilities: List of agent capabilities
        expertise: Optional areas of expertise
        tone: Communication tone
        verbosity: Response verbosity
        constraints: Behavioral constraints
        user_name: Optional user name
        user_role: Optional user role
        tracer: Optional tracer

    Returns:
        Custom configured BaseAgent
    """
    persona = PersonaBlock(
        name=name.title(),
        role=role,
        capabilities=capabilities,
        expertise=expertise or [],
        tone=tone,
        verbosity=verbosity,
        constraints=constraints or [],
    )

    human = HumanBlock(
        name=user_name,
        role=user_role,
    )

    return BaseAgent(
        name=name,
        persona=persona,
        human=human,
        client=client,
        tracer=tracer,
    )


# Agent registry for managing multiple agents
class AgentRegistry:
    """
    Registry for managing multiple agents.

    Useful for multi-agent systems where you need to
    coordinate between different specialized agents.
    """

    def __init__(self, client: Any, tracer: Tracer | None = None):
        """
        Initialize the registry.

        Args:
            client: Letta client (shared by all agents)
            tracer: Optional tracer (shared by all agents)
        """
        self.client = client
        self.tracer = tracer
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """
        Register an agent.

        Args:
            agent: Agent to register
        """
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent if found, None otherwise
        """
        return self._agents.get(name)

    def create_and_register(
        self,
        name: str,
        agent_type: str = "default",
        **kwargs: Any,
    ) -> BaseAgent:
        """
        Create and register an agent.

        Args:
            name: Agent name
            agent_type: Type of agent (default, coding, research)
            **kwargs: Additional arguments for agent creation

        Returns:
            Created and registered agent
        """
        factories = {
            "default": create_default_agent,
            "coding": create_coding_agent,
            "research": create_research_agent,
        }

        factory = factories.get(agent_type, create_default_agent)
        agent = factory(
            client=self.client,
            name=name,
            tracer=self.tracer,
            **kwargs,
        )

        self.register(agent)
        return agent

    def list_agents(self) -> list[str]:
        """Get list of registered agent names."""
        return list(self._agents.keys())

    def remove(self, name: str) -> BaseAgent | None:
        """
        Remove an agent from the registry.

        Args:
            name: Agent name

        Returns:
            Removed agent if found
        """
        return self._agents.pop(name, None)

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents
