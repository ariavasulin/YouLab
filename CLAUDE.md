# YouLab Platform

Course delivery platform with personalized AI tutoring. First course: college essay coaching.

## Stack

```
OpenWebUI (Pipe) → LettaStarter (Python) → Letta Server → Claude API
                                        → Honcho (planned)
```

- **Letta**: Agent framework with persistent memory. LettaStarter wraps it with memory management and observability.
- **Honcho**: Theory of Mind layer (planned, not yet integrated)
- **OpenWebUI**: Chat frontend — LettaStarter includes a Pipe for integration

## Project Structure

```
src/letta_starter/       # Python backend
  agents/                # BaseAgent + factory functions
  memory/                # Memory blocks, rotation strategies, manager
  pipelines/             # OpenWebUI Pipe integration
  observability/         # Logging, metrics, tracing (Langfuse)
  config/                # Pydantic settings from env
  main.py                # CLI entry point
tests/                   # Pytest suite
courses/                 # (planned) Curriculum as markdown
docs/                    # (planned) Architecture specs
```

## Commands

```bash
# Setup
uv sync                          # Install deps
uv sync --all-extras             # With dev + observability

# Run
uv run letta-starter             # Interactive CLI (requires letta server)
uv run letta-starter --agent X   # Use specific agent name

# Test/Lint
uv run pytest                    # Run tests
uv run ruff check src/           # Lint
uv run mypy src/                 # Type check
```

Requires Letta server running: `pip install letta && letta server`

## Key Files

- `src/letta_starter/memory/blocks.py` - PersonaBlock/HumanBlock schemas with serialization
- `src/letta_starter/memory/strategies.py` - Context rotation (Aggressive/Preservative/Adaptive)
- `src/letta_starter/agents/base.py` - BaseAgent with integrated memory + tracing
- `src/letta_starter/pipelines/letta_pipe.py` - OpenWebUI Pipeline integration
- `pyproject.toml` - Dependencies and tool config
- `.env.example` - Required environment variables
