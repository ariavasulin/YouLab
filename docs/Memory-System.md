# Memory System

[[README|← Back to Overview]]

The memory system provides structured, token-efficient context management for Letta agents.

## Overview

```
┌────────────────────────────────────────────────────────┐
│                    Core Memory                          │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │    PersonaBlock     │  │      HumanBlock         │  │
│  │                     │  │                         │  │
│  │  [IDENTITY]         │  │  [USER] Alice | Student │  │
│  │  YouLab Coach | AI  │  │  [TASK] Essay topics    │  │
│  │                     │  │  [STATE] active_task    │  │
│  │  [CAPABILITIES]     │  │  [PREFS] Socratic...    │  │
│  │  Guide discovery... │  │  [CONTEXT] Discussed... │  │
│  │                     │  │                         │  │
│  │  [STYLE]            │  │                         │  │
│  │  warm, adaptive     │  │                         │  │
│  └─────────────────────┘  └───────────┬─────────────┘  │
│                                       │                 │
│                    Rotation at >80%   │                 │
└───────────────────────────────────────┼─────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────┐
│                  Archival Memory                        │
│                                                         │
│  [ARCHIVED 2025-12-31T10:00:00]                        │
│  [USER] Alice | High school senior                     │
│  [TASK] Brainstorm essay topics                        │
│  [CONTEXT] Discussed identity themes; Explored...      │
│                                                         │
│  [TASK COMPLETED 2025-12-30T15:00:00]                  │
│  Task: Initial brainstorming                            │
│  Notes: Identified 5 potential topics...               │
│                                                         │
└────────────────────────────────────────────────────────┘
```

## Memory Blocks

### PersonaBlock

Defines agent identity - stable across sessions.

**Location**: `src/letta_starter/memory/blocks.py:28-131`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str | `"Assistant"` | Agent display name |
| `role` | str | Required | Primary role |
| `capabilities` | list[str] | `[]` | What agent can do |
| `tone` | str | `"professional"` | Communication style |
| `verbosity` | str | `"concise"` | Response length |
| `constraints` | list[str] | `[]` | What NOT to do |
| `expertise` | list[str] | `[]` | Specializations |

**Serialization Format**:

```
[IDENTITY] YouLab Essay Coach | AI tutor for college essays
[CAPABILITIES] Guide self-discovery, Brainstorm topics, Provide feedback
[EXPERTISE] College admissions, Personal narrative, Reflective writing
[STYLE] warm, adaptive
[CONSTRAINTS] Never write essays; Ask clarifying questions first
```

**Limits**:
- Max 5 capabilities
- Max 4 expertise areas
- Max 3 constraints
- Total: 1500 characters (default)

---

### HumanBlock

User context - dynamic, frequently updated.

**Location**: `src/letta_starter/memory/blocks.py:134-274`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str \| None | `None` | User's name |
| `role` | str \| None | `None` | User's profession |
| `current_task` | str \| None | `None` | Active work |
| `session_state` | SessionState | `IDLE` | Current state |
| `preferences` | list[str] | `[]` | Learned preferences |
| `context_notes` | list[str] | `[]` | Recent context |
| `facts` | list[str] | `[]` | Important facts |

**SessionState Values**:

| State | Description |
|-------|-------------|
| `IDLE` | No active task |
| `ACTIVE_TASK` | Working on something |
| `WAITING_INPUT` | Awaiting user response |
| `THINKING` | Processing |
| `ERROR_RECOVERY` | Handling error |

**Serialization Format**:

```
[USER] Alice | High school senior
[TASK] Brainstorm essay topics about identity
[STATE] active_task
[PREFS] Prefers Socratic questions; Likes detailed feedback
[FACTS] Planning to study CS; Has published poetry
[CONTEXT] Discussed identity; Explored challenges; Wants curiosity
```

**Limits**:
- Max 4 preferences
- Max 3 facts
- Max 3 context notes (last 3 of rolling window)

---

### Helper Methods

```python
# Add context with rolling window
human.add_context_note("Discussed identity themes")  # max 10 notes

# Learn about user
human.add_preference("Prefers Socratic questions")
human.add_fact("Planning to study computer science")

# Task management
human.set_task("Brainstorm essay topics")  # Sets state to ACTIVE_TASK
human.clear_task()  # Returns to IDLE
```

---

## Rotation Strategies

Strategies determine when to move context from core to archival memory.

**Location**: `src/letta_starter/memory/strategies.py`

### ContextMetrics

```python
@dataclass
class ContextMetrics:
    persona_chars: int
    human_chars: int
    persona_max: int
    human_max: int

    @property
    def persona_usage(self) -> float  # 0-1
    @property
    def human_usage(self) -> float    # 0-1
    @property
    def total_usage(self) -> float    # 0-1
```

### Strategy Comparison

| Strategy | Threshold | Best For |
|----------|-----------|----------|
| AggressiveRotation | 70% | Long sessions, many short tasks |
| PreservativeRotation | 90% | Complex multi-step tasks |
| AdaptiveRotation | 80% (adjusts) | General use (**default**) |

### AggressiveRotation

Rotates frequently to keep core memory lean.

```python
threshold = 0.7  # 70%

def compress(content, target_chars):
    # Keep most recent content
    return "..." + content[-(target_chars - 3):]
```

### PreservativeRotation

Preserves more in core, rotates only when necessary.

```python
threshold = 0.9  # 90%

def compress(content, target_chars):
    # Prioritize structured content (lines starting with [)
    priority_lines = [l for l in lines if l.startswith("[")]
    other_lines = [l for l in lines if not l.startswith("[")]
    # Add priority lines first, then others
```

### AdaptiveRotation

Learns from usage patterns.

```python
base_threshold = 0.8  # 80%

# Adjusts based on rotation frequency
if rotating_too_often:    # avg < 0.5
    threshold += 0.05     # max 0.95
elif rarely_rotating:      # avg > 0.9
    threshold -= 0.05     # min 0.6

def compress(content, target_chars):
    # Score lines by importance
    # [TASK] = 100, [USER] = 90, [CONTEXT] = 80, [*] = 50, other = 10
    # Keep highest-scoring lines up to target
```

---

## MemoryManager

Orchestrates memory lifecycle.

**Location**: `src/letta_starter/memory/manager.py`

### Initialization

```python
manager = MemoryManager(
    client=letta_client,
    agent_id="agent-abc123",
    max_chars=1500,
    strategy=AdaptiveRotation(),  # default
)
```

### High-Level Methods

```python
# Task management
manager.set_task("Brainstorm essay topics", context="Starting session")
manager.clear_task(archive=True)  # Archive before clearing

# Learning
manager.learn_preference("Prefers detailed feedback")
manager.learn_fact("Studies computer science")

# Context
manager.add_context("Discussed identity themes")

# Diagnostics
summary = manager.get_summary()
# Returns: usage percentages, state, task, notes count

# Search
results = manager.search_archival("essay topics", limit=5)
```

### Automatic Rotation

When `update_human()` is called:

1. Serialize human block
2. Calculate metrics
3. Check `strategy.should_rotate(metrics)`
4. If yes, call `_rotate_human_to_archival()`
5. Update Letta with serialized block

### Archival Format

```
[ARCHIVED 2025-12-31T10:00:00]
[USER] Alice | High school senior
[TASK] Brainstorm essay topics
[STATE] active_task
[PREFS] Prefers Socratic questions
[CONTEXT] Discussed identity; Explored challenges
```

### Task Archival

When clearing a task with `archive=True`:

```
[TASK COMPLETED 2025-12-31T10:00:00]
Task: Brainstorm essay topics
Context:
- Discussed identity themes
- Explored personal challenges
- Identified 5 potential topics
```

---

## Pre-configured Personas

**Location**: `src/letta_starter/memory/blocks.py:278-321`

### DEFAULT_PERSONA

```python
PersonaBlock(
    name="Assistant",
    role="General-purpose AI assistant",
    capabilities=["Answer questions", "Help with tasks", ...],
    tone="friendly",
    verbosity="adaptive",
)
```

### CODING_ASSISTANT_PERSONA

```python
PersonaBlock(
    name="CodeHelper",
    role="Software development assistant",
    capabilities=["Write/review code", "Debug", ...],
    expertise=["Python", "JavaScript", "System design"],
    tone="professional",
    verbosity="detailed",
    constraints=["Include error handling", "Prefer readability"],
)
```

### RESEARCH_ASSISTANT_PERSONA

```python
PersonaBlock(
    name="Researcher",
    role="Research and analysis assistant",
    capabilities=["Synthesize info", "Compare options", ...],
    expertise=["Research methodology", "Data analysis"],
    tone="professional",
    verbosity="detailed",
)
```

---

## Integration with BaseAgent

```python
class BaseAgent:
    def __init__(self, ...):
        # Create agent with serialized memory
        agent = client.create_agent(
            memory_blocks=[
                {"label": "persona", "value": persona.to_memory_string()},
                {"label": "human", "value": human.to_memory_string()},
            ]
        )

        # Initialize manager
        self.memory = MemoryManager(client, agent.id)

    def update_context(self, task=None, note=None):
        if task:
            self.memory.set_task(task)
        if note:
            self.memory.add_context(note)

    def learn(self, preference=None, fact=None):
        if preference:
            self.memory.learn_preference(preference)
        if fact:
            self.memory.learn_fact(fact)
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CORE_MEMORY_MAX_CHARS` | `1500` | Max chars per block |
| `ARCHIVAL_ROTATION_THRESHOLD` | `0.8` | Default rotation threshold |

---

## Related Pages

- [[Agent-System]] - How agents use memory
- [[Configuration]] - Memory settings
- [[Letta-SDK]] - Letta memory API
