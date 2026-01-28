"""
Background agent execution engine.

Note (ARI-85): Trigger system not implemented. Currently only executes when
manually called via POST /background/{task_name}/run.
- after_messages trigger: Run after N messages
- Cooldown enforcement: Track last_run_at per user per task

See: thoughts/shared/plans/2026-01-16-ARI-85-poc-course-background-agent.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from youlab_server.curriculum.schema import (
        BackgroundAgentConfig,
        DialecticQuery,
        TaskConfig,
    )
    from youlab_server.honcho.client import HonchoClient
    from youlab_server.storage.git import GitUserStorageManager

from youlab_server.background.factory import BackgroundAgentFactory
from youlab_server.honcho.client import SessionScope
from youlab_server.memory.enricher import MemoryEnricher, MergeStrategy
from youlab_server.storage.blocks import UserBlockManager

log = structlog.get_logger()


@dataclass
class QueryResult:
    """Result of a single query execution."""

    query_id: str
    user_id: str
    agent_id: str
    success: bool
    insight: str | None = None
    error: str | None = None


@dataclass
class RunResult:
    """Result of a background agent run."""

    agent_id: str
    started_at: datetime
    completed_at: datetime | None = None
    users_processed: int = 0
    queries_executed: int = 0
    enrichments_applied: int = 0
    errors: list[str] = field(default_factory=list)


class BackgroundAgentRunner:
    """Executes background agents based on configuration."""

    def __init__(
        self,
        letta_client: Any,
        honcho_client: HonchoClient | None,
        storage_manager: GitUserStorageManager | None = None,
    ) -> None:
        """
        Initialize the background agent runner.

        Args:
            letta_client: Letta client for agent operations
            honcho_client: Honcho client for dialectic queries
            storage_manager: Git storage manager for creating PendingDiffs

        """
        self.letta = letta_client
        self.honcho = honcho_client
        self.storage_manager = storage_manager
        self.enricher = MemoryEnricher(letta_client)  # Keep for fallback/legacy
        self.factory = BackgroundAgentFactory(letta_client)  # For agent-based execution
        self.logger = log.bind(component="background_runner")

    async def run_agent(
        self,
        config: BackgroundAgentConfig,
        user_ids: list[str] | None = None,
        agent_id: str = "unknown",
    ) -> RunResult:
        """
        Execute a background agent for specified users.

        Args:
            config: Background agent configuration
            user_ids: Specific users to process (None = all)
            agent_id: Agent identifier (from config key in curriculum)

        Returns:
            RunResult with execution details

        """
        result = RunResult(
            agent_id=agent_id,
            started_at=datetime.now(),
        )

        if not config.enabled:
            result.errors.append("Agent is disabled")
            result.completed_at = datetime.now()
            return result

        if self.honcho is None:
            result.errors.append("Honcho client not available")
            result.completed_at = datetime.now()
            return result

        # Get users to process
        target_users = user_ids or await self._get_target_users(config)

        self.logger.info(
            "background_agent_started",
            agent_id=agent_id,
            user_count=len(target_users),
            query_count=len(config.queries),
        )

        # Process users in batches
        for i in range(0, len(target_users), config.batch_size):
            batch = target_users[i : i + config.batch_size]

            for user_id in batch:
                await self._process_user(
                    config=config,
                    user_id=user_id,
                    result=result,
                    agent_id=agent_id,
                )

        result.completed_at = datetime.now()

        self.logger.info(
            "background_agent_completed",
            agent_id=agent_id,
            users_processed=result.users_processed,
            queries_executed=result.queries_executed,
            enrichments_applied=result.enrichments_applied,
            errors=len(result.errors),
        )

        return result

    async def run_task(
        self,
        config: TaskConfig,
        user_ids: list[str] | None = None,
        task_name: str = "unknown",
    ) -> RunResult:
        """
        Execute a v2 background task for specified users.

        If config has system + tools, uses agent-based execution.
        Otherwise falls back to query-based execution.

        Args:
            config: Task configuration (v2 format)
            user_ids: Specific users to process (None = all)
            task_name: Task name identifier

        Returns:
            RunResult with execution details

        """
        result = RunResult(
            agent_id=task_name,
            started_at=datetime.now(),
        )

        # Check if this is agent-based or query-based execution
        use_agent_execution = bool(config.system and config.tools)

        # Get users to process
        target_users = user_ids or await self._get_target_users_v2(config)

        self.logger.info(
            "background_task_started",
            task_name=task_name,
            user_count=len(target_users),
            execution_mode="agent" if use_agent_execution else "query",
            query_count=len(config.queries),
        )

        # Process users in batches
        for i in range(0, len(target_users), config.batch_size):
            batch = target_users[i : i + config.batch_size]

            for user_id in batch:
                if use_agent_execution:
                    await self._process_user_with_agent(
                        config=config,
                        user_id=user_id,
                        result=result,
                        task_name=task_name,
                    )
                else:
                    await self._process_user_with_queries(
                        config=config,
                        user_id=user_id,
                        result=result,
                        task_name=task_name,
                    )

        result.completed_at = datetime.now()

        self.logger.info(
            "background_task_completed",
            task_name=task_name,
            users_processed=result.users_processed,
            enrichments_applied=result.enrichments_applied,
            errors=len(result.errors),
        )

        return result

    async def _get_target_users_v2(
        self,
        config: TaskConfig,
    ) -> list[str]:
        """Get list of users to process based on v2 config."""
        users: list[str] = []

        for agent_type in config.agent_types:
            agents = self.letta.agents.list()
            for agent in agents:
                if agent.name and f"_{agent_type}" in agent.name:
                    parts = agent.name.split("_")
                    if len(parts) >= 3:  # noqa: PLR2004
                        user_id = parts[1]
                        if user_id not in users:
                            users.append(user_id)

        return users

    async def _process_user_with_agent(
        self,
        config: TaskConfig,
        user_id: str,
        result: RunResult,
        task_name: str,
    ) -> None:
        """Process a user using agent-based execution."""
        result.users_processed += 1

        try:
            # Get current memory blocks for the user
            memory_blocks = self._get_user_blocks(user_id)

            # Get or create background agent
            agent_id = self.factory.get_or_create_agent(
                task_name=task_name,
                user_id=user_id,
                system_prompt=config.system or "",
                tools=config.tools,
                memory_blocks=memory_blocks,
            )

            # Build instruction for the agent
            instruction = self._build_agent_instruction(config, memory_blocks)

            # Send instruction to agent
            self.logger.info(
                "background_agent_executing",
                task_name=task_name,
                user_id=user_id,
                agent_id=agent_id,
            )

            response = self.factory.send_instruction(
                agent_id=agent_id,
                instruction=instruction,
                user_id=user_id,
            )

            self.logger.info(
                "background_agent_response",
                task_name=task_name,
                user_id=user_id,
                response_length=len(response),
            )

            # Count as enrichment if agent successfully ran
            result.enrichments_applied += 1

        except Exception as e:
            self.logger.exception(
                "background_agent_failed",
                task_name=task_name,
                user_id=user_id,
                error=str(e),
            )
            result.errors.append(f"Agent execution failed for {user_id}: {e}")

    async def _process_user_with_queries(
        self,
        config: TaskConfig,
        user_id: str,
        result: RunResult,
        task_name: str,
    ) -> None:
        """Process a user using query-based execution (legacy/fallback)."""
        result.users_processed += 1

        if self.honcho is None:
            result.errors.append(f"Honcho unavailable for task {task_name}")
            return

        for query in config.queries:
            try:
                # Query Honcho
                scope = SessionScope(query.scope.value)
                response = await self.honcho.query_dialectic(
                    user_id=user_id,
                    question=query.question,
                    session_scope=scope,
                    recent_limit=query.recent_limit,
                )

                if response is None:
                    result.errors.append(f"Query failed for {user_id}: {query.target}")
                    continue

                result.queries_executed += 1

                # Create PendingDiff via UserBlockManager
                if self.storage_manager is not None:
                    user_storage = self.storage_manager.get(user_id)
                    block_manager = UserBlockManager(
                        user_id=user_id,
                        storage=user_storage,
                        letta_client=self.letta,
                    )

                    operation = "append" if query.merge == MergeStrategy.APPEND else "replace"
                    diff = block_manager.propose_edit(
                        agent_id=f"background:{task_name}",
                        block_label=query.target_block,
                        field=query.target_field,
                        operation=operation,
                        proposed_value=response.insight,
                        reasoning=f"Background insight: {query.question[:100]}",
                    )

                    self.logger.info(
                        "pending_diff_created",
                        user_id=user_id,
                        diff_id=diff.id,
                        block=query.target_block,
                        task_name=task_name,
                    )
                    result.enrichments_applied += 1

            except Exception as e:
                result.errors.append(f"Query failed for {user_id}/{query.target}: {e}")

    def _get_user_blocks(self, user_id: str) -> dict[str, str]:
        """Get current memory block contents for a user."""
        blocks: dict[str, str] = {}

        if self.storage_manager is None:
            return blocks

        try:
            user_storage = self.storage_manager.get(user_id)
            if not user_storage.exists:
                return blocks

            block_manager = UserBlockManager(
                user_id=user_id,
                storage=user_storage,
                letta_client=self.letta,
            )

            # List all blocks and read their content
            block_labels = block_manager.list_blocks()
            for label in block_labels:
                body = block_manager.get_block_body(label)
                if body:
                    blocks[label] = body

        except Exception as e:
            self.logger.warning(
                "failed_to_get_user_blocks",
                user_id=user_id,
                error=str(e),
            )

        return blocks

    def _build_agent_instruction(
        self,
        config: TaskConfig,
        memory_blocks: dict[str, str],
    ) -> str:
        """Build instruction message for background agent."""
        # Build context about available blocks
        max_preview_len = 200
        block_context = "\n".join(
            f"- {name}: {content[:max_preview_len]}..."
            if len(content) > max_preview_len
            else f"- {name}: {content}"
            for name, content in memory_blocks.items()
        )

        return f"""Analyze the conversation history and update memory blocks as needed.

**Current Memory Block Contents:**
{block_context if block_context else "(No blocks available)"}

**Your Task:**
1. Use query_honcho to understand recent conversation progress
2. Use edit_memory_block to propose updates to relevant blocks
3. Be concise - only add meaningful observations

You have tools available: query_honcho, edit_memory_block
Make tool calls as needed to complete your analysis."""

    async def _get_target_users(
        self,
        config: BackgroundAgentConfig,
    ) -> list[str]:
        """Get list of users to process based on config."""
        # Get all users with agents of specified types
        users: list[str] = []

        for agent_type in config.agent_types:
            # List agents matching pattern youlab_{user_id}_{agent_type}
            agents = self.letta.list_agents()
            for agent in agents:
                if agent.name and f"_{agent_type}" in agent.name:
                    # Extract user_id from agent name
                    parts = agent.name.split("_")
                    if len(parts) >= 3:  # noqa: PLR2004
                        user_id = parts[1]
                        if user_id not in users:
                            users.append(user_id)

        return users

    async def _process_user(
        self,
        config: BackgroundAgentConfig,
        user_id: str,
        result: RunResult,
        agent_id: str,
    ) -> None:
        """Process all queries for a single user."""
        result.users_processed += 1

        for query in config.queries:
            await self._execute_query(
                config=config,
                query=query,
                user_id=user_id,
                result=result,
                agent_id=agent_id,
            )

    async def _execute_query(
        self,
        config: BackgroundAgentConfig,
        query: DialecticQuery,
        user_id: str,
        result: RunResult,
        agent_id: str,
    ) -> None:
        """Execute a single query and apply enrichment."""
        result.queries_executed += 1

        if self.honcho is None:
            result.errors.append(f"Honcho unavailable for query {query.id}")
            return

        # Query Honcho dialectic
        scope = SessionScope(query.session_scope.value)
        response = await self.honcho.query_dialectic(
            user_id=user_id,
            question=query.question,
            session_scope=scope,
            recent_limit=query.recent_limit,
        )

        if response is None:
            result.errors.append(f"Dialectic query failed for user {user_id}: {query.id}")
            return

        # Find target agent
        target_agent_id = self._get_agent_id(user_id, config.agent_types[0])
        if not target_agent_id:
            result.errors.append(f"No agent found for user {user_id}")
            return

        # Use UserBlockManager to create PendingDiff (preferred path)
        if self.storage_manager is not None:
            try:
                user_storage = self.storage_manager.get(user_id)
                block_manager = UserBlockManager(
                    user_id=user_id,
                    storage=user_storage,
                    letta_client=self.letta,
                )

                # Map merge strategy to operation
                strategy = MergeStrategy(query.merge_strategy.value)
                operation = "append" if strategy == MergeStrategy.APPEND else "replace"

                diff = block_manager.propose_edit(
                    agent_id=f"background:{agent_id}",
                    block_label=query.target_block,
                    field=query.target_field,
                    operation=operation,
                    proposed_value=response.insight,
                    reasoning=f"Background agent insight: {query.question[:100]}",
                    confidence="medium",
                    source_query=query.question,
                )

                self.logger.info(
                    "pending_diff_created",
                    user_id=user_id,
                    diff_id=diff.id,
                    block=query.target_block,
                    agent_id=agent_id,
                )
                result.enrichments_applied += 1

            except Exception as e:
                result.errors.append(f"Failed to create pending diff for {user_id}/{query.id}: {e}")
        else:
            # Fallback to legacy MemoryEnricher (direct Letta updates, no git)
            strategy = MergeStrategy(query.merge_strategy.value)
            enrich_result = self.enricher.enrich(
                agent_id=target_agent_id,
                block=query.target_block,
                field=query.target_field,
                content=response.insight,
                strategy=strategy,
                source=f"background:{agent_id}",
                source_query=query.question,
            )

            if enrich_result.success:
                result.enrichments_applied += 1
            else:
                result.errors.append(
                    f"Enrichment failed for {user_id}/{query.id}: {enrich_result.message}"
                )

    def _get_agent_id(self, user_id: str, agent_type: str) -> str | None:
        """Look up agent ID for a user."""
        agent_name = f"youlab_{user_id}_{agent_type}"
        agents = self.letta.list_agents()
        for agent in agents:
            if agent.name == agent_name:
                return agent.id
        return None
