# Development Guide

[[README|<- Back to Overview]]

Complete guide for developing and contributing to YouLab.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Running Letta server (for integration testing)

---

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd YouLab
make setup  # Installs deps + pre-commit hooks
```

---

## Development Workflow

1. **Make changes** in `src/letta_starter/`
2. **Run lint fix** frequently: `make lint-fix`
3. **Verify before commit**: `make verify-agent`

Pre-commit hooks run `make verify` automatically.

---

## Commands Reference

### Verification (Agent-Optimized)

| Command | Description |
|---------|-------------|
| `make check-agent` | Quick: lint + typecheck, minimal output |
| `make test-agent` | Tests only, fail-fast |
| `make verify-agent` | Full: lint + typecheck + tests |

### Standard Commands

| Command | Description |
|---------|-------------|
| `make lint` | Run ruff check |
| `make lint-fix` | Auto-fix lint issues |
| `make typecheck` | Run basedpyright |
| `make test` | Run pytest with coverage |
| `make coverage-html` | Generate HTML coverage report |

---

## Tooling Configuration

All tools are configured in `pyproject.toml`.

### uv (Package Manager)

```bash
uv sync              # Install dependencies
uv run <command>     # Run command in venv
uv add <package>     # Add dependency
```

### Ruff (Linter + Formatter)

```bash
make lint-fix        # Auto-fix and format
```

Key settings:
- Line length: 100
- Target: Python 3.11
- Uses ALL rules with sensible ignores

### Basedpyright (Type Checker)

```bash
make typecheck
```

Strict mode with external library handling disabled.

### Pre-commit

Hooks run `make verify` before each commit. Bypass with `--no-verify` (emergency only).

---

## Testing

### Running Tests

```bash
make test-agent      # Quick, fail-fast
make test            # Full with coverage
make coverage-html   # Generate HTML report
```

### Test Structure

```
tests/
├── conftest.py           # Shared fixtures
├── test_memory.py        # Memory block tests
├── test_templates.py     # Agent template tests
├── test_pipe.py          # Pipeline tests
└── test_server/          # HTTP service tests
```

### Writing Tests

```python
def test_persona_block_serialization(sample_persona_data):
    """Test PersonaBlock serializes to memory string."""
    persona = PersonaBlock(**sample_persona_data)
    result = persona.to_memory_string()
    assert "[IDENTITY]" in result

@pytest.mark.asyncio
async def test_agent_manager_cache():
    """Test AgentManager caches agent IDs."""
    manager = AgentManager(mock_client)
    agent_id = await manager.get_or_create_agent("user1", "tutor")
    cached_id = await manager.get_or_create_agent("user1", "tutor")
    assert agent_id == cached_id
```

### Mocking Letta

```python
@pytest.fixture
def mock_letta_client():
    client = MagicMock()
    client.agents.create = AsyncMock(return_value=MagicMock(id="agent-123"))
    return client
```

---

## Code Style

- Type annotations everywhere
- Prefer composition over inheritance
- Keep functions focused and small

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `AgentManager` |
| Functions | snake_case | `get_agent` |
| Constants | UPPER_SNAKE | `DEFAULT_PORT` |
| Private | _prefix | `_cache` |

---

## IDE Setup

### VS Code

Recommended extensions: Python, Pylance, Ruff

```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `Letta connection failed` | Ensure `letta server` is running |
| `Type errors` | Run `make typecheck` for details |
| `Import errors` | Run `uv sync` to update deps |

---

## Related Pages

- [[Configuration]] - Environment variables
- [[Quickstart]] - Getting started
