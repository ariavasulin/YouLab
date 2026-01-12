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

Propose an update to a user's memory block.

**Location**: `src/youlab_server/tools/memory.py`

> **Important**: This tool creates a **pending diff** that requires user approval. Changes are NOT applied immediately.

### Usage

Agents call this tool to propose changes to user memory:

```python
edit_memory_block(
    block="student",
    field="strengths",
    content="Strong analytical thinking",
    strategy="append",
    reasoning="Observed during problem-solving discussion",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `block` | string | Required | Block label (e.g., `"student"`, `"journey"`) |
| `field` | string | Required | Field to update |
| `content` | string | Required | Content to add/replace |
| `strategy` | string | `"append"` | Merge strategy |
| `reasoning` | string | `""` | **Explanation of why** this change is proposed |

**Merge Strategies**:

| Strategy | Behavior |
|----------|----------|
| `append` | Add to existing (default, safe) |
| `replace` | Overwrite existing |
| `llm_diff` | Intelligently merge |

### Returns

Confirmation that the proposal was created:

```
Proposed change to student.strengths (ID: abc12345).
The user will review and approve/reject this suggestion.
```

### Pending Diff Workflow

1. Agent calls `edit_memory_block` with reasoning
2. System creates `PendingDiff` in user storage
3. User sees pending change in UI
4. User approves → Change applied, git commit created
5. User rejects → Change discarded
6. New proposals for same block supersede older ones

### Example Prompts

Include in agent persona:

```
You have access to the edit_memory_block tool. Use it to:
- Propose updates to what you've learned about the student
- Suggest adding new strengths or insights
- Recommend updating the learning journey

IMPORTANT:
- Changes require user approval - explain your reasoning clearly
- The reasoning field helps users understand WHY you're suggesting this change
- Be specific and evidence-based in your proposals

Example: edit_memory_block(
    block="student",
    field="background",
    content="Senior year, applying to CS programs",
    strategy="replace",
    reasoning="Student mentioned they are in their final year and focused on CS applications"
)
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
