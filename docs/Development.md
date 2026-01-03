# Development Guide

[[README|← Back to Overview]]

Guide for contributing to and developing YouLab.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Running Letta server (for integration testing)

---

## Initial Setup

```bash
# Clone the repository
git clone <repo-url>
cd YouLab

# Run setup (installs deps + pre-commit hooks)
make setup
```

This installs:
- All project dependencies
- Development tools (pytest, ruff, basedpyright)
- Pre-commit hooks for automatic verification

---

## Project Structure

```
src/letta_starter/
├── agents/           # BaseAgent, templates, registry
├── memory/           # Memory blocks and strategies
├── pipelines/        # OpenWebUI Pipe integration
├── server/           # FastAPI HTTP service
│   └── strategy/     # Strategy agent endpoints
├── observability/    # Logging and tracing
├── config/           # Settings management
└── main.py           # CLI entry point

tests/
├── conftest.py       # Shared fixtures
├── test_memory.py    # Memory block tests
├── test_templates.py # Agent template tests
├── test_pipe.py      # Pipeline tests
└── test_server/      # HTTP service tests
    ├── test_endpoints.py
    ├── test_agents.py
    └── test_strategy/
```

---

## Development Workflow

### 1. Make Changes

Edit files in `src/letta_starter/`.

### 2. Run Lint Fix Frequently

```bash
make lint-fix
```

> **Important**: Run this after every file edit to catch issues early.

### 3. Verify Before Commit

```bash
# Quick check (lint + typecheck)
make check-agent

# Full verification (lint + typecheck + tests)
make verify-agent
```

### 4. Pre-commit Hooks

Commits are automatically blocked if checks fail. The hooks run `make verify` before each commit.

---

## Agent-Optimized Commands

YouLab uses the "swallow success, show failure" pattern from HumanLayer:

| Command | What It Does |
|---------|--------------|
| `make check-agent` | Lint + typecheck with minimal output |
| `make test-agent` | Tests only, fail-fast |
| `make verify-agent` | Full verification suite |

**On success**: Minimal output like `✓ Ruff check`, `✓ Typecheck`

**On failure**: Full error output for debugging

---

## Adding New Features

### Adding a New Agent Template

1. Define the template in `agents/templates.py`:

```python
MY_TEMPLATE = AgentTemplate(
    type_id="my-agent",
    display_name="My Agent",
    description="What this agent does",
    persona=PersonaBlock(
        name="MyAgent",
        role="Specific role",
        capabilities=["Capability 1", "Capability 2"],
        tone="professional",
        verbosity="concise",
    ),
)
```

2. Register in the registry:

```python
# In agents/default.py or where registry is configured
from letta_starter.agents.templates import MY_TEMPLATE

registry.register(MY_TEMPLATE)
```

3. Add tests in `tests/test_templates.py`.

### Adding a New API Endpoint

1. Add schema in `server/schemas.py`:

```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str
```

2. Add endpoint in `server/main.py`:

```python
@app.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(request: MyRequest) -> MyResponse:
    # Implementation
    return MyResponse(result="...")
```

3. Add tests in `tests/test_server/test_endpoints.py`.

### Adding Memory Block Fields

1. Extend block in `memory/blocks.py`:

```python
class HumanBlock(BaseModel):
    # Existing fields...
    new_field: str | None = None
```

2. Update `to_memory_string()` serialization.

3. Add tests in `tests/test_memory.py`.

---

## Configuration for Development

Create a `.env` file:

```bash
cp .env.example .env
```

Minimum configuration:

```env
# Required
ANTHROPIC_API_KEY=your-key

# Letta connection
LETTA_BASE_URL=http://localhost:8283

# Service settings (optional)
YOULAB_SERVICE_HOST=127.0.0.1
YOULAB_SERVICE_PORT=8100
```

---

## Running Services

### Start Letta Server

```bash
pip install letta
letta server
```

### Start HTTP Service

```bash
uv run letta-server
```

### Interactive CLI

```bash
uv run letta-starter
```

---

## Debugging

### Enable Debug Logging

```env
LOG_LEVEL=debug
```

### View Traces in Langfuse

1. Set Langfuse credentials in `.env`
2. Visit your Langfuse dashboard
3. Filter by `user_id` or `agent_id`

### Common Issues

| Issue | Solution |
|-------|----------|
| `Letta connection failed` | Ensure `letta server` is running |
| `Type errors` | Run `make typecheck` for details |
| `Import errors` | Run `uv sync` to update deps |

---

## Code Style

### General Principles

- Use type annotations everywhere
- Prefer composition over inheritance
- Keep functions focused and small
- Document non-obvious behavior

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `AgentManager` |
| Functions | snake_case | `get_agent` |
| Constants | UPPER_SNAKE | `DEFAULT_PORT` |
| Private | _prefix | `_cache` |

### Imports

Organized by ruff:
1. Standard library
2. Third-party
3. First-party (`letta_starter`)

---

## Related Pages

- [[Testing]] - Test suite documentation
- [[Tooling]] - Development tools
- [[Configuration]] - Environment variables

