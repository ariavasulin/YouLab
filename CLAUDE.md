# YouLab Platform

Course delivery platform with personalized AI tutoring. First course: college essay coaching.

## Current Stack

```
OpenWebUI → Pipeline (embedded in OpenWebUI) → Letta Server → Claude API
```

- **OpenWebUI**: Chat frontend with Pipe extension system
- **LettaStarter**: Python library providing memory management, observability, and agent factories
- **Letta**: Agent framework with persistent memory (currently single shared agent)

## Project Structure

```
src/letta_starter/       # Python backend
  agents/                # BaseAgent + factory functions + AgentRegistry + templates
  memory/                # Memory blocks, rotation strategies, manager
  pipelines/             # OpenWebUI Pipe integration
  server/                # FastAPI HTTP service (agent management, chat endpoints)
  observability/         # Logging, metrics, tracing (Langfuse)
  config/                # Pydantic settings from env
  main.py                # CLI entry point
tests/                   # Pytest suite (including tests/test_server/)
```

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Run the CLI
uv run letta-starter             # Interactive mode (requires letta server)
uv run letta-starter --agent X   # Use specific agent
uv run letta-server              # Start HTTP service (requires letta server)

# Verification (agent-optimized, minimal output)
make verify-agent                # Full: lint + typecheck + tests
make check-agent                 # Quick: lint + typecheck only
make test-agent                  # Pytest only (no coverage)

# Individual tools
make lint-fix                    # Auto-fix lint issues
```

Pre-commit hooks run `make verify` automatically - commits are blocked if checks fail.

**Claude**: Run `make lint-fix` frequently during development and after every file edit to catch issues early.

**Claude**: Always use the `-agent` variants for verification. They implement HumanLayer's "swallow success, show failure" pattern:
- Minimal output on success: `✓ Ruff check`, `✓ Typecheck`, `✓ Tests (N tests)`
- Full output only on failure
- Fail-fast (`-x`) for tests - one bug at a time

Requires Letta server: `pip install letta && letta server`

## Key Files

- `src/letta_starter/memory/blocks.py` - PersonaBlock/HumanBlock schemas with serialization
- `src/letta_starter/memory/strategies.py` - Context rotation (Aggressive/Preservative/Adaptive)
- `src/letta_starter/memory/manager.py` - Memory lifecycle orchestration
- `src/letta_starter/agents/base.py` - BaseAgent with integrated memory + tracing
- `src/letta_starter/agents/default.py` - Factory functions + AgentRegistry
- `src/letta_starter/agents/templates.py` - AgentTemplate + TUTOR_TEMPLATE for essay coaching
- `src/letta_starter/server/main.py` - FastAPI app with /health, /agents, /chat endpoints
- `src/letta_starter/server/agents.py` - AgentManager for per-user Letta agents
- `src/letta_starter/pipelines/letta_pipe.py` - OpenWebUI Pipeline integration
- `src/letta_starter/config/settings.py` - Pydantic settings from environment
- `pyproject.toml` - Dependencies and tool config
- `.env.example` - Required environment variables

## Roadmap

Target architecture adds Honcho integration and curriculum-driven tutoring:

```
OpenWebUI (Pipe) → LettaStarter HTTP Service → Letta Server → Claude API
                                             → Honcho (ToM layer)
```

**Full plan**: `thoughts/shared/plans/2025-12-26-youlab-technical-foundation.md`

- [X] **Phase 1: HTTP Service** — FastAPI server with agent management (`server/`)
- [ ] **Phase 2: User Identity & Routing** — Per-student Letta agents via Pipe integration
- [ ] **Phase 3: Honcho Integration** — Message persistence, dialectic API for student insights
- [ ] **Phase 4: Thread Context** — Parse chat titles to update agent context per module/lesson
- [ ] **Phase 5: Curriculum Parser** — Load course definitions from markdown, hot-reload
- [ ] **Phase 6: Background Worker** — Query Honcho dialectic on idle, update agent memory
- [ ] **Phase 7: Student Onboarding** — First-time setup flow, profile initialization

## Thoughts Directory

The `thoughts/` directory is managed separately via `humanlayer thoughts` (not committed to this repo).

```
thoughts/
  {username}/           # Personal notes
  shared/               # Team notes
    research/           # Research documents
    plans/              # Implementation plans
  global/               # Cross-repo notes
  searchable/           # Auto-generated (NEVER write here)
```

**Important**: Never write to `thoughts/searchable/` — it gets wiped on every sync. Write to `thoughts/shared/` instead.

**Context doc**: `thoughts/shared/youlab-project-context.md` — Full architecture decisions, open questions, and next steps.

## Linear

Team: **Ariav** (`dd52dd50-3e8c-43c2-810f-d79c71933dc9`)
Project: **YouLab** (`eac4c2fe-bee6-4784-9061-05aaba98409f`)
Assignee: **ARI** (Ariav Asulin)
