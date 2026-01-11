# Agent Tools

[[README|← Back to Overview]]

Custom Letta tools that agents can call during conversations.

## Overview

YouLab provides two agent tools:

| Tool | Purpose | Location |
|------|---------|----------|
| `query_honcho` | Query Honcho for student insights | `src/youlab_server/tools/dialectic.py` |
| `edit_memory_block` | Update memory blocks | `src/youlab_server/tools/memory.py` |

These tools enable agents to:
- Access theory-of-mind insights mid-conversation
- Update their own memory based on learned information

---

## query_honcho

Query Honcho dialectic for insights about the current student.

**Location**: `src/youlab_server/tools/dialectic.py`

### Usage

Agents call this tool with a natural language question:

```python
query_honcho(
    question="What learning style works best for this student?",
    session_scope="all",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | Required | Natural language question about the student |
| `session_scope` | string | `"all"` | Which sessions to include |

**Session Scopes**:

| Scope | Description |
|-------|-------------|
| `all` | All conversation history |
| `recent` | Last few sessions |
| `current` | Current conversation only |

### Returns

Returns Honcho's insight as a string, or an error message if unavailable.

### Example Prompts

Include in agent persona to enable usage:

```
You have access to the query_honcho tool. Use it to:
- Understand student learning patterns
- Recall past conversation context
- Identify communication preferences

Example: query_honcho("How engaged is this student with the current topic?")
```

### Context Requirements

The tools require client context to be set before use:

```python
from youlab_server.tools.dialectic import set_honcho_client, set_user_context
from youlab_server.tools.memory import set_letta_client

# During service initialization
set_honcho_client(honcho_client)
set_letta_client(letta_client)

# Before each conversation
set_user_context(agent_id="agent-abc", user_id="user123")
```

---

## edit_memory_block

Update a field in the agent's memory blocks.

**Location**: `src/youlab_server/tools/memory.py`

### Usage

Agents call this tool to record learned information:

```python
edit_memory_block(
    block="human",
    field="facts",
    content="Student is applying to Stanford and MIT",
    strategy="append",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `block` | string | Required | `"human"` or `"persona"` |
| `field` | string | Required | Field to update |
| `content` | string | Required | Content to add/replace |
| `strategy` | string | `"append"` | Merge strategy |

**Available Fields**:

| Block | Fields |
|-------|--------|
| `human` | `context_notes`, `facts`, `preferences` |
| `persona` | `constraints`, `expertise` |

**Merge Strategies**:

| Strategy | Behavior |
|----------|----------|
| `append` | Add to existing (default, safe) |
| `replace` | Overwrite existing |
| `llm_diff` | Intelligently merge |

### Returns

Confirmation message or error description.

### Protected Fields

Some fields cannot be edited by agents:

| Protected Field | Reason |
|-----------------|--------|
| `persona.name` | Identity should not change |
| `persona.role` | Role should not change |

Attempting to edit protected fields returns an error.

### Example Prompts

Include in agent persona:

```
You have access to the edit_memory_block tool. Use it to:
- Record important facts about the student
- Note preferences for future reference
- Update context based on new information

Example: edit_memory_block(
    block="human",
    field="facts",
    content="Student prefers morning study sessions",
    strategy="append"
)

IMPORTANT: Only store factual, relevant information. Don't overwrite existing content unless correcting errors.
```

---

## Tool Registration

Tools are registered with Letta agents during creation:

```python
from youlab_server.tools.dialectic import query_honcho
from youlab_server.tools.memory import edit_memory_block

# Tools are added to agent via Letta SDK
agent = client.create_agent(
    ...
    tools=[query_honcho, edit_memory_block],
)
```

---

## Comparison: Tools vs Background Agents

| Aspect | Agent Tools | Background Agents |
|--------|-------------|-------------------|
| Trigger | During conversation | Scheduled/manual |
| Actor | Agent decides | System decides |
| Scope | Current session | Batch across users |
| Audit | Letta message history | Archival memory |
| Use case | Real-time insights | Periodic enrichment |

**When to use tools**: Agent needs information or wants to record something during a conversation.

**When to use background agents**: Periodic batch processing of student data across all users.

---

## Related Pages

- [[Background-Agents]] - Scheduled memory enrichment
- [[Honcho]] - Honcho integration and dialectic queries
- [[Memory-System]] - Memory block structure
- [[Letta-Tools]] - Letta tool system reference
