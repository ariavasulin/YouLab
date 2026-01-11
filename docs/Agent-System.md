# Agent System

[[README|← Back to Overview]]

> **Note**: The template-based agent creation (`AgentTemplate`, factory functions, `BaseAgent`) is deprecated. New code should use `AgentManager.create_agent()` which loads configuration from TOML files in `config/courses/`.

## Migration Guide

The agent system has migrated from Python-based templates to TOML-based configuration.

### Before (Deprecated)

```python
# Old approach - templates.py
from youlab_server.agents.templates import TUTOR_TEMPLATE, templates
from youlab_server.agents.default import create_custom_agent
from youlab_server.memory.blocks import PersonaBlock, HumanBlock

agent = create_custom_agent(
    client=letta_client,
    name="tutor",
    role="AI tutor",
    capabilities=["Guide students", "Provide feedback"],
    ...
)
```

### After (Recommended)

```toml
# config/courses/my-course/course.toml
[agent]
type = "tutor"
display_name = "My Course Coach"
system_prompt = "You are an AI tutor..."

[agent.blocks.persona]
name = "persona"
label = "Persona"
value = """
[IDENTITY] Course Coach | AI tutor
[CAPABILITIES] Guide students, Provide feedback
[STYLE] warm, adaptive
"""
```

```python
# Python code - use AgentManager
from youlab_server.server.agents import AgentManager
from youlab_server.curriculum.loader import load_course_config

config = load_course_config("my-course")
agent_manager = AgentManager(letta_client)
agent_state = await agent_manager.create_agent(
    user_id="user123",
    course_config=config,
)
```

### Migration Steps

1. **Convert PersonaBlock to TOML blocks**: Define your agent's persona as a `[agent.blocks.persona]` section in your course TOML file
2. **Replace factory functions**: Use `AgentManager.create_agent()` instead of `create_*_agent()` functions
3. **Update imports**: Remove imports from deprecated modules (`agents/templates`, `agents/default`, `agents/base`, `memory/blocks`, `memory/manager`)
4. **Use curriculum loader**: Load configuration via `load_course_config()` from `curriculum/loader.py`

### Deprecated Modules

| Deprecated Module | Replacement |
|-------------------|-------------|
| `agents/templates.py` | `config/courses/*/course.toml` |
| `agents/default.py` | `AgentManager.create_agent()` |
| `agents/base.py` | Direct Letta agents via AgentManager |
| `memory/blocks.py` (PersonaBlock/HumanBlock) | TOML-defined blocks |
| `memory/manager.py` | Agent-driven memory via `edit_memory_block` tool |
| `memory/strategies.py` | Not needed with agent-driven memory |

These modules emit `DeprecationWarning` on import and will be removed in a future version.

---

## AgentManager (Recommended)

The `AgentManager` class is the recommended way to create and manage agents.

**Location**: `src/youlab_server/server/agents.py`

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

    async def delete_agent(self, user_id: str, course_id: str) -> bool:
        """Delete user's agent."""
```

### Agent Naming Convention

Agents are named using the pattern: `youlab_{user_id}_{course_id}`

This allows each user to have separate agents for different courses.

---

## Legacy Documentation

> **Warning**: The following sections document deprecated APIs. They are kept for reference during migration but should not be used in new code.

The agent system provides templates, factories, and runtime management for Letta agents.

## Overview

```
┌───────────────────────────────────────────────────────────────┐
│                     AgentTemplateRegistry                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   tutor     │  │   coding    │  │  research   │  ...      │
│  │  Template   │  │  Template   │  │  Template   │           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │
└─────────┼────────────────┼───────────────┼───────────────────┘
          │                │               │
          ▼                ▼               ▼
┌───────────────────────────────────────────────────────────────┐
│                      Factory Functions                         │
│  create_default_agent()  create_coding_agent()  create_...()  │
└─────────────────────────────┬─────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│                        BaseAgent                               │
│  • Integrated memory management (MemoryManager)               │
│  • Observability (Tracer, structlog)                          │
│  • Message handling with Letta SDK                            │
└─────────────────────────────────┬─────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────┐
│                      AgentRegistry                             │
│  • Multi-agent coordination                                    │
│  • Named agent storage and retrieval                          │
└───────────────────────────────────────────────────────────────┘
```

## Agent Templates

Templates define agent types with pre-configured personas.

**Location**: `src/youlab_server/agents/templates.py`

### AgentTemplate Class

```python
class AgentTemplate(BaseModel):
    type_id: str          # Unique identifier ("tutor")
    display_name: str     # Human-readable ("College Essay Coach")
    description: str      # Template description
    persona: PersonaBlock # Agent identity
    human: HumanBlock     # Initial user context (usually empty)
    tools: list[Callable] # Tool functions available to agent
```

### TUTOR_TEMPLATE

The primary template for college essay coaching:

```python
TUTOR_TEMPLATE = AgentTemplate(
    type_id="tutor",
    display_name="College Essay Coach",
    description="Primary tutor for college essay writing course",
    persona=PersonaBlock(
        name="YouLab Essay Coach",
        role="AI tutor specializing in college application essays",
        capabilities=[
            "Guide students through self-discovery exercises",
            "Help brainstorm and develop essay topics",
            "Provide constructive feedback on drafts",
            "Support emotional journey of college applications",
        ],
        expertise=[
            "College admissions",
            "Personal narrative",
            "Reflective writing",
            "Strengths-based coaching",
        ],
        tone="warm",
        verbosity="adaptive",
        constraints=[
            "Never write essays for students",
            "Always ask clarifying questions before giving advice",
            "Celebrate small wins and progress",
        ],
    ),
    human=HumanBlock(),  # Empty, filled during onboarding
)
```

### AgentTemplateRegistry

Global registry for templates:

```python
templates = AgentTemplateRegistry()

# Get template
template = templates.get("tutor")

# List all types
types = templates.list_types()  # ["tutor"]

# Get all templates
all_templates = templates.get_all()  # {"tutor": AgentTemplate(...)}

# Register custom template
templates.register(my_template)
```

---

## Factory Functions

Factory functions create agents with pre-configured settings.

**Location**: `src/youlab_server/agents/default.py`

### Available Factories

| Function | Persona | Use Case |
|----------|---------|----------|
| `create_default_agent()` | General assistant | Default conversations |
| `create_coding_agent()` | Code helper | Development tasks |
| `create_research_agent()` | Researcher | Analysis and synthesis |
| `create_custom_agent()` | Custom | Fully configurable |

### create_default_agent

```python
agent = create_default_agent(
    client=letta_client,
    name="my-agent",
    tracer=optional_tracer,
)
```

Uses `DEFAULT_PERSONA`:
- Name: "Assistant"
- Tone: "friendly"
- Verbosity: "adaptive"

### create_coding_agent

```python
agent = create_coding_agent(
    client=letta_client,
    name="code-helper",
    tracer=optional_tracer,
)
```

Uses `CODING_ASSISTANT_PERSONA`:
- Name: "CodeHelper"
- Expertise: Python, JavaScript, System design, Testing
- Constraints: Include error handling, prefer readability

Pre-configures preferences:
- "Type hints in code"
- "Detailed explanations"

### create_research_agent

```python
agent = create_research_agent(
    client=letta_client,
    name="researcher",
    tracer=optional_tracer,
)
```

Uses `RESEARCH_ASSISTANT_PERSONA`:
- Name: "Researcher"
- Expertise: Research methodology, Data analysis, Critical thinking

Pre-configures preferences:
- "Thorough analysis"
- "Cited sources"

### create_custom_agent

Fully customizable:

```python
agent = create_custom_agent(
    client=letta_client,
    name="custom-agent",
    role="Custom agent role",
    capabilities=["Capability 1", "Capability 2"],
    expertise=["Domain 1", "Domain 2"],
    tone="professional",
    verbosity="concise",
    constraints=["Constraint 1"],
    user_name="Alice",
    user_role="Student",
    tracer=optional_tracer,
)
```

---

## BaseAgent

The core agent class with integrated memory and observability.

**Location**: `src/youlab_server/agents/base.py`

### Initialization

```python
agent = BaseAgent(
    name="my-agent",
    persona=my_persona_block,
    human=my_human_block,
    client=letta_client,
    tracer=optional_tracer,
    max_memory_chars=1500,
)
```

On init:
1. Serialize memory blocks
2. Create agent in Letta (or retrieve existing)
3. Initialize MemoryManager
4. Log initialization

### Core Methods

#### send_message

```python
response = agent.send_message(
    message="Help me brainstorm essay topics",
    session_id="session-123",
)
```

Flow:
1. Log "message_received"
2. Wrap in `tracer.trace_llm_call()`
3. Call `_send_message_internal()`
4. Extract token usage for metrics
5. Extract response text
6. Log "message_sent"
7. Return text

#### update_context

```python
agent.update_context(
    task="Brainstorm essay topics",
    note="Student interested in identity themes",
)
```

Updates the human block via MemoryManager.

#### learn

```python
agent.learn(
    preference="Prefers Socratic questions",
    fact="Studies computer science",
)
```

Records learned information in human block.

#### get_memory_summary

```python
summary = agent.get_memory_summary()
# Returns:
# {
#     "agent_id": "...",
#     "persona_usage": "45.2%",
#     "human_usage": "62.1%",
#     "session_state": "active_task",
#     "current_task": "Brainstorm topics",
#     ...
# }
```

#### search_memory

```python
results = agent.search_memory(
    query="essay topics discussed",
    limit=5,
)
# Returns list of matching archival entries
```

---

## AgentRegistry

Manages multiple agent instances.

**Location**: `src/youlab_server/agents/default.py:160-261`

### Usage

```python
registry = AgentRegistry(client, tracer)

# Create and register
agent = registry.create_and_register(
    name="coding-assistant",
    agent_type="coding",
)

# Get agent
agent = registry.get("coding-assistant")

# List all
names = registry.list_agents()

# Remove
removed = registry.remove("coding-assistant")

# Count
count = len(registry)

# Check existence
if "coding-assistant" in registry:
    ...
```

### Supported Agent Types

| Type | Factory Used |
|------|--------------|
| `"default"` | `create_default_agent()` |
| `"coding"` | `create_coding_agent()` |
| `"research"` | `create_research_agent()` |

---

## HTTP Service Integration

The HTTP service uses `AgentManager` (different from `AgentRegistry`):

```python
# AgentManager for HTTP service
class AgentManager:
    # Naming convention
    def _agent_name(user_id, agent_type):
        return f"youlab_{user_id}_{agent_type}"

    # Creates from template
    def create_agent(user_id, agent_type="tutor", user_name=None):
        template = templates.get(agent_type)
        # ... creates via Letta SDK
```

Key differences:

| AgentRegistry | AgentManager |
|---------------|--------------|
| Multi-agent coordination | Per-user agent management |
| Named agents | User/type-based naming |
| In-memory storage | Letta storage + cache |
| For library use | For HTTP service |

---

## Creating Custom Templates

```python
from youlab_server.agents.templates import AgentTemplate, templates
from youlab_server.memory.blocks import PersonaBlock, HumanBlock

# Define template
MY_TEMPLATE = AgentTemplate(
    type_id="counselor",
    display_name="College Counselor",
    description="Specialized counselor for college admissions",
    persona=PersonaBlock(
        name="Counselor",
        role="College admissions counselor",
        capabilities=[...],
        expertise=[...],
        tone="supportive",
        verbosity="detailed",
        constraints=[...],
    ),
    human=HumanBlock(),
)

# Register
templates.register(MY_TEMPLATE)

# Use
template = templates.get("counselor")
```

---

## Related Pages

- [[Memory-System]] - Memory blocks and strategies
- [[HTTP-Service]] - AgentManager for web service
- [[Letta-SDK]] - Underlying SDK patterns
