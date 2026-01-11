# Agent System

[[README|<- Back to Overview]]

YouLab uses Letta agents managed through `AgentManager` with TOML-based configuration.

## AgentManager

The `AgentManager` class manages per-user agents.

**Location**: `src/letta_starter/server/agents.py`

### Key Methods

```python
class AgentManager:
    async def create_agent(
        self,
        user_id: str,
        course_config: CourseConfig,
        user_name: str | None = None,
    ) -> AgentState:
        """Create a new agent from TOML course configuration."""

    async def get_or_create_agent(
        self,
        user_id: str,
        course_config: CourseConfig,
    ) -> AgentState:
        """Get existing agent or create new one."""

    async def send_message(
        self,
        user_id: str,
        message: str,
        course_config: CourseConfig,
    ) -> str:
        """Send message to user's agent."""
```

### Agent Naming

Agents use the pattern: `youlab_{user_id}_{course_id}`

### Creating Agents

Agents are created from TOML course configurations:

```python
from letta_starter.curriculum.loader import load_course_config
from letta_starter.server.agents import AgentManager

config = load_course_config("college-essay")
manager = AgentManager(letta_client)
agent = await manager.create_agent(user_id="user123", course_config=config)
```

See [[config-schema]] for TOML configuration format.

---

## Migration from Legacy APIs

> **Note**: The template-based agent creation is deprecated. Existing code should migrate to TOML-based configuration.

### Deprecated Modules

| Deprecated | Replacement |
|------------|-------------|
| `agents/templates.py` | `config/courses/*/course.toml` |
| `agents/default.py` | `AgentManager.create_agent()` |
| `agents/base.py` | Direct Letta agents via AgentManager |
| `memory/blocks.py` | TOML-defined blocks |

### Migration Steps

1. Define agent persona in `[agent.blocks.persona]` in course TOML
2. Use `AgentManager.create_agent()` with `CourseConfig`
3. Remove imports from deprecated modules

### Before (Deprecated)

```python
from letta_starter.agents.templates import TUTOR_TEMPLATE
from letta_starter.agents.default import create_custom_agent

agent = create_custom_agent(client, name="tutor", ...)
```

### After (Current)

```toml
# config/courses/my-course/course.toml
[agent]
type = "tutor"
system_prompt = "You are an AI tutor..."

[agent.blocks.persona]
label = "persona"
value = """
[IDENTITY] Course Coach | AI tutor
[CAPABILITIES] Guide students, Provide feedback
"""
```

```python
config = load_course_config("my-course")
agent = await manager.create_agent(user_id, config)
```

---

## Related Pages

- [[config-schema]] - TOML configuration format
- [[HTTP-Service]] - Agent endpoints
- [[Memory-System]] - Memory block concepts
- [[Letta-Integration]] - Letta SDK patterns
