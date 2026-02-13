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
3. Server creates ephemeral agent: base instructions + tool guide + CLAUDE.md + memory blocks
4. Agent streams response via SSE (event types: `status`, `tool_call_start`, `tool_call_complete`, `tool_call_error`, `message`, `done`, `error`)
5. Messages persisted to Honcho (fire-and-forget — silent failure on error)

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
config/courses/                 # TOML agent definitions (legacy, not loaded by Ralph)
```

## Agent Lifecycle (Per-Request)

Ralph creates a **new, ephemeral agent for every chat request**. There is no persistent agent state between messages — all continuity comes from conversation history (passed in the request) and memory blocks (persisted in Dolt).

**Agent construction** (`server.py:291-310`):
1. Build system prompt: base instructions + tool usage guide + CLAUDE.md (from workspace) + memory blocks
2. Instantiate tools as Python objects (workspace-scoped):
   - `ShellTools(base_dir=workspace)` — shell commands
   - `HookedFileTools(base_dir=workspace, ...)` — file ops with LaTeX auto-compile
   - `HonchoTools()` — conversation history queries
   - `MemoryBlockTools()` — read blocks + propose edits
3. Create `Agent(model=OpenRouter(...), tools=[...], instructions=...)`
4. Stream response via SSE, then discard agent

**Memory block initialization**: When a user has zero blocks, `ensure_welcome_blocks` (`memory.py:79-100`) creates all 4 default blocks at once. This only fires for brand-new users.

**Default memory blocks** (defined in `memory.py:15-76`):
| Label | Title | Purpose |
|-------|-------|---------|
| `origin_story` | Origin Story | Who they are, goals, strengths, weaknesses |
| `tech_relationship` | Tech Relationship | How they use technology, distraction patterns |
| `ai_partnership` | AI Partnership | What AI should/shouldn't help with |
| `onboarding_progress` | Current Progress | Welcome module progress tracking |

> **Legacy**: `config/courses/` contains TOML agent definitions from the Letta-based stack. These files exist but are **not loaded by Ralph**. They may be resurrected as a declarative config system in the future.

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Development (auto-reload, kills stale processes, starts Dolt)
make dev                         # Recommended: starts Ralph with auto-reload
./hack/dev.sh                    # Same thing, directly
./hack/dev.sh --kill             # Stop the dev server

# Production-style (no auto-reload)
uv run ralph-server              # Start Ralph HTTP backend on port 8200

# LaTeX Notes (Tectonic required for PDF generation)
brew install tectonic            # macOS
cargo install tectonic           # Cross-platform via Rust

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

> **Dev testing SOP**: See `docs/dev-testing.md` for full dev workflow, testing procedures, and troubleshooting.

## Error Boundaries

When dependencies fail, the system degrades silently. This table documents what breaks.

| Component | Failure Mode | Lost | Preserved | User Sees |
|-----------|-------------|------|-----------|-----------|
| **Dolt** | Connection refused | Memory blocks, proposals, activity tracking, background tasks | Chat, file/shell tools | No memory context in responses |
| **Honcho** | Import/init failure | Message persistence, dialectic queries | Everything else | Messages not saved across sessions |
| **Honcho** | Fire-and-forget task fails | Individual message | Subsequent messages | Nothing (silent loss) |
| **LaTeX** | Compilation failure | PDF output | File saved successfully | Error in artifact panel; **agent is unaware** |
| **OpenRouter** | API error | Current response | System state | SSE error event |
| **Activity tracking** | DB error | User activity timestamp | Everything else | Nothing (warning logged) |

## Environment Variables (Ralph)

All settings are in `config.py` with prefix `RALPH_`. See `Settings` class for defaults.

```bash
# Core (required)
RALPH_OPENROUTER_API_KEY=...                              # OpenRouter API key
RALPH_OPENROUTER_MODEL=anthropic/claude-sonnet-4-20250514 # Default model

# Workspace
RALPH_AGENT_WORKSPACE=/path/to/workspace  # Shared workspace (optional, overrides per-user)
RALPH_USER_DATA_DIR=/data/ralph/users     # Per-user workspaces

# Honcho
RALPH_HONCHO_WORKSPACE_ID=ralph           # Honcho workspace
RALPH_HONCHO_ENVIRONMENT=demo             # demo, local, or production
RALPH_HONCHO_API_KEY=...                  # Honcho API key (optional)

# Dolt
RALPH_DOLT_HOST=localhost
RALPH_DOLT_PORT=3307
RALPH_DOLT_USER=root
RALPH_DOLT_PASSWORD=devpassword
RALPH_DOLT_DATABASE=youlab

# OpenWebUI sync (optional)
RALPH_OPENWEBUI_URL=https://...           # OpenWebUI instance URL
RALPH_OPENWEBUI_API_KEY=...              # OpenWebUI API key
RALPH_SYNC_TO_OPENWEBUI=true             # Enable KB sync
```

## Codebase Patterns

- Use `model_config = {"env_prefix": "..."}` instead of nested `class Config` for Pydantic Settings
- OpenWebUI pipe docstrings need proper format: summary line ending with period, then metadata
- The ralph package lives at `src/ralph/`
- Run checks from the YouLab root: `make check-agent` - this runs on src/ and tests/
- For ralph-specific checks: `uv run ruff check src/ralph/` and `uv run basedpyright src/ralph/`
- All Agno tool instances must be wrapped in `strip_agno_fields()` — strips `requires_confirmation` and `external_execution` fields that OpenRouter/Mistral rejects
- Agno tools are synchronous but Dolt is async — `memory_blocks.py` uses `_run_async_with_fresh_client()` to bridge via thread pool (30s timeout)

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

## Production Server

- **Host alias**: `vps` (via `~/.ssh/config`)
- **IP**: `23.94.218.158`
- **User**: `root`
- **SSH Port**: 22
- **Auth**: SSH key (`~/.ssh/id_ed25519`)
- **Login**: `ssh vps`

## Linear

Team: **Ariav** (`dd52dd50-3e8c-43c2-810f-d79c71933dc9`)
Project: **YouLab** (`eac4c2fe-bee6-4784-9061-05aaba98409f`)

## Production Users (OpenWebUI)

| Name | Email | User ID |
|------|-------|---------|
| Ariav Asulin | ariav2002@gmail.com | `ed6d1437-7b38-47a4-bd49-670267f0a7ce` |
| Noam Michael | noam_michael@berkeley.edu | `979fe457-9206-43b9-8ecf-0b73612cff6e` |
| Genee | geneeramsay@gmail.com | `5003623c-cb9c-4252-89b7-68279e59583b` |

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
  'origin_story',
  'Origin Story',
  '## Who I Am At My Best\n\nTest content here...',
  NULL,
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
curl -s "$BASE_URL/users/$USER_ID/blocks/origin_story" | jq .

# Get pending diffs
curl -s "$BASE_URL/users/$USER_ID/blocks/origin_story/diffs" | jq .
```

### Creating Proposals (Agent Diffs)

Proposals simulate what agents do when they want to update a memory block. The user must approve/reject them in the UI. Proposals are stored as Dolt branches named `agent/{user_id}/{label}`.

```bash
# Create a proposal (simulates agent suggesting a change)
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/origin_story/propose" \
  -H "Content-Type: application/json" \
  -d '{
    "body": "## Who I Am At My Best\n\nUpdated content with new information...",
    "agent_id": "tutor-agent",
    "reasoning": "Student mentioned new interests during conversation",
    "confidence": "high"
  }' | jq .

# Approve a proposal (apply the change — merges branch to main, deletes branch)
DIFF_ID="agent__7a41011b-5255-4225-b75e-1d8484d0e37f__origin_story"
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/origin_story/diffs/$DIFF_ID/approve" | jq .

# Reject a proposal (discard — force-deletes the branch)
curl -s -X POST "$BASE_URL/users/$USER_ID/blocks/origin_story/diffs/$DIFF_ID/reject" | jq .
```

### Viewing Dolt Branches (Proposals)
Proposals are stored as Dolt branches. Each proposal branch contains the agent's suggested changes.

```sql
-- List all branches (includes proposal branches)
SELECT * FROM dolt_branches WHERE name LIKE 'agent/%';

-- View diff between main and a proposal branch
SELECT * FROM dolt_diff('main', 'agent/USER_ID/BLOCK_LABEL', 'memory_blocks');
```
