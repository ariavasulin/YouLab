# Memory System

[[README|<- Back to Overview]]

YouLab agents use Letta's two-tier memory architecture with blocks defined in TOML configuration.

## Architecture

```
+-----------------------------------------+
|        Core Memory (In-Context)         |
|  Always visible in every prompt         |
|  - persona block (agent identity)       |
|  - human block (user context)           |
|  - custom blocks from TOML              |
+-----------------------------------------+
                  |
                  | Agent-driven rotation
                  v
+-----------------------------------------+
|     Archival Memory (Vector DB)         |
|  Semantic search on-demand              |
|  - Unlimited capacity                   |
|  - Historical context                   |
+-----------------------------------------+
```

## Defining Memory Blocks

Memory blocks are defined in course TOML files:

```toml
# config/courses/my-course/course.toml

[agent.blocks.persona]
label = "persona"
description = "Agent identity and capabilities"
value = """
[IDENTITY] Essay Coach | AI tutor
[CAPABILITIES] Guide discovery, Brainstorm topics
[STYLE] warm, adaptive
"""

[agent.blocks.human]
label = "human"
description = "User context, updated during conversations"
value = """
[USER] {name} | Student
[TASK] None
[STATE] idle
"""
```

See [[config-schema]] for full TOML schema.

## Agent-Driven Memory

Agents update their own memory using the `edit_memory_block` tool:

```python
# Agent can call this tool during conversations
edit_memory_block(
    block_label="human",
    action="replace",
    old_content="[TASK] None",
    new_content="[TASK] Essay brainstorming"
)
```

## Memory Block Format

YouLab uses a token-efficient bracket notation:

```
[IDENTITY] YouLab Coach | AI tutor for college essays
[CAPABILITIES] Guide discovery; Brainstorm topics; Provide feedback
[STYLE] warm, adaptive
[CONSTRAINTS] Never write essays for students
```

This format:
- Maximizes information density
- Is easily parseable by agents
- Fits within Letta's ~2000 char block limit

---

## Migration from Legacy APIs

> **Note**: `MemoryManager`, `PersonaBlock`, and `HumanBlock` classes are deprecated.

| Deprecated | Replacement |
|------------|-------------|
| `memory/manager.py` | Agent-driven via `edit_memory_block` tool |
| `memory/blocks.py` | TOML-defined blocks |
| `memory/strategies.py` | Not needed with agent-driven memory |

---

## Related Pages

- [[config-schema]] - TOML block definitions
- [[Agent-System]] - Agent management
- [[Letta-Integration]] - Letta memory concepts
