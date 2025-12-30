"""Agent management for the HTTP service."""

from typing import Any

import structlog
from letta_client import Letta

from letta_starter.agents.templates import templates

log = structlog.get_logger()


class AgentManager:
    """Manages Letta agents for YouLab users."""

    def __init__(self, letta_base_url: str) -> None:
        self.letta_base_url = letta_base_url
        self._client = None
        # Cache: (user_id, agent_type) -> agent_id
        self._cache: dict[tuple[str, str], str] = {}

    @property
    def client(self) -> Any:
        """Lazy-initialize Letta client."""
        if self._client is None:
            self._client = Letta(base_url=self.letta_base_url)
        return self._client

    @client.setter
    def client(self, value: Any) -> None:
        """Set the Letta client (for testing)."""
        self._client = value

    def _agent_name(self, user_id: str, agent_type: str) -> str:
        """Generate agent name from user_id and type."""
        return f"youlab_{user_id}_{agent_type}"

    def _agent_metadata(self, user_id: str, agent_type: str) -> dict[str, str]:
        """Generate agent metadata."""
        return {
            "youlab_user_id": user_id,
            "youlab_agent_type": agent_type,
        }

    async def rebuild_cache(self) -> int:
        """Rebuild cache from Letta on startup. Returns count of agents found."""
        agents = self.client.list_agents()
        count = 0
        for agent in agents:
            if agent.name and agent.name.startswith("youlab_"):
                meta = agent.metadata or {}
                user_id = meta.get("youlab_user_id")
                agent_type = meta.get("youlab_agent_type", "tutor")
                if user_id:
                    self._cache[(user_id, agent_type)] = agent.id
                    count += 1
        log.info("rebuilt_agent_cache", count=count)
        return count

    def get_agent_id(self, user_id: str, agent_type: str = "tutor") -> str | None:
        """Get agent ID from cache, or lookup in Letta."""
        cache_key = (user_id, agent_type)

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Lookup in Letta by name
        agent_name = self._agent_name(user_id, agent_type)
        agents = self.client.list_agents()
        for agent in agents:
            if agent.name == agent_name:
                self._cache[cache_key] = agent.id
                return agent.id

        return None

    def create_agent(
        self,
        user_id: str,
        agent_type: str = "tutor",
        user_name: str | None = None,
    ) -> str:
        """Create a new agent from template. Returns agent_id."""
        # Check if already exists
        existing = self.get_agent_id(user_id, agent_type)
        if existing:
            log.info("agent_already_exists", user_id=user_id, agent_type=agent_type)
            return existing

        # Get template
        template = templates.get(agent_type)
        if template is None:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Create agent
        agent_name = self._agent_name(user_id, agent_type)
        metadata = self._agent_metadata(user_id, agent_type)

        # Customize human block with user name if provided
        human_block = template.human
        if user_name:
            human_block = template.human.model_copy()
            human_block.name = user_name

        agent = self.client.create_agent(
            name=agent_name,
            memory={
                "persona": template.persona.to_memory_string(),
                "human": human_block.to_memory_string(),
            },
            metadata=metadata,
        )

        # Update cache
        self._cache[(user_id, agent_type)] = agent.id
        log.info(
            "agent_created",
            agent_id=agent.id,
            user_id=user_id,
            agent_type=agent_type,
        )
        return agent.id

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent information by ID."""
        try:
            agent = self.client.get_agent(agent_id)
            meta = agent.metadata or {}
            return {
                "agent_id": agent.id,
                "user_id": meta.get("youlab_user_id", ""),
                "agent_type": meta.get("youlab_agent_type", "tutor"),
                "agent_name": agent.name,
                "created_at": getattr(agent, "created_at", None),
            }
        except Exception:
            return None

    def list_user_agents(self, user_id: str) -> list[dict[str, Any]]:
        """List all agents for a user."""
        results = []
        agents = self.client.list_agents()
        for agent in agents:
            meta = agent.metadata or {}
            if meta.get("youlab_user_id") == user_id:
                results.append(
                    {
                        "agent_id": agent.id,
                        "user_id": user_id,
                        "agent_type": meta.get("youlab_agent_type", "tutor"),
                        "agent_name": agent.name,
                        "created_at": getattr(agent, "created_at", None),
                    }
                )
        return results

    def send_message(self, agent_id: str, message: str) -> str:
        """Send a message to an agent. Returns response text."""
        response = self.client.send_message(
            agent_id=agent_id,
            message=message,
            role="user",
        )
        return self._extract_response(response)

    def _extract_response(self, response: Any) -> str:
        """Extract text from Letta response object."""
        texts = []
        if hasattr(response, "messages"):
            for msg in response.messages:
                if hasattr(msg, "assistant_message") and msg.assistant_message:
                    texts.append(msg.assistant_message)
                elif hasattr(msg, "text") and msg.text:
                    texts.append(msg.text)
        return "\n".join(texts) if texts else ""

    def check_letta_connection(self) -> bool:
        """Check if Letta server is reachable."""
        try:
            self.client.list_agents()
            return True
        except Exception:
            return False
