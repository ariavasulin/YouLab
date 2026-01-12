# YouLab Platform

Course delivery platform with personalized AI tutoring. First course: college essay coaching.

## Current Stack

```
OpenWebUI → Pipeline → HTTP Service → Letta Server → Claude API
                            ↘ Honcho (message persistence)
```

- **OpenWebUI**: Chat frontend with Pipe extension system
- **YouLab Server**: Python library providing memory management, observability, and agent factories
- **Letta**: Agent framework with persistent memory (currently single shared agent)
- **Honcho**: Message persistence for theory-of-mind modeling

## Project Structure

```
src/youlab_server/       # Python backend
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
    modules/             # Module and step definitions
curriculum/              # Curriculum system (schema, loader, dynamic blocks)
tests/                   # Pytest suite (including tests/test_server/)
OpenWebUI/open-webui/    # Nested git repo (NOT a submodule)
  src/lib/components/    # Svelte components (frontend changes here)
  backend/               # Python backend + dev.sh
  backend/data/          # SQLite DB, uploads (persists locally)
```

## Documentation (Progressive Disclosure)

Don't memorize - look things up. Use `./hack/claude-docs.sh` to query docs.

```bash
./hack/claude-docs.sh list              # See all docs with descriptions
./hack/claude-docs.sh search "memory"   # Search for a topic
./hack/claude-docs.sh show Architecture # Read a specific doc
```

**When to read what:**
| Question | Read |
|----------|------|
| How does X work? | `docs/` - authoritative source of truth |
| What's the current plan? | `thoughts/shared/plans/` |
| Architecture decisions | `thoughts/shared/plans` |
| Config/TOML syntax | `docs/config-schema.md` |
| OpenWebUI frontend changes | `docs/OpenWebUI-Development.md` |
| Implementation details | Search codebase directly |

**Precedence**: `docs/` > `thoughts/shared/` > code comments

## Commands

```bash
# Setup (run once, installs deps + pre-commit hooks)
make setup

# Run the CLI
uv run youlab                    # Interactive mode (requires letta server)
uv run youlab --agent X          # Use specific agent
uv run youlab-server             # Start HTTP service (requires letta server)

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

## Code Review

CodeRabbit provides AI code review on all PRs. Config: `.coderabbit.yaml`, `.semgrep.yaml`

PR commands: `@coderabbitai review`, `@coderabbitai full review`, `@coderabbitai generate docstrings`

**Claude**: Run `make lint-fix` frequently during development and after every file edit to catch issues early.

**Claude**: Always use the `-agent` variants for verification. They implement HumanLayer's "swallow success, show failure" pattern:
- Minimal output on success: `✓ Ruff check`, `✓ Typecheck`, `✓ Tests (N tests)`
- Full output only on failure
- Fail-fast (`-x`) for tests - one bug at a time

Requires Letta server: `pip install letta && letta server`

## Key Entry Points

Don't memorize file paths - search the codebase. Key entry points:

- `src/youlab_server/server/main.py` - HTTP service entry point
- `src/youlab_server/pipelines/letta_pipe.py` - OpenWebUI integration
- `config/courses/college-essay/course.toml` - Course configuration

For everything else: `./hack/claude-docs.sh search "<topic>"` or grep the codebase.

## Deprecated Code

The following modules are deprecated in favor of TOML-based configuration:

| Module | Replacement |
|--------|-------------|
| `agents/templates.py` | `config/courses/*/course.toml` |
| `agents/default.py` | `AgentManager.create_agent()` with curriculum |
| `agents/base.py` | Letta agents via `AgentManager` |
| `memory/manager.py` | Agent-driven memory via `edit_memory_block` tool |
| `memory/blocks.py` PersonaBlock/HumanBlock | Dynamic blocks from TOML schema |
| `memory/strategies.py` | Not needed with agent-driven memory |

These modules remain for backwards compatibility but emit `DeprecationWarning` on import.

## Linear

Team: **Ariav** (`dd52dd50-3e8c-43c2-810f-d79c71933dc9`)
Project: **YouLab** (`eac4c2fe-bee6-4784-9061-05aaba98409f`)
