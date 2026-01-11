# Letta Integration

[[README|<- Back to Overview]]

How YouLab integrates with the Letta agent framework.

## Overview

Letta provides stateful AI agents with persistent memory. YouLab leverages:

- **Persistent state** - Agent state survives restarts
- **Two-tier memory** - Core (in-context) + Archival (vector search)
- **Streaming** - Real-time response delivery
- **Tool system** - Custom tools for memory editing

For complete Letta documentation, see [docs.letta.com](https://docs.letta.com).

---

## Client Initialization

```python
from letta_client import Letta

# Self-hosted (YouLab default)
client = Letta(base_url="http://localhost:8283")

# From settings
from youlab_server.config import get_settings
settings = get_settings()
client = Letta(base_url=str(settings.letta_base_url))
```

---

## Agent Creation

YouLab creates agents with course-specific configuration:

```python
agent = client.agents.create(
    name="youlab_user123_college-essay",
    memory_blocks=[
        {"label": "persona", "value": persona_string},
        {"label": "human", "value": human_string},
    ],
    model="anthropic/claude-sonnet-4-20250514",
    embedding="openai/text-embedding-3-small",
    metadata={
        "youlab_user_id": "user123",
        "youlab_course_id": "college-essay",
    },
)
```

---

## Memory Patterns

### Core Memory Blocks

Always visible in agent context:

```python
blocks = client.agents.core_memory.list(agent_id)
human_block = next(b for b in blocks if b.label == "human")

# Update block
client.agents.core_memory.update(
    agent_id=agent_id,
    block_id=human_block.id,
    value=new_value,
)
```

### Archival Memory

Long-term storage with semantic search:

```python
# Insert
client.agents.archival_memory.insert(
    agent_id=agent_id,
    text="[ARCHIVED 2025-01-01]\nContext...",
)

# Search
results = client.agents.archival_memory.search(
    agent_id=agent_id,
    query="essay topics",
    limit=5,
)
```

---

## Streaming

### SDK Pattern

```python
with client.agents.messages.stream(
    agent_id=agent.id,
    input="Hello!",
    stream_tokens=False,
    include_pings=True,
) as stream:
    for chunk in stream:
        if chunk.message_type == "assistant_message":
            print(chunk.content)
```

### Message Types

| Type | Purpose |
|------|---------|
| `reasoning_message` | Agent thinking |
| `tool_call_message` | Tool invocation |
| `assistant_message` | Response to user |
| `stop_reason` | Stream complete |
| `usage_statistics` | Token counts |

---

## Tool System

### Creating Tools

```python
def my_tool(arg: str) -> str:
    """
    Tool description.

    Args:
        arg: Input argument

    Returns:
        Result string
    """
    return f"Processed: {arg}"

tool = client.tools.upsert_from_function(func=my_tool)
```

### Attaching to Agent

```python
client.agents.tools.attach(agent_id=agent.id, tool_id=tool.id)
```

---

## Best Practices

### 1. Reuse Client Instances

```python
# Good
client = Letta()
for user in users:
    agent = client.agents.retrieve(...)

# Bad - creates overhead
for user in users:
    client = Letta()  # Don't do this
```

### 2. Cache Agent IDs

```python
_cache: dict[str, str] = {}

async def get_agent_id(user_id: str) -> str:
    if user_id not in _cache:
        agent = await find_agent(user_id)
        _cache[user_id] = agent.id
    return _cache[user_id]
```

### 3. Use Structured Memory

```python
# Good - parseable
"[USER] Alice | Student\n[TASK] Essay brainstorming"

# Bad - unstructured
"Alice is a student working on essay brainstorming"
```

---

## Related Pages

- [[Letta-Reference]] - Quick reference and links
- [[Agent-System]] - YouLab agent management
- [[Memory-System]] - Memory block patterns
