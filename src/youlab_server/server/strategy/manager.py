"""Strategy agent manager for RAG-enabled project knowledge."""

from typing import Any

import structlog
from letta_client import Letta

log = structlog.get_logger()

# Strategy agent persona - instructs agent to search archival memory
STRATEGY_PERSONA = """You are a YouLab project strategist with comprehensive knowledge stored in your archival memory.

CRITICAL: Before answering ANY question about YouLab:
1. Use archival_memory_search to find relevant documentation
2. Cite the sources you found in your response
3. If no relevant documents found, say so explicitly

Your archival memory contains:
- Architecture documentation
- Roadmap and phase plans
- Design decisions and rationale
- Technical specifications

Be concise, accurate, and always reference your archival knowledge."""

STRATEGY_HUMAN = """Developer seeking project information and strategic guidance."""


class StrategyManager:
    """
    Manages a singleton strategy agent with RAG capabilities.

    Unlike AgentManager which creates per-user agents, StrategyManager
    maintains a single shared agent for project-wide knowledge queries.
    """

    AGENT_NAME = "YouLab-Support"

    def __init__(self, letta_base_url: str) -> None:
        """
        Initialize the strategy manager.

        Args:
            letta_base_url: URL of the Letta server.

        """
        self.letta_base_url = letta_base_url
        self._client: Letta | None = None
        self._agent_id: str | None = None

    @property
    def client(self) -> Letta:
        """Lazy-initialize Letta client."""
        if self._client is None:
            self._client = Letta(base_url=self.letta_base_url)
        return self._client

    @client.setter
    def client(self, value: Any) -> None:
        """Set the Letta client (for testing)."""
        self._client = value

    def _find_existing_agent(self) -> str | None:
        """
        Find existing strategy agent if one exists.

        Returns:
            Agent ID if found, None otherwise.

        """
        for agent in self.client.list_agents():
            if agent.name == self.AGENT_NAME:
                return agent.id
        return None

    def ensure_agent(self) -> str:
        """
        Get or create the singleton strategy agent.

        Returns:
            The agent ID.

        """
        # Return cached agent_id if available
        if self._agent_id is not None:
            return self._agent_id

        # Look for existing agent
        existing_id = self._find_existing_agent()
        if existing_id is not None:
            self._agent_id = existing_id
            log.info("strategy_agent_found", agent_id=existing_id)
            return existing_id

        # Create new agent
        agent = self.client.create_agent(
            name=self.AGENT_NAME,
            memory={
                "persona": STRATEGY_PERSONA,
                "human": STRATEGY_HUMAN,
            },
        )
        self._agent_id = agent.id
        log.info("strategy_agent_created", agent_id=agent.id)
        return agent.id

    def upload_document(self, content: str, tags: list[str] | None = None) -> None:
        """
        Upload content to the strategy agent's archival memory.

        Args:
            content: The document content to store.
            tags: Optional tags for categorization.

        """
        agent_id = self.ensure_agent()
        tags = tags or []

        # Format content with tags for searchability
        if tags:
            tag_str = ", ".join(tags)
            memory = f"[TAGS: {tag_str}]\n{content}"
        else:
            memory = content

        self.client.insert_archival_memory(
            agent_id=agent_id,
            memory=memory,
        )
        log.info(
            "document_uploaded",
            agent_id=agent_id,
            content_length=len(content),
            tags=tags,
        )

    def ask(self, question: str) -> str:
        """
        Ask the strategy agent a question.

        The agent will search its archival memory for relevant context
        before responding.

        Args:
            question: The question to ask.

        Returns:
            The agent's response text.

        """
        agent_id = self.ensure_agent()

        response = self.client.send_message(
            agent_id=agent_id,
            message=question,
            role="user",
        )

        return self._extract_response(response)

    def search_documents(self, query: str, limit: int = 5) -> list[str]:
        """
        Search the strategy agent's archival memory.

        Args:
            query: Search query string.
            limit: Maximum number of results.

        Returns:
            List of matching document texts.

        """
        agent_id = self.ensure_agent()

        results = self.client.get_archival_memory(
            agent_id=agent_id,
            query=query,
            limit=limit,
        )

        if not results:
            return []

        return [r.text for r in results]

    def check_agent_exists(self) -> bool:
        """
        Check if the strategy agent exists.

        Returns:
            True if the agent exists, False otherwise.

        """
        return self._find_existing_agent() is not None

    def _extract_response(self, response: Any) -> str:
        """
        Extract text from Letta response object.

        Args:
            response: The response from send_message.

        Returns:
            Extracted text content.

        """
        if not hasattr(response, "messages"):
            return ""

        texts = []
        for msg in response.messages:
            if hasattr(msg, "assistant_message") and msg.assistant_message:
                texts.append(msg.assistant_message)
            elif hasattr(msg, "text") and msg.text:
                texts.append(msg.text)

        return "\n".join(texts) if texts else ""
