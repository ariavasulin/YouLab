"""Background agent execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from letta_starter.background.schema import BackgroundAgentConfig, DialecticQuery
    from letta_starter.honcho.client import HonchoClient

from letta_starter.honcho.client import SessionScope
from letta_starter.memory.enricher import MemoryEnricher, MergeStrategy

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
    ) -> None:
        """
        Initialize the background agent runner.

        Args:
            letta_client: Letta client for agent operations
            honcho_client: Honcho client for dialectic queries

        """
        self.letta = letta_client
        self.honcho = honcho_client
        self.enricher = MemoryEnricher(letta_client)
        self.logger = log.bind(component="background_runner")

    async def run_agent(
        self,
        config: BackgroundAgentConfig,
        user_ids: list[str] | None = None,
    ) -> RunResult:
        """
        Execute a background agent for specified users.

        Args:
            config: Background agent configuration
            user_ids: Specific users to process (None = all)

        Returns:
            RunResult with execution details

        """
        result = RunResult(
            agent_id=config.id,
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
            agent_id=config.id,
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
                )

        result.completed_at = datetime.now()

        self.logger.info(
            "background_agent_completed",
            agent_id=config.id,
            users_processed=result.users_processed,
            queries_executed=result.queries_executed,
            enrichments_applied=result.enrichments_applied,
            errors=len(result.errors),
        )

        return result

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
    ) -> None:
        """Process all queries for a single user."""
        result.users_processed += 1

        for query in config.queries:
            await self._execute_query(
                config=config,
                query=query,
                user_id=user_id,
                result=result,
            )

    async def _execute_query(
        self,
        config: BackgroundAgentConfig,
        query: DialecticQuery,
        user_id: str,
        result: RunResult,
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
        agent_id = self._get_agent_id(user_id, config.agent_types[0])
        if not agent_id:
            result.errors.append(f"No agent found for user {user_id}")
            return

        # Apply enrichment
        strategy = MergeStrategy(query.merge_strategy.value)
        enrich_result = self.enricher.enrich(
            agent_id=agent_id,
            block=query.target_block,
            field=query.target_field,
            content=response.insight,
            strategy=strategy,
            source=f"background:{config.id}",
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
