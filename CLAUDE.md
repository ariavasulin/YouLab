# YouLab Platform

Course delivery platform with personalized AI tutoring. First course: college essay coaching.

## Current Stack

```
OpenWebUI → Pipeline → HTTP Service → Letta Server → Claude API
                            ↘ Honcho (message persistence)
```

- **OpenWebUI**: Chat frontend with Pipe extension system
- **LettaStarter**: Python library providing memory management, observability, and agent factories
- **Letta**: Agent framework with persistent memory (currently single shared agent)
- **Honcho**: Message persistence for theory-of-mind modeling

## Project Structure

```
src/letta_starter/       # Python backend
  agents/                # BaseAgent + factory functions + AgentRegistry + templates
  memory/                # Memory blocks, rotation strategies, manager, enricher
  pipelines/             # OpenWebUI Pipe integration
  server/                # FastAPI HTTP service (agent management, chat endpoints)
    strategy/            # RAG-enabled strategy agent (project knowledge queries)
  honcho/                # Honcho client for message persistence + dialectic queries
  tools/                 # Agent tools (query_honcho, edit_memory_block)
  background/            # Background agent runner + TOML config schemas
  observability/         # Logging, metrics, tracing (Langfuse)
  config/                # Pydantic settings from env
  main.py                # CLI entry point
config/courses/          # TOML course configs (see docs/config-schema.md)
  {course-id}/           # Course directory
    course.toml          # Main config (agent, blocks, background agents)
    modules/             # Module and lesson definitions
curriculum/              # Curriculum system (schema, loader, dynamic blocks)
tests/                   # Pytest suite (including tests/test_server/)
```

## Documentation

/docs is religiously maintained and the unequivocal source of truth for anything related to this project. When answering questions and working on this project, consult the documentation here first and with highest precedence. 

Assume thoughts it generally more up to date than anything in /thoughts unless told otherwise.

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

# Documentation
npx serve docs                   # Serve docs locally at http://localhost:3000
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
- `src/letta_starter/memory/enricher.py` - MemoryEnricher for external memory updates with audit trailing
- `src/letta_starter/agents/base.py` - BaseAgent with integrated memory + tracing
- `src/letta_starter/agents/default.py` - Factory functions + AgentRegistry
- `src/letta_starter/agents/templates.py` - AgentTemplate + TUTOR_TEMPLATE for essay coaching
- `src/letta_starter/server/main.py` - FastAPI app with /health, /agents, /chat, /background endpoints
- `src/letta_starter/server/agents.py` - AgentManager for per-user Letta agents
- `src/letta_starter/server/background.py` - Background agent HTTP endpoints
- `src/letta_starter/server/strategy/manager.py` - StrategyManager singleton for RAG queries
- `src/letta_starter/server/strategy/router.py` - FastAPI router: /strategy/documents, /ask, /health
- `src/letta_starter/pipelines/letta_pipe.py` - OpenWebUI Pipeline integration
- `src/letta_starter/config/settings.py` - Pydantic settings from environment
- `src/letta_starter/honcho/client.py` - HonchoClient for message persistence + dialectic queries
- `src/letta_starter/tools/dialectic.py` - query_honcho tool for in-conversation ToM queries
- `src/letta_starter/tools/memory.py` - edit_memory_block tool for agent-driven memory updates
- `src/letta_starter/background/schema.py` - Pydantic schemas for TOML course configuration
- `src/letta_starter/background/runner.py` - BackgroundAgentRunner execution engine
- `src/letta_starter/curriculum/schema.py` - Full curriculum schema (CourseConfig, blocks, lessons)
- `src/letta_starter/curriculum/blocks.py` - Dynamic memory block generation from TOML
- `src/letta_starter/curriculum/loader.py` - TOML loading and caching
- `src/letta_starter/server/curriculum.py` - HTTP endpoints for curriculum management
- `config/courses/college-essay/course.toml` - College essay course configuration
- `docs/config-schema.md` - Complete TOML configuration reference
- `pyproject.toml` - Dependencies and tool config
- `.env.example` - Required environment variables

## Roadmap

Current architecture with Honcho integration:

```
OpenWebUI (Pipe) → LettaStarter HTTP Service → Letta Server → Claude API
                                             → Honcho (ToM layer)
```

**Full plan**: `thoughts/shared/plans/2025-12-26-youlab-technical-foundation.md`

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
