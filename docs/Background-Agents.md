# Background Agents

[[README|← Back to Overview]]

Background agents run scheduled or manual tasks to enrich agent memory using Honcho dialectic queries.

## Overview

Background agents enable theory-of-mind (ToM) integration by:
1. Querying Honcho for insights about students
2. Enriching agent memory with those insights
3. Writing audit trails to archival memory

```
┌──────────────────────────────────────────────────────────────┐
│                  Background Agent Flow                        │
│                                                               │
│  Trigger (cron/manual)                                        │
│         │                                                     │
│         ▼                                                     │
│  ┌─────────────────────┐                                      │
│  │ BackgroundAgentRunner│                                     │
│  └──────────┬──────────┘                                      │
│             │                                                 │
│             ▼                                                 │
│  ┌─────────────────────┐      ┌─────────────────────┐        │
│  │   HonchoClient      │──────│   Honcho Service    │        │
│  │   query_dialectic() │      │   (ToM insights)    │        │
│  └──────────┬──────────┘      └─────────────────────┘        │
│             │                                                 │
│             ▼                                                 │
│  ┌─────────────────────┐                                      │
│  │   MemoryEnricher    │                                      │
│  │   (audit trail)     │                                      │
│  └──────────┬──────────┘                                      │
│             │                                                 │
│             ▼                                                 │
│  ┌─────────────────────┐                                      │
│  │   Letta Agent       │                                      │
│  │   (memory blocks)   │                                      │
│  └─────────────────────┘                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## TOML Configuration

Background agents are configured via TOML files in `config/courses/`.

**Location**: `config/courses/{course-name}.toml`

### Course Structure

```toml
id = "college-essay"
name = "College Essay Coaching"

[[background_agents]]
id = "insight-harvester"
name = "Student Insight Harvester"
enabled = true
agent_types = ["tutor"]
user_filter = "all"
batch_size = 50

[background_agents.triggers]
schedule = "0 3 * * *"  # Cron expression
manual = true

[background_agents.triggers.idle]
enabled = false
threshold_minutes = 30
cooldown_minutes = 60

[[background_agents.queries]]
id = "learning_style"
question = "What learning style works best for this student?"
session_scope = "all"
target_block = "human"
target_field = "context_notes"
merge_strategy = "append"
```

### Configuration Schema

#### CourseConfig

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique course identifier |
| `name` | string | Display name |
| `background_agents` | array | List of background agents |

#### BackgroundAgentConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | Required | Unique agent identifier |
| `name` | string | Required | Display name |
| `enabled` | bool | `true` | Whether agent runs |
| `agent_types` | array | `["tutor"]` | Which agent types to process |
| `user_filter` | string | `"all"` | User filtering |
| `batch_size` | int | `50` | Users per batch |
| `triggers` | Triggers | - | Trigger configuration |
| `queries` | array | `[]` | Dialectic queries |

#### Triggers

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schedule` | string | `null` | Cron expression |
| `idle.enabled` | bool | `false` | Enable idle trigger |
| `idle.threshold_minutes` | int | `30` | Idle time threshold |
| `idle.cooldown_minutes` | int | `60` | Cooldown between runs |
| `manual` | bool | `true` | Allow manual triggers |

#### DialecticQuery

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | Required | Query identifier |
| `question` | string | Required | Natural language question |
| `session_scope` | enum | `"all"` | `all`, `recent`, `current`, `specific` |
| `recent_limit` | int | `5` | Sessions for `recent` scope |
| `target_block` | string | Required | `"human"` or `"persona"` |
| `target_field` | string | Required | Field to update |
| `merge_strategy` | enum | `"append"` | `append`, `replace`, `llm_diff` |

---

## Components

### BackgroundAgentRunner

**Location**: `src/youlab_server/background/runner.py`

Executes background agents based on configuration.

```python
from youlab_server.background.runner import BackgroundAgentRunner

runner = BackgroundAgentRunner(
    letta_client=letta,
    honcho_client=honcho,
)

result = await runner.run_agent(
    config=agent_config,
    user_ids=["user123"],  # Optional: specific users
)

print(f"Processed {result.users_processed} users")
print(f"Applied {result.enrichments_applied} enrichments")
```

#### RunResult

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Background agent ID |
| `started_at` | datetime | Start time |
| `completed_at` | datetime | End time |
| `users_processed` | int | Users processed |
| `queries_executed` | int | Queries run |
| `enrichments_applied` | int | Successful enrichments |
| `errors` | list | Error messages |

---

### MemoryEnricher

**Location**: `src/youlab_server/memory/enricher.py`

Handles external memory updates with audit trailing.

```python
from youlab_server.memory.enricher import MemoryEnricher, MergeStrategy

enricher = MemoryEnricher(letta_client)

result = enricher.enrich(
    agent_id="agent-abc123",
    block="human",
    field="context_notes",
    content="Student prefers visual explanations",
    strategy=MergeStrategy.APPEND,
    source="background:insight-harvester",
    source_query="What learning style works best?",
)
```

#### Audit Trail

Each enrichment writes an audit entry to the agent's archival memory:

```
[MEMORY_EDIT 2025-01-08T03:00:00]
Source: background:insight-harvester
Block: human
Field: context_notes
Strategy: append
Query: What learning style works best?
Content: Student prefers visual explanations...
```

---

## HTTP Endpoints

### GET /background/agents

List configured background agents.

```bash
curl http://localhost:8100/background/agents
```

### POST /background/{agent_id}/run

Manually trigger a background agent.

```bash
curl -X POST http://localhost:8100/background/insight-harvester/run \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["user123"]}'
```

### POST /background/config/reload

Hot-reload TOML configuration.

```bash
curl -X POST http://localhost:8100/background/config/reload
```

See [[HTTP-Service#Background Endpoints]] for full API details.

---

## Merge Strategies

| Strategy | Behavior |
|----------|----------|
| `append` | Add to existing list (default, safe) |
| `replace` | Overwrite existing content |
| `llm_diff` | Intelligently merge (TODO: LLM integration) |

---

## Example: Insight Harvester

The `college-essay.toml` config includes an insight harvester that:

1. Runs daily at 3 AM
2. Queries all students with tutor agents
3. Asks three questions per student:
   - Learning style preferences
   - Engagement patterns
   - Communication style
4. Enriches memory blocks with insights

```toml
[[background_agents.queries]]
id = "learning_style"
question = "What learning style works best for this student? Do they prefer examples, theory, or hands-on practice?"
session_scope = "all"
target_block = "human"
target_field = "context_notes"
merge_strategy = "append"
```

---

## Related Pages

- [[Honcho]] - Honcho integration and dialectic queries
- [[HTTP-Service]] - Background endpoint details
- [[Agent-Tools]] - In-conversation tools (query_honcho, edit_memory_block)
- [[Memory-System]] - Memory block architecture
