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
  agents/                # BaseAgent + factory functions + AgentRegistry
  memory/                # Memory blocks, rotation strategies, manager
  pipelines/             # OpenWebUI Pipe integration
  observability/         # Logging, metrics, tracing (Langfuse)
  config/                # Pydantic settings from env
  main.py                # CLI entry point
tests/                   # Pytest suite
```

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Run the CLI
uv run letta-starter             # Interactive mode (requires letta server)
uv run letta-starter --agent X   # Use specific agent

# Verification (run before committing)
make verify                      # Full: lint + typecheck + tests
make check                       # Quick: lint + typecheck only

# Individual tools
make lint                        # Ruff check + format check
make lint-fix                    # Auto-fix lint issues
make typecheck                   # BasedPyright
make test                        # Pytest (with coverage)
make test-agent                  # Pytest (agent-optimized, minimal output)
```

Pre-commit hooks run `make verify` automatically - commits are blocked if checks fail.

**Claude**: Run `make lint-fix` frequently during development and after every file edit to catch issues early.

**Claude**: Use `make test-agent` instead of `make test` for faster feedback with minimal context usage. It:
- Stops on first failure (`-x`)
- Shows only failure details, not passing tests
- Omits coverage report
- Uses single-line success output: `✓ Tests (N tests)`

Requires Letta server: `pip install letta && letta server`

## Key Files

- `src/letta_starter/memory/blocks.py` - PersonaBlock/HumanBlock schemas with serialization
- `src/letta_starter/memory/strategies.py` - Context rotation (Aggressive/Preservative/Adaptive)
- `src/letta_starter/memory/manager.py` - Memory lifecycle orchestration
- `src/letta_starter/agents/base.py` - BaseAgent with integrated memory + tracing
- `src/letta_starter/agents/default.py` - Factory functions + AgentRegistry
- `src/letta_starter/pipelines/letta_pipe.py` - OpenWebUI Pipeline integration
- `src/letta_starter/config/settings.py` - Pydantic settings from environment
- `pyproject.toml` - Dependencies and tool config
- `.env.example` - Required environment variables

## Planned (Not Yet Implemented)

Target architecture adds per-student agents, Honcho integration, and curriculum-driven tutoring:

```
OpenWebUI (Pipe) → LettaStarter HTTP Service → Letta Server → Claude API
                                             → Honcho (ToM layer)
```

**Roadmap** (see `thoughts/shared/plans/2025-12-26-youlab-technical-foundation.md`):

1. **HTTP Service** — FastAPI server (`server.py`) so Pipe stays thin
   - Detailed plan: `thoughts/shared/plans/2025-12-29-phase-1-http-service.md`
2. **User Identity & Routing** — Per-student Letta agents, not shared
3. **Honcho Integration** — Message persistence, dialectic API for student insights
4. **Thread Context** — Parse chat titles to update agent context per module/lesson
5. **Curriculum Parser** — Load course definitions from markdown, hot-reload
6. **Background Worker** — Query Honcho dialectic on idle, update agent memory
7. **Student Onboarding** — First-time setup flow, profile initialization

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

**Implementation plan**: `thoughts/shared/plans/2025-12-26-youlab-technical-foundation.md` — 7-phase plan for building the technical foundation (not yet implemented).

## Linear

Team: **Ariav** (`dd52dd50-3e8c-43c2-810f-d79c71933dc9`)
Project: **YouLab** (`eac4c2fe-bee6-4784-9061-05aaba98409f`)
Assignee: **ARI** (Ariav Asulin)
