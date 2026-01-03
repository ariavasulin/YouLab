# Letta SDK Patterns

[[README|← Back to Overview]]

Common patterns for working with the Letta SDK in YouLab.

## Overview

Letta is the agent framework that powers YouLab. It provides:
- Persistent memory (core + archival)
- Streaming responses
- Tool integration
- Multi-turn conversations

---

## Client Initialization

```python
from letta import Letta

# Default connection (localhost:8283)
client = Letta()

# Custom URL
client = Letta(base_url="http://localhost:8283")
```

In YouLab, the client is typically initialized via settings:

```python
from letta_starter.config import get_settings

settings = get_settings()
client = Letta(base_url=str(settings.letta_base_url))
```

---

## Agent Management

### Creating an Agent

```python
agent = client.agents.create(
    name="youlab_user123_tutor",
    memory_blocks=[
        {"label": "persona", "value": persona_string},
        {"label": "human", "value": human_string},
    ],
    system="You are a helpful assistant...",
    model="claude-sonnet-4-20250514",
    embedding="letta/letta-free",
    metadata={
        "youlab_user_id": "user123",
        "youlab_agent_type": "tutor",
    },
)
```

### Listing Agents

```python
# List all agents
agents = client.agents.list()

# Filter by name
agents = client.agents.list(name="youlab_user123_tutor")
```

### Getting an Agent

```python
agent = client.agents.retrieve(agent_id)
```

### Agent Properties

```python
agent.id          # Unique identifier
agent.name        # Agent name
agent.model       # LLM model
agent.metadata    # Custom metadata
agent.created_at  # Creation timestamp
```

---

## Memory Management

### Memory Blocks

Letta agents have two primary memory blocks:

| Block | Label | Purpose |
|-------|-------|---------|
| Persona | `persona` | Agent identity (stable) |
| Human | `human` | User context (dynamic) |

### Reading Memory

```python
blocks = client.agents.core_memory.list(agent_id)

for block in blocks:
    if block.label == "human":
        current_value = block.value
```

### Updating Memory

```python
# Get the block ID first
blocks = client.agents.core_memory.list(agent_id)
human_block = next(b for b in blocks if b.label == "human")

# Update the block
client.agents.core_memory.update(
    agent_id=agent_id,
    block_id=human_block.id,
    value=new_value,
)
```

### Archival Memory

```python
# Insert into archival
client.agents.archival_memory.insert(
    agent_id=agent_id,
    text="[ARCHIVED 2025-01-01]\nImportant context...",
)

# Search archival
results = client.agents.archival_memory.search(
    agent_id=agent_id,
    query="essay topics",
    limit=5,
)

for result in results:
    print(result.text)
```

---

## Sending Messages

### Synchronous

```python
response = client.agents.messages.create(
    agent_id=agent_id,
    messages=[{"role": "user", "content": "Hello!"}],
)

# Extract assistant message
for msg in response.messages:
    if hasattr(msg, "content") and msg.content:
        print(msg.content)
```

### Streaming

```python
from letta.streaming import StreamingChatCompletionChunk

stream = client.agents.messages.create_stream(
    agent_id=agent_id,
    messages=[{"role": "user", "content": "Hello!"}],
)

for chunk in stream:
    if isinstance(chunk, StreamingChatCompletionChunk):
        # Process chunk type
        if hasattr(chunk, "choices"):
            for choice in chunk.choices:
                if choice.delta and choice.delta.content:
                    print(choice.delta.content, end="")
```

---

## Streaming Chunk Types

YouLab handles these Letta streaming chunk types:

| Type | When Sent | YouLab Handling |
|------|-----------|-----------------|
| `reasoning_message` | Agent is thinking | `{"type": "status", "content": "Thinking..."}` |
| `tool_call_message` | Agent uses a tool | `{"type": "status", "content": "Using {tool}..."}` |
| `assistant_message` | Actual response | `{"type": "message", "content": "..."}` |
| `stop_reason` | Stream complete | `{"type": "done"}` |
| `ping` | Keepalive | `: keepalive\n\n` |
| `error_message` | Error occurred | `{"type": "error", "message": "..."}` |

---

## YouLab's BaseAgent Pattern

YouLab wraps Letta agents with the `BaseAgent` class:

```python
from letta_starter.agents.base import BaseAgent
from letta_starter.memory.blocks import PersonaBlock, HumanBlock

class TutorAgent(BaseAgent):
    def __init__(self, client: Letta, user_id: str):
        persona = PersonaBlock(
            name="YouLab Coach",
            role="Essay writing tutor",
            capabilities=["Guide discovery", "Brainstorm topics"],
        )
        human = HumanBlock(name=user_id)

        super().__init__(
            client=client,
            name=f"youlab_{user_id}_tutor",
            persona=persona,
            human=human,
        )
```

### BaseAgent Features

```python
# Memory management
agent.memory.set_task("Write introduction")
agent.memory.add_context("Discussed themes")
agent.memory.learn_preference("Prefers examples")

# Diagnostics
summary = agent.memory.get_summary()
print(f"Memory usage: {summary['total_usage']:.1%}")

# Archival search
results = agent.memory.search_archival("essay topics")
```

---

## Error Handling

### Connection Errors

```python
from httpx import ConnectError

try:
    client.agents.list()
except ConnectError:
    print("Letta server not available")
```

### Agent Not Found

```python
try:
    agent = client.agents.retrieve("invalid-id")
except Exception as e:
    if "not found" in str(e).lower():
        print("Agent doesn't exist")
```

### Health Check Pattern

```python
def check_letta_health() -> bool:
    try:
        client.agents.list(limit=1)
        return True
    except Exception:
        return False
```

---

## Best Practices

### 1. Reuse Client Instances

```python
# Good - reuse client
client = Letta()
for user_id in users:
    agent = client.agents.retrieve(...)

# Bad - create new client each time
for user_id in users:
    client = Letta()  # Overhead!
    agent = client.agents.retrieve(...)
```

### 2. Cache Agent IDs

```python
# YouLab's AgentManager pattern
class AgentManager:
    def __init__(self):
        self._cache: dict[tuple[str, str], str] = {}

    async def get_agent_id(self, user_id: str, agent_type: str) -> str:
        key = (user_id, agent_type)
        if key not in self._cache:
            # Query Letta
            agent = await self._find_agent(user_id, agent_type)
            self._cache[key] = agent.id
        return self._cache[key]
```

### 3. Handle Memory Limits

```python
# Check before updating
current_chars = len(human_block.value)
max_chars = 1500

if current_chars > max_chars * 0.8:
    # Rotate to archival
    await archive_old_context()
```

### 4. Use Structured Memory

```python
# Good - structured, parseable
"[USER] Alice | Student\n[TASK] Essay brainstorming\n[STATE] active_task"

# Bad - unstructured
"The user Alice is a student working on essay brainstorming"
```

---

## Related Pages

- [[Memory-System]] - Memory block details
- [[Agent-System]] - Agent templates
- [[HTTP-Service]] - Service integration
- [[Streaming|HTTP-Service#streaming-implementation]] - Streaming details

