# YouLab Platform

Introspective AI tutoring platform with transparent, user-controlled context. Memory blocks are version-controlled and agent edits require user approval.

## Architecture Overview

```
OpenWebUI → Ralph Pipe → Ralph Server (FastAPI) → Agno Agent → OpenRouter API
                                 │                    │
                                 ▼                    ▼
                              Dolt DB            User Workspace
                         (memory blocks)         (files/shell)
                                 │
                                 ▼
                              Honcho
                        (message history)
```

**Key Components**:
- **Ralph Pipe** (`src/ralph/pipe.py`): HTTP client bridging OpenWebUI to Ralph server via SSE
- **Ralph Server** (`src/ralph/server.py`): Creates per-request Agno agents with workspace-scoped tools
- **Dolt** (`src/ralph/dolt.py`): MySQL-compatible DB with git-like versioning for memory blocks
- **Honcho** (`src/ralph/honcho.py`): Message persistence and dialectic queries

**Data Flow**:
1. User sends message in OpenWebUI
2. Pipe extracts user_id, chat_id, forwards to `/chat/stream`
3. Server builds agent with: base instructions + CLAUDE.md + memory blocks
4. Agent streams response via SSE
5. Messages persisted to Honcho (fire-and-forget)

## Project Structure

```
src/ralph/                      # Main application
├── server.py                   # FastAPI endpoints + Agno agent
├── pipe.py                     # OpenWebUI pipe (HTTP client)
├── config.py                   # Environment configuration
├── dolt.py                     # Dolt database client
├── memory.py                   # Memory context builder
├── honcho.py                   # Honcho message persistence
├── api/
│   ├── blocks.py               # Memory block REST API
│   ├── background.py           # Background task API
│   ├── workspace.py            # Workspace file API
│   └── notes_adapter.py        # OpenWebUI notes bridge
├── tools/
│   ├── memory_blocks.py        # Claude Code-style block editing
│   ├── honcho_tools.py         # Conversation history queries
│   └── latex_tools.py          # PDF note generation
├── background/                 # Scheduled task infrastructure
└── sync/                       # OpenWebUI KB sync

src/youlab_server/              # Legacy Letta-based stack (deprecated)
config/courses/                 # TOML agent definitions
    {course}/agents.toml        # Agent, blocks, and tasks for course
```

## Agent Configuration (TOML)

Agents are defined in `config/courses/{course}/agents.toml`:

```toml
[agent]
name = "Essay Coach"
model = "anthropic/claude-sonnet-4"
system_prompt = "..."
tools = ["file_tools", "honcho_tools", "memory_blocks"]
blocks = ["student", "journey"]

[[block]]
label = "student"
title = "Student Profile"
template = "## About Me\n\n[To be filled in]"

[[task]]
name = "weekly-review"
trigger = { type = "cron", schedule = "0 9 * * 1" }
system_prompt = "Review student progress..."
tools = ["honcho_tools", "memory_blocks"]
blocks = ["student"]
```

**Key rules**:
- Only one `agents.toml` can define `[[block]]` schema for a given label
- Blocks check if user has existing content before initializing from template
- Multiple courses can share blocks (e.g., "student") without redefining them

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Ralph (new stack)
uv run ralph-server              # Start Ralph HTTP backend on port 8200

# LaTeX Notes (Tectonic required for PDF generation)
brew install tectonic            # macOS
cargo install tectonic           # Cross-platform via Rust

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
