# Letta Core Concepts

[[README|← Back to Overview]]

Understanding Letta's architecture and design philosophy.

## What is Letta?

Letta is a platform for building **stateful AI agents** based on the MemGPT research. Unlike traditional LLM APIs that are stateless, Letta agents:

- **Maintain persistent state** - All agent state persists to database at each step
- **Self-manage memory** - Agents autonomously decide what to store and retrieve
- **Exist as services** - Independent services that continue when your app stops

---

## Key Architectural Principles

### 1. No Sessions, Only Agents

Traditional chatbots use ephemeral "threads" or "sessions." Letta eliminates this:

> There are only **stateful agents with a single perpetual thread** of messages.

Every interaction becomes part of the agent's persistent memory.

### 2. Tool-Based Actions

Everything an agent does is a tool call:

| Category | Examples |
|----------|----------|
| Memory | `memory_insert`, `memory_replace`, `archival_memory_search` |
| Communication | `send_message` (legacy) |
| External | Custom tools, web search, code execution |

### 3. Two-Tier Memory

```
┌─────────────────────────────────────┐
│        Core Memory (In-Context)     │
│  Always visible in every prompt     │
│  - persona block                    │
│  - human block                      │
│  - custom blocks                    │
└─────────────────────────────────────┘
                  │
                  │ Rotation / Search
                  ▼
┌─────────────────────────────────────┐
│     Archival Memory (Vector DB)     │
│  Semantic search on-demand          │
│  - Unlimited capacity               │
│  - Historical context               │
└─────────────────────────────────────┘
```

---

## The Agentic Loop

At each step:

1. Agent receives input (user message or system trigger)
2. LLM processes with full context (system + memory + history)
3. Agent decides on tool calls (memory updates, external actions)
4. Tool results are added to context
5. **State is checkpointed** to database
6. Loop continues until agent signals completion

```
Input → LLM → Tool Calls → Execute → Checkpoint → Response
         ↑                              │
         └──────────────────────────────┘
                   (loop)
```

---

## Agent State

An agent's complete state includes:

| Component | Description |
|-----------|-------------|
| `id` | Unique identifier |
| `name` | Human-readable name |
| `model` | LLM model (e.g., `openai/gpt-4o-mini`) |
| `embedding` | Embedding model for archival search |
| `system` | System prompt (instructions) |
| `memory_blocks` | Core memory blocks (persona, human, etc.) |
| `tools` | Attached tools |
| `metadata` | Custom key-value data |

---

## Model Handle Format

Models are specified as `provider/model-name`:

| Provider | Example Models |
|----------|----------------|
| OpenAI | `openai/gpt-4o-mini`, `openai/gpt-4.1` |
| Anthropic | `anthropic/claude-3-5-sonnet`, `anthropic/claude-3-opus` |
| Ollama | `ollama/llama2:7b-q6_K` |
| Google | `google/gemini-pro` |

**Embedding Models**:

| Model | Notes |
|-------|-------|
| `openai/text-embedding-3-small` | Recommended |
| `openai/text-embedding-ada-002` | Used in YouLab |
| `letta/letta-free` | Free hosted option |

---

## Memory Blocks

Structured sections of context always visible to the agent.

### Block Properties

| Property | Type | Description |
|----------|------|-------------|
| `label` | string | Unique identifier (`persona`, `human`, custom) |
| `description` | string | Guides agent on how to use block |
| `value` | string | Actual content |
| `limit` | int | Character limit (default: 2000) |
| `read_only` | bool | Prevent agent modifications |

### Default Blocks

- **`persona`** - Agent identity, capabilities, constraints (stable)
- **`human`** - User information, preferences, current task (dynamic)

### How Agents Use Blocks

The `description` field is critical:

```python
# Block with clear description
{
    "label": "preferences",
    "description": "User preferences learned over time. Update when user expresses likes/dislikes.",
    "value": "Prefers concise answers. Likes examples."
}
```

The agent reads the description to understand:
- When to read from this block
- When to update it
- What kind of information belongs here

---

## Archival Memory

Long-term storage with semantic search.

### Characteristics

| Feature | Value |
|---------|-------|
| Storage | Vector database (pgvector, TurboPuffer) |
| Search | Hybrid (semantic + keyword) |
| Capacity | Unlimited (100k+ passages) |
| Agent Access | Insert + Search (no delete) |

### Agent Tools

| Tool | Purpose |
|------|---------|
| `archival_memory_insert` | Store content with tags |
| `archival_memory_search` | Semantic search |
| `conversation_search` | Search chat history |

### Best Practice

Use memory blocks for "executive summary" and archival for full details:

```
Core Memory:
  "User prefers Socratic questioning. Working on essay about identity."

Archival Memory:
  [Full history of 20 conversations about essay development]
```

---

## Agent Types

### Modern Architecture (Current)

Create agents without specifying `agent_type`:

```python
agent = client.agents.create(
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-ada-002",
    memory_blocks=[...],
)
```

Features:
- Works with any chat model
- Native reasoning support
- No heartbeat system

### Legacy Architecture

Older agent types (deprecated):

| Type | Notes |
|------|-------|
| `memgpt_agent` | Required `send_message` tool, heartbeats |
| `memgpt_v2_agent` | Sleep-time agents |
| `letta_v1_agent` | Transitional |

---

## Client Initialization

```python
from letta_client import Letta

# Self-hosted (YouLab default)
client = Letta(base_url="http://localhost:8283")

# Letta Cloud
client = Letta(token="LETTA_API_KEY")

# Async client
from letta_client import AsyncLetta
async_client = AsyncLetta(base_url="http://localhost:8283")
```

---

## YouLab Integration

YouLab creates per-user agents with naming convention:

```python
name = f"youlab_{user_id}_{agent_type}"
# Example: "youlab_user123_tutor"

metadata = {
    "youlab_user_id": user_id,
    "youlab_agent_type": agent_type,
}
```

See [[Agent-System]] for full details on YouLab's agent management.

---

## External Resources

- [Letta Documentation](https://docs.letta.com)
- [Core Concepts Guide](https://docs.letta.com/core-concepts/)
- [Building Stateful Agents](https://docs.letta.com/guides/agents/overview/)
- [MemGPT Research Background](https://docs.letta.com/concepts/memgpt/)

---

## Related Pages

- [[Letta-SDK]] - SDK patterns and code examples
- [[Letta-REST-API]] - Complete API reference
- [[Letta-Streaming]] - Message streaming
- [[Memory-System]] - YouLab's memory implementation
