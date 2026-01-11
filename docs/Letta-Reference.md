# Letta Quick Reference

[[README|<- Back to Overview]]

Quick reference for Letta APIs. For detailed documentation, see [docs.letta.com](https://docs.letta.com).

## Installation

```bash
pip install letta         # Server
pip install letta-client  # Python SDK
```

## Server

```bash
letta server              # Start on :8283
```

## Client

```python
from letta_client import Letta

client = Letta(base_url="http://localhost:8283")
```

---

## Common Operations

### Agents

```python
# Create
agent = client.agents.create(
    name="my-agent",
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",
    memory_blocks=[
        {"label": "persona", "value": "I am..."},
        {"label": "human", "value": "User info..."},
    ],
)

# List
agents = client.agents.list()

# Get
agent = client.agents.retrieve(agent_id)

# Delete
client.agents.delete(agent_id)
```

### Messages

```python
# Synchronous
response = client.agents.messages.create(
    agent_id=agent.id,
    input="Hello!"
)

# Streaming
with client.agents.messages.stream(
    agent_id=agent.id,
    input="Hello!",
) as stream:
    for chunk in stream:
        print(chunk)
```

### Memory

```python
# Core memory
blocks = client.agents.core_memory.list(agent_id)
client.agents.core_memory.update(agent_id, block_id, value="...")

# Archival memory
client.agents.archival_memory.insert(agent_id, text="...")
results = client.agents.archival_memory.search(agent_id, query="...")
```

### Tools

```python
# Create from function
tool = client.tools.upsert_from_function(func=my_function)

# Attach to agent
client.agents.tools.attach(agent_id, tool_id)
```

---

## Model Formats

```python
# LLM models
"openai/gpt-4o-mini"
"anthropic/claude-3-5-sonnet"
"ollama/llama2:7b"

# Embedding models
"openai/text-embedding-3-small"
"letta/letta-free"
```

---

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LETTA_BASE_URL=http://localhost:8283
```

---

## Official Documentation

| Topic | Link |
|-------|------|
| Getting Started | [docs.letta.com/quickstart](https://docs.letta.com/quickstart) |
| Core Concepts | [docs.letta.com/core-concepts](https://docs.letta.com/core-concepts) |
| Agent Memory | [docs.letta.com/guides/agents/memory](https://docs.letta.com/guides/agents/memory) |
| Streaming | [docs.letta.com/guides/agents/streaming](https://docs.letta.com/guides/agents/streaming) |
| Tools | [docs.letta.com/guides/agents/tools](https://docs.letta.com/guides/agents/tools) |
| REST API | [docs.letta.com/api-reference](https://docs.letta.com/api-reference) |

---

## Version Compatibility

YouLab requires `letta>=0.6.0`. Current stable: 0.10.x

See [GitHub releases](https://github.com/letta-ai/letta/releases) for changelog.

---

## Related Pages

- [[Letta-Integration]] - YouLab-specific patterns
- [[Configuration]] - Environment setup
