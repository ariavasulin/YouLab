# Course Configuration Schema

This document describes the TOML configuration schema for YouLab courses.

## Schema Versions

**v2 (Current)** - Recommended format with merged `[agent]` section and simplified syntax.

**v1 (Legacy)** - Separate `[course]` + `[agent]` sections. See [Legacy v1 Schema](#legacy-v1-schema) for migration.

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

---

## course.toml Reference (v2)

### [agent] - Merged Course & Agent Configuration

In v2, the `[agent]` section combines course metadata with agent settings. This eliminates redundancy and makes configs more concise.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Unique course identifier (kebab-case) |
| name | string | yes | - | Display name |
| version | string | no | "1.0.0" | Semantic version |
| description | string | no | "" | Course description |
| modules | list[string] | no | [] | Module file names to load (without .toml) |
| model | string | no | "anthropic/claude-sonnet-4-20250514" | LLM model identifier |
| embedding | string | no | "openai/text-embedding-3-small" | Embedding model |
| context_window | int | no | 128000 | Context window size |
| max_response_tokens | int | no | 4096 | Maximum response tokens |
| system | string | no | "" | System prompt |
| tools | list[string] | no | [] | Tool list (see [Tools](#tools---tool-list)) |

**Example:**
```toml
[agent]
id = "college-essay"
name = "College Essay Coaching"
version = "1.0.0"
description = "AI-powered tutoring for college application essays"
modules = ["01-self-discovery", "02-topic-development", "03-drafting"]
model = "anthropic/claude-sonnet-4-20250514"
embedding = "openai/text-embedding-3-small"
context_window = 128000
max_response_tokens = 4096
system = """You are YouLab Essay Coach, an AI tutor specializing in college application essays.

Your approach:
- Guide students through self-discovery exercises
- Help brainstorm and develop essay topics
- Provide constructive feedback on drafts"""

tools = ["send_message", "query_honcho", "edit_memory_block"]
```

### tools - Tool List

v2 uses a simple string list for tools. Each tool uses its default rule from the registry, or you can override with `:rule` suffix.

**Registry Defaults:**
| Tool | Default Rule | Description |
|------|--------------|-------------|
| `send_message` | `exit` | Send a message to the user |
| `query_honcho` | `continue` | Query conversation history via Honcho dialectic |
| `edit_memory_block` | `continue` | Update a field in the agent's memory block |

**Rule Types:**
| Rule | Description |
|------|-------------|
| `exit` | Exit agent loop after this tool runs |
| `continue` | Continue agent loop after this tool |
| `first` | Run this tool first in the loop |

**Syntax:**
```toml
# Use default rules from registry
tools = ["send_message", "query_honcho", "edit_memory_block"]

# Override specific rules
tools = ["send_message:exit", "custom_tool:continue", "my_init:first"]
```

Unknown tools default to `continue` rule.

---

### [block.{name}] - Memory Block Schema

v2 uses `[block.{name}]` with `field.*` dotted keys for a more readable inline syntax.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| label | string | yes | - | Letta's internal block label (e.g., "persona", "human") |
| description | string | no | "" | Block description |
| shared | bool | no | false | Enable cross-agent memory sharing (see [Shared Blocks](#shared-blocks)) |
| field.{name} | FieldSchema | no | - | Field definitions (dotted key syntax) |

**FieldSchema:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| type | enum | - | Field type: `string`, `int`, `float`, `bool`, `list`, `datetime` |
| default | any | type-specific | Default value |
| options | list[string] | null | Valid values (for dropdowns) |
| max | int | null | Max items for lists |
| description | string | null | Field description |
| required | bool | false | Whether field is required |

**Example:**
```toml
[block.persona]
label = "persona"
shared = false
description = "Agent identity and behavior configuration"
field.name = { type = "string", default = "YouLab Essay Coach", description = "Agent's display name" }
field.role = { type = "string", default = "AI tutor specializing in college application essays" }
field.capabilities = { type = "list", default = ["Guide students", "Provide feedback"], max = 10 }
field.tone = { type = "string", default = "warm", options = ["warm", "professional", "friendly", "formal"] }
field.verbosity = { type = "string", default = "adaptive", options = ["concise", "detailed", "adaptive"] }

[block.human]
label = "human"
shared = false
description = "Student information and session context"
field.name = { type = "string", default = "", description = "Student's name" }
field.role = { type = "string", default = "" }
field.current_task = { type = "string", default = "" }
field.session_state = { type = "string", default = "idle", options = ["idle", "active_task", "waiting_input"] }
field.preferences = { type = "list", default = [], max = 10 }
field.facts = { type = "list", default = [], max = 20 }
```

### Shared Blocks

When `shared = true`, the block is created once and reused across all agents using the same course. This enables cross-agent memory sharing for team knowledge, organization context, etc.

**How it works:**
1. First agent creation for a course creates the shared block
2. Subsequent agents attach to the existing block (via `block_ids`)
3. Changes by any agent are visible to all agents sharing the block

**Use cases:**
- Team knowledge base
- Organization policies
- Shared context across tutors

**Example:**
```toml
[block.team]
label = "team"
shared = true
description = "Shared team knowledge across all tutors"
field.policies = { type = "list", default = [], max = 50 }
field.resources = { type = "list", default = [], max = 100 }
```

**Implementation:** See `AgentManager._get_or_create_shared_block()` in `src/letta_starter/server/agents.py:53-112`

---

### [[task]] - Background Tasks

v2 replaces `[background.{name}]` tables with a `[[task]]` array. This is more TOML-idiomatic for lists and simplifies the schema.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| schedule | string | null | Cron expression (e.g., "0 3 * * *") |
| manual | bool | true | Allow manual trigger |
| on_idle | bool | false | Trigger on user idle |
| idle_threshold_minutes | int | 30 | Minutes of idle before trigger |
| idle_cooldown_minutes | int | 60 | Cooldown between idle triggers |
| agent_types | list[string] | ["tutor"] | Agent types to process |
| user_filter | string | "all" | User filter expression |
| batch_size | int | 50 | Users per batch |
| queries | list[QueryConfig] | [] | Dialectic queries to run |
| system | string | null | Custom system prompt for task agent |
| tools | list[string] | [] | Additional tools for task agent |

**QueryConfig:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| target | string | - | Target in "block.field" format |
| question | string | - | Question to ask about conversation |
| scope | enum | "all" | Session scope: "all", "recent", "current", "specific" |
| recent_limit | int | 5 | Number of recent sessions (if scope is "recent") |
| merge | enum | "append" | Merge strategy: "append", "replace", "llm_diff" |

**Example:**
```toml
[[task]]
schedule = "0 3 * * *"  # 3 AM daily
manual = true
agent_types = ["tutor", "college-essay"]
user_filter = "all"
batch_size = 50
queries = [
    { target = "human.context_notes", question = "What learning style works best?", scope = "all", merge = "append" },
    { target = "human.facts", question = "How engaged is this student?", scope = "recent", recent_limit = 5, merge = "append" },
    { target = "persona.constraints", question = "How should I adjust my style?", scope = "all", merge = "llm_diff" }
]

[[task]]
schedule = "0 12 * * 0"  # Sundays at noon
manual = false
system = "You are an analytics agent that summarizes weekly progress."
tools = ["query_honcho"]
queries = [
    { target = "human.facts", question = "Summarize this week's progress", scope = "recent", recent_limit = 7, merge = "replace" }
]
```

---

### [messages] - UI Messages

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| welcome_first | string | "Hello! How can I help you today?" | First-time user greeting |
| welcome_returning | string | "Welcome back!" | Returning user greeting |
| error_unavailable | string | "I'm temporarily unavailable..." | Error message |

**Example:**
```toml
[messages]
welcome_first = "Welcome to YouLab! I'm your Essay Coach."
welcome_returning = "Welcome back! Ready to continue?"
error_unavailable = "I'm having a moment - please try again in a few seconds."
```

---

## Module File Reference

Module files define the curriculum structure with steps.

### [module] - Module Metadata

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Module identifier |
| name | string | yes | - | Display name |
| order | int | no | 0 | Sort order |
| description | string | no | "" | Module description |

### [[steps]] - Step Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| id | string | yes | - | Step identifier |
| name | string | yes | - | Display name |
| order | int | no | 0 | Sort order within module |
| description | string | no | "" | Step description |
| objectives | list[string] | no | [] | Learning objectives |

### [steps.completion] - Completion Criteria

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| required_fields | list[string] | [] | Fields that must be non-empty (e.g., "human.name") |
| min_turns | int | null | Minimum conversation turns |
| min_list_length | dict[string, int] | {} | Minimum items in list fields |
| auto_advance | bool | false | Auto-advance when complete |

### [steps.agent] - Step-Specific Agent Config

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| opening | string | null | Opening message for this step |
| focus | list[string] | [] | Topics to focus on |
| guidance | list[string] | [] | Guidance for the agent |
| persona_overrides | dict | {} | Override persona fields for this step |

**Example module file:**
```toml
[module]
id = "01-self-discovery"
name = "Self-Discovery"
order = 1
description = "Explore who you are and what matters to you"

[[steps]]
id = "welcome"
name = "Welcome & Onboarding"
order = 1
objectives = ["Learn student's name", "Set expectations"]

[steps.completion]
required_fields = ["human.name"]
min_turns = 3

[steps.agent]
opening = "Welcome! What's your name?"
focus = ["introduction", "goals"]
```

---

## API Endpoints

The curriculum system exposes HTTP endpoints for management:

- `GET /curriculum/courses` - List all courses
- `GET /curriculum/courses/{id}` - Get course summary
- `GET /curriculum/courses/{id}/full` - Get complete config as JSON
- `GET /curriculum/courses/{id}/modules` - Get modules with steps
- `POST /curriculum/reload` - Hot-reload all configurations

---

## Complete v2 Example

```toml
# =============================================================================
# AGENT CONFIGURATION (v2 schema - combines course + agent)
# =============================================================================

[agent]
id = "college-essay"
name = "College Essay Coaching"
version = "1.0.0"
description = "AI-powered tutoring for college application essays"
modules = ["01-self-discovery", "02-topic-development", "03-drafting"]
model = "anthropic/claude-sonnet-4-20250514"
system = """You are YouLab Essay Coach, an AI tutor."""
tools = ["send_message", "query_honcho", "edit_memory_block"]

# =============================================================================
# MEMORY BLOCKS (v2 format - field.* dotted keys)
# =============================================================================

[block.persona]
label = "persona"
description = "Agent identity and behavior"
field.name = { type = "string", default = "Essay Coach" }
field.tone = { type = "string", default = "warm", options = ["warm", "professional"] }
field.capabilities = { type = "list", default = ["Guide students"], max = 10 }

[block.human]
label = "human"
description = "Student information"
field.name = { type = "string", default = "" }
field.facts = { type = "list", default = [], max = 20 }

# =============================================================================
# BACKGROUND TASKS (v2 format - [[task]] array)
# =============================================================================

[[task]]
schedule = "0 3 * * *"
queries = [
    { target = "human.facts", question = "What motivates this student?", merge = "append" }
]

# =============================================================================
# UI MESSAGES
# =============================================================================

[messages]
welcome_first = "Welcome to YouLab!"
welcome_returning = "Welcome back!"
```

---

## Legacy v1 Schema

> **Deprecated**: v1 schema is supported for backwards compatibility but should be migrated to v2.

### Key Differences

| Feature | v1 | v2 |
|---------|----|----|
| Course metadata | `[course]` section | Merged into `[agent]` |
| Block syntax | `[blocks.x.fields.y]` nested tables | `[block.x]` with `field.y = {...}` |
| Tool config | `[[agent.tools]]` with explicit rules | `tools = ["name"]` with registry defaults |
| Background agents | `[background.name]` tables | `[[task]]` array |
| Shared blocks | Not supported | `shared = true` flag |

### v1 Example (Legacy)

```toml
# v1: Separate [course] and [agent] sections
[course]
id = "college-essay"
name = "College Essay Coaching"
modules = ["01-self-discovery"]

[agent]
model = "anthropic/claude-sonnet-4-20250514"
system = "You are an essay coach."

# v1: Explicit tool configuration
[[agent.tools]]
id = "send_message"
rules = { type = "exit_loop" }

[[agent.tools]]
id = "query_honcho"
rules = { type = "continue_loop" }

# v1: Nested block fields
[blocks.persona]
label = "persona"

[blocks.persona.fields]
name = { type = "string", default = "Essay Coach" }
tone = { type = "string", default = "warm" }

# v1: Named background agent sections
[background.insight-harvester]
enabled = true
agent_types = ["tutor"]

[background.insight-harvester.triggers]
schedule = "0 3 * * *"

[[background.insight-harvester.queries]]
id = "learning_style"
question = "What learning style works best?"
target_block = "human"
target_field = "context_notes"
merge_strategy = "append"
```

### Migration Guide

1. **Merge [course] into [agent]**: Move `id`, `name`, `version`, `description`, `modules` from `[course]` to `[agent]`

2. **Simplify tools**: Replace `[[agent.tools]]` with `tools = ["name", ...]`

3. **Update block syntax**: Change `[blocks.x.fields.y]` to `[block.x]` with `field.y = {...}`

4. **Convert background agents**: Replace `[background.name]` with `[[task]]` array

5. **Add shared flag**: For cross-agent blocks, add `shared = true`

The loader (`CurriculumLoader`) automatically detects and handles both formats.
