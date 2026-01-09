"""Agent management for the HTTP service."""

import json
from collections.abc import Iterator
from typing import Any

import structlog
from letta_client import Letta

from letta_starter.curriculum import curriculum

log = structlog.get_logger()


class AgentManager:
    """Manages Letta agents for YouLab users."""

    def __init__(self, letta_base_url: str) -> None:
        self.letta_base_url = letta_base_url
        self._client = None
        # Cache: (user_id, agent_type) -> agent_id
        self._cache: dict[tuple[str, str], str] = {}
        # Cache: (course_id, block_label) -> block_id for shared blocks
        self._shared_blocks: dict[tuple[str, str], str] = {}

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

    def _shared_block_name(self, course_id: str, block_label: str) -> str:
        """Generate unique name for a shared block."""
        return f"youlab_shared_{course_id}_{block_label}"

    def _get_or_create_shared_block(
        self,
        course_id: str,
        block_label: str,
        block_value: str,
        description: str = "",
    ) -> str:
        """
        Get or create a shared block for a course.

        Shared blocks are created once and reused across all agents
        using the same course. This enables cross-agent memory sharing.

        Args:
            course_id: Course identifier
            block_label: Block label (e.g., "team", "organization")
            block_value: Initial block content
            description: Block description

        Returns:
            Block ID

        """
        cache_key = (course_id, block_label)

        # Check cache first
        if cache_key in self._shared_blocks:
            return self._shared_blocks[cache_key]

        # Check if block exists in Letta
        block_name = self._shared_block_name(course_id, block_label)
        existing_blocks = self.client.blocks.list()
        for block in existing_blocks:
            if getattr(block, "name", None) == block_name:
                self._shared_blocks[cache_key] = block.id
                log.debug(
                    "shared_block_found",
                    course_id=course_id,
                    block_label=block_label,
                    block_id=block.id,
                )
                return block.id

        # Create new shared block
        block = self.client.blocks.create(
            label=block_label,
            value=block_value,
            name=block_name,
            description=description or f"Shared {block_label} block for {course_id}",
        )

        self._shared_blocks[cache_key] = block.id
        log.info(
            "shared_block_created",
            course_id=course_id,
            block_label=block_label,
            block_id=block.id,
        )

        return block.id

    async def rebuild_cache(self) -> int:
        """Rebuild cache from Letta on startup. Returns count of agents found."""
        agents = self.client.agents.list()
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
        agents = self.client.agents.list()
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
        """
        Create a new agent for a user.

        This method now delegates to create_agent_from_curriculum() using
        the "default" course configuration.

        Args:
            user_id: User identifier
            agent_type: Agent type (used as course_id, defaults to "default" for "tutor")
            user_name: Optional user name to set in human block

        Returns:
            Agent ID

        """
        # Map legacy "tutor" type to "default" course
        course_id = "default" if agent_type == "tutor" else agent_type

        return self.create_agent_from_curriculum(
            user_id=user_id,
            course_id=course_id,
            user_name=user_name,
        )

    def create_agent_from_curriculum(
        self,
        user_id: str,
        course_id: str,
        user_name: str | None = None,
        block_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """
        Create an agent based on curriculum configuration.

        Args:
            user_id: User identifier
            course_id: Course to use for agent configuration
            user_name: Optional user name to set in student/human block
            block_overrides: Optional field overrides per block

        Returns:
            Agent ID

        Raises:
            ValueError: If course not found

        """
        course = curriculum.get(course_id)
        if course is None:
            raise ValueError(f"Unknown course: {course_id}")

        # Use course_id as agent_type for caching
        agent_type = course_id
        agent_name = self._agent_name(user_id, agent_type)

        # Check for existing agent
        existing = self.get_agent_id(user_id, agent_type)
        if existing:
            log.info(
                "agent_already_exists",
                user_id=user_id,
                agent_type=agent_type,
                course_id=course_id,
            )
            return existing

        # Get block registry for this course
        block_registry = curriculum.get_block_registry(course_id)
        if block_registry is None:
            raise ValueError(f"Block registry not found for course: {course_id}")

        # Build memory blocks from course schema
        # Separate shared blocks (existing block_ids) from per-agent blocks
        overrides = block_overrides or {}
        memory_blocks = []
        shared_block_ids = []

        for block_name, block_schema in course.blocks.items():
            model_class = block_registry.get(block_name)
            if model_class is None:
                continue

            # Get block-specific overrides
            block_override = overrides.get(block_name, {})

            # Inject user name into human/student block
            if block_schema.label == "human" and user_name:
                block_override.setdefault("name", user_name)

            # Create instance with overrides
            instance = model_class(**block_override)
            block_value = instance.to_memory_string()

            if block_schema.shared:
                # Shared block: get or create once, attach via block_ids
                block_id = self._get_or_create_shared_block(
                    course_id=course_id,
                    block_label=block_schema.label,
                    block_value=block_value,
                    description=block_schema.description,
                )
                shared_block_ids.append(block_id)
            else:
                # Per-agent block: create fresh for this agent
                memory_blocks.append(
                    {
                        "label": block_schema.label,
                        "value": block_value,
                    }
                )

        # Build tool list
        tool_names = [tool.id for tool in course.agent.tools if tool.enabled]

        # Build tool rules
        tool_rules = []
        for tool in course.agent.tools:
            if tool.enabled and tool.rules:
                rule: dict[str, Any] = {
                    "tool_name": tool.id,
                    "type": tool.rules.type.value,
                }
                if tool.rules.max_count:
                    rule["max_count"] = tool.rules.max_count
                tool_rules.append(rule)

        # Create agent with curriculum config
        # Include block_ids for shared blocks (these are pre-existing blocks)
        agent = self.client.agents.create(
            name=agent_name,
            model=course.agent.model,
            embedding=course.agent.embedding,
            system=course.agent.system if course.agent.system else None,
            memory_blocks=memory_blocks if memory_blocks else None,
            block_ids=shared_block_ids if shared_block_ids else None,
            tools=tool_names if tool_names else None,
            tool_rules=tool_rules if tool_rules else None,
            metadata={
                **self._agent_metadata(user_id, agent_type),
                "course_id": course_id,
                "course_version": course.version,
            },
        )

        self._cache[(user_id, agent_type)] = agent.id

        log.info(
            "agent_created_from_curriculum",
            user_id=user_id,
            course_id=course_id,
            agent_id=agent.id,
            blocks=list(course.blocks.keys()),
            shared_blocks=len(shared_block_ids),
            tools=tool_names,
        )

        return agent.id

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent information by ID."""
        try:
            agent = self.client.agents.retrieve(agent_id)
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
        agents = self.client.agents.list()
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
        response = self.client.agents.messages.create(
            agent_id=agent_id,
            input=message,
        )
        return self._extract_response(response)

    def stream_message(
        self,
        agent_id: str,
        message: str,
        enable_thinking: bool = True,
    ) -> Iterator[str]:
        """
        Stream a message to an agent. Yields SSE-formatted events.

        Uses the Letta SDK's streaming API: client.agents.messages.stream()
        """
        try:
            # Note: enable_thinking is typed as `str | Omit` in the SDK.
            # The docstring says "If set to True, enables reasoning" but the
            # actual expected value format is unclear. Using string "true"/"false".
            # If this doesn't work, try passing the boolean directly.
            with self.client.agents.messages.stream(
                agent_id=agent_id,
                input=message,
                enable_thinking="true" if enable_thinking else "false",
                stream_tokens=False,
                include_pings=True,
            ) as stream:
                for chunk in stream:
                    event = self._chunk_to_sse_event(chunk)
                    if event:
                        yield event
        except Exception as e:
            log.exception("stream_message_failed", agent_id=agent_id, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    def _chunk_to_sse_event(self, chunk: Any) -> str | None:
        """
        Convert Letta streaming chunk to SSE event string.

        Handles these message types from LettaStreamingResponse:
        - reasoning_message: Agent's internal thinking
        - tool_call_message: Tool being invoked
        - assistant_message: Final response text
        - stop_reason: Stream complete
        - ping: Keep-alive
        - error_message: Error occurred

        Ignores (returns None):
        - tool_return_message: Tool execution results (internal)
        - usage_statistics: Token counts (internal)
        - hidden_reasoning_message: Hidden thinking (internal)
        - system_message, user_message: Echo of input (internal)
        """
        msg_type = getattr(chunk, "message_type", None)
        event_data: dict[str, Any] | None = None

        if msg_type == "reasoning_message":
            reasoning = getattr(chunk, "reasoning", "")
            event_data = {"type": "status", "content": "Thinking...", "reasoning": reasoning}
        elif msg_type == "tool_call_message":
            tool_call = getattr(chunk, "tool_call", None)
            tool_name = getattr(tool_call, "name", "tool") if tool_call else "tool"
            event_data = {"type": "status", "content": f"Using {tool_name}..."}
        elif msg_type == "assistant_message":
            # Note: content can be Union[str, List[ContentPart]] per SDK
            content = getattr(chunk, "content", "")
            if not isinstance(content, str):
                content = str(content)
            # Strip Letta metadata (follow_ups, title, tags) from content
            content = self._strip_letta_metadata(content)
            event_data = {"type": "message", "content": content}
        elif msg_type == "stop_reason":
            event_data = {"type": "done"}
        elif msg_type == "ping":
            return ": keepalive\n\n"
        elif msg_type == "error_message":
            error_msg = getattr(chunk, "message", "Unknown error")
            event_data = {"type": "error", "message": error_msg}

        # Intentionally ignore: tool_return_message, usage_statistics,
        # hidden_reasoning_message, system_message, user_message
        if event_data is None:
            return None
        return f"data: {json.dumps(event_data)}\n\n"

    def _strip_letta_metadata(self, content: str) -> str:
        """
        Strip Letta metadata (follow_ups, title, tags) from message content.

        Letta appends JSON objects like { "follow_ups": [...] }{ "title": "..." }
        to the end of messages. This strips them to show only the actual message.
        """
        if not content:
            return content

        # Find the first { that starts a JSON object at the end
        # Work backwards to find where the actual message ends
        result = content
        while result:
            # Find the last { in the string
            last_brace = result.rfind("{")
            if last_brace == -1:
                break

            # Check if everything after this brace looks like JSON metadata
            potential_json = result[last_brace:]
            try:
                parsed = json.loads(potential_json)
                # If it's a dict with known metadata keys, strip it
                if isinstance(parsed, dict) and any(
                    k in parsed for k in ("follow_ups", "title", "tags")
                ):
                    result = result[:last_brace].rstrip()
                else:
                    break
            except json.JSONDecodeError:
                break

        return result

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
            self.client.agents.list()
            return True
        except Exception:
            return False
