# Agent System

[[README|← Back to Overview]]

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

**Location**: `src/letta_starter/agents/templates.py`

### AgentTemplate Class

```python
class AgentTemplate(BaseModel):
    type_id: str          # Unique identifier ("tutor")
    display_name: str     # Human-readable ("College Essay Coach")
    description: str      # Template description
    persona: PersonaBlock # Agent identity
    human: HumanBlock     # Initial user context (usually empty)
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

# Register custom template
templates.register(my_template)
```

---

## Factory Functions

Factory functions create agents with pre-configured settings.

**Location**: `src/letta_starter/agents/default.py`

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

**Location**: `src/letta_starter/agents/base.py`

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

**Location**: `src/letta_starter/agents/default.py:160-261`

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
from letta_starter.agents.templates import AgentTemplate, templates
from letta_starter.memory.blocks import PersonaBlock, HumanBlock

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
