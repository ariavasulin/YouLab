# YouLab Platform

Introspective AI tutoring platform that learns about students and self-manages context through memory blocks and theory-of-mind modeling.

## Architecture Overview

**Current State**: The project has two parallel implementations:

1. **Legacy Stack** (`src/youlab_server/`) - Letta-based, fully featured but being phased out
2. **Ralph MVP** (`src/ralph/`) - New Agno-based greenfield implementation, actively developed

### Ralph Flow (New Architecture)

Ralph provides a "Claude Code-like" experience: OpenWebUI chat → Agno Agent with file/shell tools.

```
OpenWebUI → Ralph Pipe (HTTP client) → Ralph Server (FastAPI) → Agno Agent → OpenRouter API
                                                                     ↓
                                                              FileTools + ShellTools
                                                                     ↓
                                                              User Workspace
```

**Key Components**:
- **Ralph Pipe** (`src/ralph/pipe.py`): Lightweight HTTP client for OpenWebUI, streams SSE events from Ralph server
- **Ralph Server** (`src/ralph/server.py`): FastAPI backend that creates Agno agents per-request with workspace-scoped tools
- **Agno Agent**: Uses `agno.agent.Agent` with OpenRouter model and `FileTools`/`ShellTools` scoped to user workspace
- **Honcho Client** (`src/ralph/honcho.py`): Message persistence and dialectic queries for student insights

**Data Flow**:
1. User sends message in OpenWebUI
2. Pipe extracts user_id, chat_id, and full message history
3. Pipe POSTs to Ralph server `/chat/stream` endpoint
4. Server creates Agno agent with workspace tools and CLAUDE.md instructions
5. Agent streams response via SSE with status updates
6. Pipe forwards events to OpenWebUI event emitter

### Legacy Stack (Being Phased Out)

```
OpenWebUI → Letta Pipe → YouLab Server (FastAPI) → Letta Server → Claude API
                              ↘ Honcho (message persistence)
```

The legacy stack in `src/youlab_server/` uses Letta for agents, curriculum TOML configs, memory blocks, background agents, and git-based storage with diff approval workflows. This is being replaced by Ralph.

## Project Structure

```
src/ralph/                   # NEW: Agno-based MVP (active development)
  __init__.py                # Exports Pipe
  pipe.py                    # OpenWebUI Pipe (HTTP client to Ralph server)
  server.py                  # FastAPI backend with Agno agent
  honcho.py                  # Honcho client for message persistence
  config.py                  # Pydantic settings (RALPH_* env vars)
  tools/                     # Custom tools
    query_honcho.py          # Honcho dialectic query tool

src/youlab_server/           # LEGACY: Letta-based backend (being phased out)
  agents/                    # BaseAgent + factories (deprecated)
  memory/                    # Memory blocks, rotation strategies (deprecated)
  pipelines/                 # OpenWebUI Pipe for Letta
  server/                    # FastAPI HTTP service
  honcho/                    # Honcho client
  tools/                     # Agent tools (sandbox-compatible versions)
  background/                # Background agent runner
  curriculum/                # TOML course config system
  storage/                   # Git-based user storage with diffs
  observability/             # Logging, metrics, tracing (Langfuse)
  config/                    # Pydantic settings

config/courses/              # TOML course configs (legacy)
OpenWebUI/open-webui/        # Nested git repo (NOT a submodule)
```

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Ralph (new stack)
uv run ralph-server              # Start Ralph HTTP backend on port 8200

# Legacy (being phased out)
uv run youlab                    # Interactive mode (requires letta server)
uv run youlab-server             # Start YouLab HTTP service (requires letta server)

# Verification (agent-optimized, minimal output)
make verify-agent                # Full: lint + typecheck + tests
make check-agent                 # Quick: lint + typecheck only
make test-agent                  # Pytest only (no coverage)

# Individual tools
make lint-fix                    # Auto-fix lint issues

# Ralph-specific checks (from project root)
uv run ruff check src/ralph/
uv run basedpyright src/ralph/
```

Pre-commit hooks run `make verify` automatically - commits are blocked if checks fail.

## Environment Variables (Ralph)

```bash
RALPH_OPENROUTER_API_KEY=...     # Required: OpenRouter API key
RALPH_OPENROUTER_MODEL=anthropic/claude-sonnet-4-20250514  # Default model
RALPH_AGENT_WORKSPACE=/path/to/workspace  # Shared workspace (optional)
RALPH_USER_DATA_DIR=/data/ralph/users     # Per-user workspaces
RALPH_HONCHO_WORKSPACE_ID=ralph           # Honcho workspace
RALPH_HONCHO_ENVIRONMENT=demo             # demo, local, or production
```

## Codebase Patterns

- Use `model_config = {"env_prefix": "..."}` instead of nested `class Config` for Pydantic Settings
- OpenWebUI pipe docstrings need proper format: summary line ending with period, then metadata
- The ralph package lives at `src/ralph/`
- Run checks from the YouLab root: `make check-agent` - this runs on src/ and tests/
- For ralph-specific checks: `uv run ruff check src/ralph/` and `uv run basedpyright src/ralph/`
- Agno tools need `strip_agno_fields()` helper to remove fields Mistral doesn't accept

## Task Management

Use beads (`bd` command) for persistent task tracking across sessions:
- `bd ready` - See unblocked tasks
- `bd start <id>` - Claim a task before working
- `bd close <id> --reason "what you did"` - Complete tasks
- `bd sync` - Save to git (CRITICAL before session ends)

**Always run `bd sync` before ending any session.**

Relationship to other systems:
- **Linear**: Project-level planning and tracking
- **beads**: Implementation-level task persistence

## Linear

Team: **Ariav** (`dd52dd50-3e8c-43c2-810f-d79c71933dc9`)
Project: **YouLab** (`eac4c2fe-bee6-4784-9061-05aaba98409f`)

## Testing Memory Blocks (Dolt)

Memory blocks are stored in Dolt (MySQL-compatible with git-like versioning). The Dolt server runs in Docker.

### Prerequisites
```bash
docker compose up -d dolt   # Start Dolt container
uv run ralph-server         # Start Ralph API on port 8200
```

### Direct Dolt SQL Access
```bash
# Connect to Dolt via Docker
docker exec -it youlab-dolt-1 dolt sql

# Or use MySQL client
mysql -h 127.0.0.1 -P 3307 -u root youlab
```

### Memory Block CRUD (via SQL)
```sql
-- List all blocks for a user
SELECT label, title, LEFT(body, 50) as body_preview
FROM memory_blocks
WHERE user_id = '7a41011b-5255-4225-b75e-1d8484d0e37f';

-- Create/update a block (REPLACE = upsert)
REPLACE INTO memory_blocks (user_id, label, title, body, schema_ref, updated_at)
VALUES (
  '7a41011b-5255-4225-b75e-1d8484d0e37f',
  'student',
  'Student Profile',
  '## About Me\n\nTest content here...',
  'college-essay/student',
  NOW()
);

-- Commit the change (required for versioning)
CALL DOLT_ADD('-A');
CALL DOLT_COMMIT('-m', 'Manual test update');
```

### Memory Block API (via curl)

```bash
USER_ID="7a41011b-5255-4225-b75e-1d8484d0e37f"
BASE_URL="http://localhost:8200"

# List blocks
curl -s "$BASE_URL/users/$USER_ID/blocks" | jq .

# Get single block
curl -s "$BASE_URL/users/$USER_ID/blocks/student" | jq .

# Get pending diffs
curl -s "$BASE_URL/users/$USER_ID/blocks/student/diffs" | jq .
```

### Creating Proposals (Agent Diffs)

Proposals simulate what agents do when they want to update a memory block. The user must approve/reject them in the UI.

```bash
# Create a proposal (simulates agent suggesting a change)
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/student/propose" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "## About Me\n\nUpdated content with new information...",
    "agent_id": "tutor-agent",
    "reasoning": "Student mentioned new interests during conversation",
    "confidence": "high"
  }' | jq .

# Approve a proposal (apply the change)
DIFF_ID="agent__7a41011b-5255-4225-b75e-1d8484d0e37f__student"
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/student/diffs/$DIFF_ID/approve" | jq .

# Reject a proposal (discard the change)
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/student/diffs/$DIFF_ID/reject" | jq .
```

### Viewing Dolt Branches (Proposals)
Proposals are stored as Dolt branches. Each proposal branch contains the agent's suggested changes.

```sql
-- List all branches (includes proposal branches)
SELECT * FROM dolt_branches WHERE name LIKE 'agent/%';

-- View diff between main and a proposal branch
SELECT * FROM dolt_diff('main', 'agent/USER_ID/BLOCK_LABEL', 'memory_blocks');
```
