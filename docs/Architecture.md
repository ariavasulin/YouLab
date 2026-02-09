# Architecture

This document provides a deep technical overview of YouLab's architecture. It's written for developers and technical evaluators who want to understand how the system works.

## System Overview

YouLab is built around a simple principle: AI tutors should be transparent about what they know. The architecture reflects this through explicit data flows and version-controlled state.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            OpenWebUI                                    │
│                      (Chat Frontend + Auth)                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Ralph Pipe: Extracts user_id, chat_id, forwards to backend     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ POST /chat/stream (SSE)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Ralph Server                                   │
│                     (FastAPI + Agno Agent)                              │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Per-Request Agent                             │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │  Instructions:                                              │ │   │
│  │  │  • Base system prompt                                       │ │   │
│  │  │  • CLAUDE.md from workspace (if exists)                     │ │   │
│  │  │  • Memory blocks for this student                           │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │  Tools (workspace-scoped):                                  │ │   │
│  │  │  • FileTools    → read/write files in /workspace            │ │   │
│  │  │  • ShellTools   → execute commands in /workspace            │ │   │
│  │  │  • HonchoTools  → query conversation history                │ │   │
│  │  │  • MemoryBlockTools → propose profile edits                 │ │   │
│  │  │  • LaTeXTools   → generate PDF notes                        │ │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  API Routers    │  │  Background     │  │  Workspace Sync         │  │
│  │  • /blocks      │  │  Scheduler      │  │  • OpenWebUI KB ↔       │  │
│  │  • /background  │  │  • Cron tasks   │  │    Local files          │  │
│  │  • /workspace   │  │  • Idle tasks   │  │                         │  │
│  │  • /notes       │  │                 │  │                         │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘  │
│           │                    │                        │               │
└───────────┼────────────────────┼────────────────────────┼───────────────┘
            │                    │                        │
            ▼                    ▼                        ▼
┌───────────────────┐  ┌─────────────────┐  ┌────────────────────────────┐
│       Dolt        │  │     Honcho      │  │      OpenWebUI API         │
│  (Memory Blocks)  │  │  (Messages)     │  │    (Knowledge Base)        │
│                   │  │                 │  │                            │
│  • memory_blocks  │  │  • Persistence  │  │  • File upload/download    │
│  • background_*   │  │  • Dialectic    │  │  • KB management           │
│  • user_activity  │  │    queries      │  │                            │
│                   │  │                 │  │                            │
└───────────────────┘  └─────────────────┘  └────────────────────────────┘
```

## Request Lifecycle

### Chat Request Flow

When a student sends a message in OpenWebUI:

1. **OpenWebUI → Pipe** (`src/ralph/pipe.py:45-130`)
   - OpenWebUI invokes `Pipe.pipe()` with message body, user info, metadata, and event emitter
   - Pipe extracts `user_id` from `__user__["id"]` and `chat_id` from `__metadata__["chat_id"]`
   - Formats messages as `[{"role": "user", "content": "..."}]`

2. **Pipe → Server** (`src/ralph/pipe.py:86-104`)
   - Opens SSE connection to `POST /chat/stream`
   - Sends JSON payload: `{user_id, chat_id, messages}`
   - Receives and forwards SSE events to OpenWebUI

3. **Server: Agent Construction** (`src/ralph/server.py:167-297`)
   - Resolves workspace path (shared or per-user)
   - Loads `CLAUDE.md` from workspace if present
   - Builds memory context from Dolt blocks
   - Composes instructions: base + CLAUDE.md + memory
   - Creates fresh Agno agent with workspace-scoped tools

4. **Server: Execution** (`src/ralph/server.py:324-384`)
   - Persists user message to Honcho (fire-and-forget)
   - Streams agent response via `agent.arun(stream=True)`
   - Yields SSE events for each chunk
   - Persists assistant response to Honcho
   - Updates user activity timestamp in Dolt

5. **Pipe → OpenWebUI** (`src/ralph/pipe.py:132-167`)
   - Converts SSE events to OpenWebUI format
   - Status events show progress
   - Message events display response chunks
   - Done event completes the stream

### Key Design Decision: Per-Request Agents

Ralph creates a fresh agent for every chat request rather than maintaining stateful agents:

**Benefits**:
- No agent state to synchronize across requests
- Memory blocks are always fresh from Dolt
- Tools are scoped to current user's workspace
- Simpler error recovery (failed requests don't corrupt state)

**Trade-offs**:
- Can't maintain in-memory conversation context (relies on message history in request)
- Agent instantiation overhead per request (mitigated by fast Agno initialization)

## Data Stores

### Dolt: Version-Controlled Memory

Dolt is a MySQL-compatible database with git-like versioning. YouLab uses it for:

**Memory Blocks** (`memory_blocks` table)
```sql
CREATE TABLE memory_blocks (
    user_id VARCHAR(255) NOT NULL,
    label VARCHAR(100) NOT NULL,
    title VARCHAR(255),
    body TEXT,
    schema_ref VARCHAR(255),
    updated_at TIMESTAMP,
    PRIMARY KEY (user_id, label)
);
```

Every update creates a Dolt commit with author attribution. History is queryable via `dolt_history_memory_blocks`.

**Proposals as Branches**

When an agent proposes a memory block edit:
1. Creates branch `agent/{user_id}/{label}` from main
2. Commits proposed change to branch
3. Stores metadata (reasoning, confidence) in commit message as JSON
4. On approval: `DOLT_MERGE` → main
5. On rejection: `DOLT_BRANCH('-D')` deletes branch

This leverages Dolt's native branching rather than application-level state management.

**Background Tasks** (`background_tasks`, `task_runs`, `user_activity` tables)

Task definitions, execution history, and user activity tracking for idle triggers.

### Honcho: Conversation Memory

Honcho provides two capabilities:

**Message Persistence**
- Every message persisted with peer identity (student or tutor)
- Sessions scoped by `chat_{chat_id}`
- Metadata includes user_id and chat_id for correlation

**Dialectic Queries**
- Agents ask questions like "What has this student struggled with?"
- Honcho's backend processes conversation history through LLM
- Returns synthesized insights without exposing raw messages

Honcho enables cross-session memory without stuffing conversation history into prompts.

### Workspaces: Per-User Filesystems

Students get isolated workspaces:

```
/data/ralph/users/{user_id}/workspace/
├── essays/
│   └── draft-v1.md
├── notes/
│   └── research.md
└── CLAUDE.md  # Optional project instructions
```

**Workspace Modes**:
- **Isolated** (default): Each user gets their own workspace
- **Shared**: All users share a single workspace (set `RALPH_AGENT_WORKSPACE`)

FileTools and ShellTools are scoped to the workspace directory, preventing path traversal.

## Tool System

Agents are equipped with five toolkits:

### FileTools + ShellTools (Agno Built-in)

Standard file and shell operations scoped to workspace. Enable "Claude Code-like" capabilities for technical tutoring.

### HonchoTools (`src/ralph/tools/honcho_tools.py`)

**Tool**: `query_student(question: str) -> str`

Queries Honcho's dialectic API for insights about the current student. The tool extracts user_id from Agno's RunContext (injected via `dependencies` parameter).

### MemoryBlockTools (`src/ralph/tools/memory_blocks.py`)

**Tools**:
- `list_memory_blocks()` - Returns available block labels
- `read_memory_block(label)` - Returns block content as markdown
- `propose_memory_edit(label, old_string, new_string, reasoning)` - Creates proposal

The `propose_memory_edit` tool implements Claude Code-style surgical string replacement. It:
1. Validates `old_string` exists in current content
2. Checks uniqueness (or uses `replace_all=True`)
3. Creates Dolt branch with proposed change
4. Returns success message (agent never sees approval status)

### LaTeXTools (`src/ralph/tools/latex_tools.py`)

**Tool**: `render_notes(title: str, content: str) -> str`

Generates PDF from LaTeX content:
1. Writes LaTeX to temp file in workspace
2. Compiles with Tectonic (subprocess)
3. Base64 encodes PDF
4. Returns HTML with embedded PDF.js viewer

The HTML is returned in a code block that OpenWebUI renders as an artifact.

## Background Tasks

The background system enables scheduled and event-driven agent execution:

### Components

- **Registry** (`src/ralph/background/registry.py`): In-memory task definitions with Dolt persistence
- **Scheduler** (`src/ralph/background/scheduler.py`): Async loop checking triggers
- **Executor** (`src/ralph/background/executor.py`): Runs agents for users in batches

### Trigger Types

**CronTrigger**: Standard cron expressions
```python
CronTrigger(schedule="0 3 * * *")  # Daily at 3 AM
```

**IdleTrigger**: Fires after user inactivity
```python
IdleTrigger(idle_minutes=1440, cooldown_minutes=2880)  # 24h idle, 48h cooldown
```

Cooldown prevents repeated triggers for the same user.

### Execution Flow

1. Scheduler checks triggers every 60 seconds
2. For eligible tasks, queries Dolt for target users
3. Executor processes users in batches (default: 5 concurrent)
4. Each user gets fresh agent with task's system prompt and tools
5. Run history persisted to Dolt for auditability

## API Endpoints

### Chat API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/stream` | POST | Main chat endpoint with SSE streaming |
| `/health` | GET | Health check |

### Memory Blocks API (`/users/{user_id}/blocks`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | List all blocks with pending counts |
| `/{label}` | GET | Get single block |
| `/{label}` | PUT | Update block (user-initiated) |
| `/{label}` | DELETE | Delete block |
| `/{label}/history` | GET | Get version history |
| `/{label}/versions/{sha}` | GET | Get content at version |
| `/{label}/restore` | POST | Restore to previous version |
| `/{label}/diffs` | GET | Get pending proposals |
| `/{label}/propose` | POST | Create proposal (agent-initiated) |
| `/{label}/diffs/{id}/approve` | POST | Approve proposal |
| `/{label}/diffs/{id}/reject` | POST | Reject proposal |

### Background Tasks API (`/background`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tasks` | GET | List all tasks |
| `/tasks` | POST | Create/update task |
| `/tasks/{name}` | GET | Get task |
| `/tasks/{name}` | DELETE | Delete task |
| `/tasks/{name}/enable` | POST | Enable task |
| `/tasks/{name}/disable` | POST | Disable task |
| `/tasks/{name}/run` | POST | Trigger immediate execution |
| `/tasks/{name}/runs` | GET | List execution history |
| `/runs/{id}` | GET | Get run details |

### Workspace API (`/users/{user_id}/workspace`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/files` | GET | List workspace files |
| `/files/{path}` | GET | Download file |
| `/files/{path}` | PUT | Upload file |
| `/files/{path}` | DELETE | Delete file |
| `/sync` | POST | Trigger KB sync |

### Notes Adapter (`/api/you/notes`)

Bridges OpenWebUI's TipTap editor to Dolt memory blocks:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | List blocks as notes |
| `/{id}` | GET | Get note with version history |
| `/{id}/update` | POST | Update note content |

## Configuration

All Ralph settings use the `RALPH_` prefix and are loaded via Pydantic Settings:

**Required**:
- `RALPH_OPENROUTER_API_KEY` - API key for model access

**Model**:
- `RALPH_OPENROUTER_MODEL` - Model ID (default: `anthropic/claude-sonnet-4-20250514`)

**Storage**:
- `RALPH_USER_DATA_DIR` - Base for per-user data (default: `/data/ralph/users`)
- `RALPH_AGENT_WORKSPACE` - Shared workspace path (optional)

**Dolt**:
- `RALPH_DOLT_HOST`, `RALPH_DOLT_PORT`, `RALPH_DOLT_USER`, `RALPH_DOLT_PASSWORD`, `RALPH_DOLT_DATABASE`

**Honcho**:
- `RALPH_HONCHO_WORKSPACE_ID` - Workspace name (default: `ralph`)
- `RALPH_HONCHO_ENVIRONMENT` - Environment (default: `demo`)
- `RALPH_HONCHO_API_KEY` - API key (required for production)

**OpenWebUI Sync**:
- `RALPH_OPENWEBUI_URL` - OpenWebUI base URL
- `RALPH_OPENWEBUI_API_KEY` - API key for KB sync

## Project Structure

```
src/ralph/
├── __init__.py              # Exports Pipe for OpenWebUI
├── pipe.py                  # OpenWebUI pipe (HTTP client)
├── server.py                # FastAPI app + chat endpoint
├── config.py                # Pydantic settings
├── dolt.py                  # Dolt client (800+ lines)
├── memory.py                # Memory context builder
├── honcho.py                # Honcho client
│
├── api/
│   ├── blocks.py            # Memory blocks REST API
│   ├── background.py        # Background tasks API
│   ├── workspace.py         # Workspace file API
│   └── notes_adapter.py     # OpenWebUI notes bridge
│
├── tools/
│   ├── __init__.py          # Exports all toolkits
│   ├── memory_blocks.py     # MemoryBlockTools
│   ├── honcho_tools.py      # HonchoTools
│   └── latex_tools.py       # LaTeXTools
│
├── background/
│   ├── models.py            # Task, Run, Trigger models
│   ├── registry.py          # Task registration
│   ├── scheduler.py         # Trigger checking loop
│   ├── executor.py          # Agent execution
│   └── tools.py             # Tool factory for tasks
│
└── sync/
    ├── workspace_sync.py    # Bidirectional file sync
    ├── openwebui_client.py  # OpenWebUI API client
    ├── knowledge.py         # KB management
    └── models.py            # Sync state models
```

## Agent Configuration System

Agents are defined declaratively in TOML files. This enables course designers to create tutoring experiences without writing code.

### TOML Schema

Each course directory contains an `agents.toml` file:

```
config/courses/
├── college-essay/
│   └── agents.toml
├── math-tutoring/
│   └── agents.toml
└── cs-fundamentals/
    └── agents.toml
```

### Schema Structure

```toml
# =============================================================================
# AGENT DEFINITION
# =============================================================================
[agent]
name = "Agent Display Name"
model = "anthropic/claude-sonnet-4"  # OpenRouter model ID
system_prompt = """
Multi-line system prompt defining agent behavior.
"""

# Tools available to this agent
tools = [
  "file_tools",      # FileTools - read/write workspace files
  "shell_tools",     # ShellTools - execute commands
  "honcho_tools",    # HonchoTools - query conversation history
  "memory_blocks",   # MemoryBlockTools - read/propose block edits
  "latex_tools",     # LaTeXTools - generate PDF notes
]

# Memory blocks this agent can access
blocks = ["student", "progress", "notes"]


# =============================================================================
# MEMORY BLOCK SCHEMAS
# =============================================================================
[[block]]
label = "student"           # Unique identifier (used in Dolt)
title = "Student Profile"   # Display name
template = """
## About Me

[To be filled in as we learn about you]

## Learning Style

[How you prefer to learn]
"""

[[block]]
label = "progress"
title = "Progress Tracker"
template = """
## Current Module

## Completed

## Struggling With
"""


# =============================================================================
# BACKGROUND TASKS
# =============================================================================
[[task]]
name = "daily-review"
trigger = { type = "cron", schedule = "0 3 * * *" }  # Cron expression
system_prompt = """
Task-specific instructions for background agent.
"""
tools = ["honcho_tools", "memory_blocks"]
blocks = ["student", "progress"]

[[task]]
name = "idle-engagement"
trigger = { type = "idle", idle_minutes = 1440, cooldown_minutes = 2880 }
system_prompt = """
Re-engage student after inactivity.
"""
tools = ["honcho_tools", "file_tools"]
blocks = ["student"]
```

### Compilation and Validation

At startup, the system:

1. **Scans** `config/courses/*/agents.toml` for all course definitions
2. **Validates** each file against the schema
3. **Detects conflicts**: If two courses define `[[block]]` with the same label but different schemas, startup fails with an error
4. **Registers** agents, blocks, and tasks in the runtime registry

### Block Resolution

When a user first interacts with a course:

1. Check if user already has the block (from another course or previous session)
2. If exists: Use existing content (preserves cross-course continuity)
3. If not: Initialize from template in `[[block]]` definition
4. If no `[[block]]` definition exists: Error (block must be defined somewhere)

This enables patterns like:

```toml
# college-essay/agents.toml - DEFINES the student block
blocks = ["student", "essays"]

[[block]]
label = "student"
template = "..."

# math-tutoring/agents.toml - USES the student block (no redefinition)
blocks = ["student", "math-progress"]

[[block]]
label = "math-progress"
template = "..."
```

Both tutors see the same "student" block, enabling shared context across domains.

### Tool Registration

Tools are registered by string ID and resolved at agent creation:

| Tool ID | Class | Capabilities |
|---------|-------|--------------|
| `file_tools` | `FileTools` | Read, write, list files in workspace |
| `shell_tools` | `ShellTools` | Execute shell commands in workspace |
| `honcho_tools` | `HonchoTools` | Query student's conversation history |
| `memory_blocks` | `MemoryBlockTools` | List, read, propose edits to blocks |
| `latex_tools` | `LaTeXTools` | Render LaTeX to PDF |

Custom tools can be registered by adding to the tool registry.

### Task Triggers

**CronTrigger**: Standard cron expressions
```toml
trigger = { type = "cron", schedule = "0 9 * * 1" }  # Monday 9 AM
```

**IdleTrigger**: Fires after user inactivity
```toml
trigger = { type = "idle", idle_minutes = 4320, cooldown_minutes = 10080 }
```
- `idle_minutes`: Time since last user activity before triggering
- `cooldown_minutes`: Minimum time between triggers for same user

## Evolution from Legacy

YouLab evolved from a Letta-based architecture (`src/youlab_server/`):

| Aspect | Legacy (Letta) | Current (Ralph/Agno) |
|--------|----------------|----------------------|
| Agent Framework | Letta | Agno |
| Memory Storage | Git repos + Letta blocks | Dolt database |
| Configuration | Complex TOML courses | Simplified `agents.toml` |
| Diff Workflow | JSON files | Dolt branches |
| Tools | Custom Letta tools | Agno toolkits |
| Background | Multi-agent orchestration | Simple scheduler with TOML tasks |

**Why the change?**

The Letta architecture provided powerful primitives (archival memory, tool execution, structured blocks) but added complexity:
- Separate Letta server to manage
- Complex memory rotation strategies
- TOML configuration sprawl
- Multiple abstraction layers

Ralph simplifies to:
- Single FastAPI server
- Per-request agents (no state management)
- Workspace files + Dolt blocks
- Direct tool execution

The core insight—transparent, user-controlled memory—remains. The implementation became simpler.

## Related Documentation

- [README](README.md) - Overview and quickstart
- [API Reference](API.md) - Detailed endpoint documentation
- [Configuration](Configuration.md) - Full environment variable reference
- [Development](Development.md) - Contributing guide
