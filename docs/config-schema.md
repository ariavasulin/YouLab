# Course Configuration Schema

This document describes the TOML configuration schema for YouLab courses.

> **Note**: TOML configuration replaces the deprecated Python-based approach (`PersonaBlock`, `HumanBlock`, `AgentTemplate`). See [[Agent-System#Migration Guide]] for migration details.

## Design Principles

- **Self-contained**: Each course.toml is complete without external references
- **Explicit**: All configuration is visible in the file
- **AI-friendly**: Easy to read and modify programmatically
- **UI-ready**: Schema is introspectable for visual editors

## File Structure

```
config/courses/{course-id}/
├── course.toml          # Main course configuration
└── modules/
    ├── 01-module-name.toml
    └── 02-module-name.toml
```

## course.toml Reference

### [course] - Course Metadata

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Unique identifier (kebab-case) |
| name | string | yes | - | Display name |
| version | string | no | "1.0.0" | Semantic version |
| description | string | no | "" | Course description |
| modules | list[string] | yes | - | Module file names to load (without .toml) |

Example:
```toml
[course]
id = "college-essay"
name = "College Essay Coaching"
version = "1.0.0"
description = "AI-powered tutoring for college application essays"
modules = ["01-self-discovery", "02-topic-development", "03-drafting"]
```

### [agent] - Agent Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| model | string | "anthropic/claude-sonnet-4-20250514" | LLM model identifier |
| embedding | string | "openai/text-embedding-3-small" | Embedding model |
| context_window | int | 128000 | Context window size |
| max_response_tokens | int | 4096 | Maximum response tokens |
| system | string | "" | System prompt |

Example:
```toml
[agent]
model = "anthropic/claude-sonnet-4-20250514"
embedding = "openai/text-embedding-3-small"
system = """You are a helpful assistant."""
```

### [[agent.tools]] - Tool Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| id | string | - | Tool identifier |
| enabled | bool | true | Whether tool is enabled |
| rules.type | enum | "continue_loop" | Tool rule type |
| rules.max_count | int | null | Maximum invocation count |

**Rule Types:**
- `exit_loop` - Exit agent loop after this tool runs
- `continue_loop` - Continue agent loop after this tool
- `run_first` - Run this tool first in the loop

Example:
```toml
[[agent.tools]]
id = "send_message"
rules = { type = "exit_loop" }

[[agent.tools]]
id = "query_honcho"
rules = { type = "continue_loop" }
```

### [blocks.{name}] - Memory Block Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| label | string | yes | Letta's internal block label (e.g., "persona", "human") |
| description | string | no | Block description |

Example:
```toml
[blocks.persona]
label = "persona"
description = "Agent identity and behavior configuration"
```

### [blocks.{name}.fields.{field}] - Field Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| type | enum | - | Field type (see below) |
| default | any | type-specific | Default value |
| options | list[string] | null | Valid values (for dropdowns) |
| max | int | null | Max items for lists |
| description | string | null | Field description |
| required | bool | false | Whether field is required |

**Field Types:**
- `string` - Text value (default: "")
- `int` - Integer (default: 0)
- `float` - Floating point (default: 0.0)
- `bool` - Boolean (default: false)
- `list` - List of strings (default: [])
- `datetime` - ISO datetime (default: null)

Example:
```toml
[blocks.persona.fields]
name = { type = "string", default = "Assistant", description = "Agent's name" }
tone = { type = "string", default = "warm", options = ["warm", "professional", "friendly"] }
capabilities = { type = "list", default = [], max = 10 }
```

### Complete Block Examples

**Persona Block** (replaces deprecated `PersonaBlock`):
```toml
[blocks.persona]
label = "persona"
description = "Agent identity and behavior"

[blocks.persona.fields]
name = { type = "string", default = "Essay Coach" }
role = { type = "string", default = "AI tutor specializing in college application essays" }
tone = { type = "string", default = "warm", options = ["warm", "professional", "friendly", "casual"] }
verbosity = { type = "string", default = "adaptive", options = ["concise", "detailed", "adaptive"] }
capabilities = { type = "list", default = ["Guide students", "Provide feedback", "Ask clarifying questions"], max = 10 }
expertise = { type = "list", default = ["College admissions", "Personal narrative", "Reflective writing"], max = 5 }
constraints = { type = "list", default = ["Never write essays for students"], max = 5 }
```

**Human Block** (replaces deprecated `HumanBlock`):
```toml
[blocks.human]
label = "human"
description = "User context and session state"

[blocks.human.fields]
name = { type = "string", default = "" }
role = { type = "string", default = "" }
current_task = { type = "string", default = "" }
session_state = { type = "string", default = "idle", options = ["idle", "active_task", "waiting_input", "thinking"] }
preferences = { type = "list", default = [], max = 10 }
context_notes = { type = "list", default = [], max = 20 }
facts = { type = "list", default = [], max = 15 }
```

### [background.{agent-id}] - Background Agent Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | true | Whether agent is enabled |
| agent_types | list[string] | ["tutor"] | Agent types to process |
| user_filter | string | "all" | User filter expression |
| batch_size | int | 50 | Users per batch |

Example:
```toml
[background.insight-harvester]
enabled = true
agent_types = ["tutor"]
batch_size = 50
```

### [background.{agent-id}.triggers] - Trigger Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| schedule | string | null | Cron expression |
| manual | bool | true | Allow manual trigger |
| after_messages | int | null | Trigger after N messages |

**Idle Trigger:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | false | Enable idle trigger |
| threshold_minutes | int | 30 | Minutes of idle before trigger |
| cooldown_minutes | int | 60 | Cooldown between triggers |

Example:
```toml
[background.insight-harvester.triggers]
schedule = "0 3 * * *"  # 3 AM daily
manual = true

[background.insight-harvester.triggers.idle]
enabled = false
threshold_minutes = 30
```

### [[background.{agent-id}.queries]] - Dialectic Queries

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| id | string | - | Unique query identifier |
| question | string | - | Question to ask about conversation |
| session_scope | enum | "all" | Scope: "all", "recent", "current", "specific" |
| recent_limit | int | 5 | Number of recent sessions (if scope is "recent") |
| target_block | string | - | Memory block to update |
| target_field | string | - | Field within block to update |
| merge_strategy | enum | "append" | How to merge: "append", "replace", "llm_diff" |

Example:
```toml
[[background.insight-harvester.queries]]
id = "learning_style"
question = "What learning style works best for this student?"
session_scope = "all"
target_block = "human"
target_field = "context_notes"
merge_strategy = "append"
```

### [messages] - UI Messages

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| welcome_first | string | "Hello! How can I help you today?" | First-time user greeting |
| welcome_returning | string | "Welcome back!" | Returning user greeting |
| error_unavailable | string | "I'm temporarily unavailable..." | Error message |

Example:
```toml
[messages]
welcome_first = "Welcome to YouLab! I'm your Essay Coach."
welcome_returning = "Welcome back! Ready to continue?"
```

## Module File Reference

Module files define the curriculum structure with lessons.

### [module] - Module Metadata

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Module identifier |
| name | string | yes | - | Display name |
| order | int | no | 0 | Sort order |
| description | string | no | "" | Module description |

### [module.background.{agent-id}] - Module-Level Background Overrides

Modules can override background agent configuration for module-specific behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| enabled | bool | inherited | Override enabled status |
| queries | array | inherited | Override or extend queries |

### [[lessons]] - Lesson Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Lesson identifier |
| name | string | yes | - | Display name |
| order | int | no | 0 | Sort order within module |
| description | string | no | "" | Lesson description |
| objectives | list[string] | no | [] | Learning objectives |

### [lessons.completion] - Completion Criteria

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| required_fields | list[string] | [] | Fields that must be non-empty (e.g., "human.name") |
| min_turns | int | null | Minimum conversation turns |
| min_list_length | dict[string, int] | {} | Minimum items in list fields |
| auto_advance | bool | false | Auto-advance when complete |

### [lessons.agent] - Lesson-Specific Agent Config

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| opening | string | null | Opening message for this lesson |
| focus | list[string] | [] | Topics to focus on |
| guidance | list[string] | [] | Guidance for the agent |
| persona_overrides | dict | {} | Override persona fields for this lesson |

Example module file:
```toml
[module]
id = "01-self-discovery"
name = "Self-Discovery"
order = 1

[[lessons]]
id = "welcome"
name = "Welcome & Onboarding"
order = 1
objectives = ["Learn student's name", "Set expectations"]

[lessons.completion]
required_fields = ["human.name"]
min_turns = 3

[lessons.agent]
opening = "Welcome! What's your name?"
focus = ["introduction", "goals"]
```

## API Endpoints

The curriculum system exposes HTTP endpoints for management:

- `GET /curriculum/courses` - List all courses
- `GET /curriculum/courses/{id}` - Get course summary
- `GET /curriculum/courses/{id}/full` - Get complete config as JSON
- `GET /curriculum/courses/{id}/modules` - Get modules with lessons
- `POST /curriculum/reload` - Hot-reload all configurations
