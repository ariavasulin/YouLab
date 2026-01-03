# Testing

[[README|← Back to Overview]]

Test suite documentation for YouLab.

## Overview

| Property | Value |
|----------|-------|
| Framework | pytest |
| Async Support | pytest-asyncio |
| Coverage | pytest-cov |
| Test Directory | `tests/` |

---

## Running Tests

### Quick Run (Agent-Optimized)

```bash
make test-agent
```

Minimal output on success, full output on failure. Uses fail-fast (`-x`).

### Full Run with Coverage

```bash
make test
# or
uv run pytest
```

### Coverage Report

```bash
# Terminal report
make coverage

# HTML report
make coverage-html
open htmlcov/index.html
```

---

## Test Structure

```
tests/
├── conftest.py                # Shared fixtures
├── test_memory.py             # Memory block tests
├── test_templates.py          # Agent template tests
├── test_pipe.py               # Pipeline tests
└── test_server/
    ├── conftest.py            # Server fixtures
    ├── test_endpoints.py      # HTTP endpoint tests
    ├── test_agents.py         # AgentManager tests
    ├── test_schemas.py        # Schema validation tests
    ├── test_tracing.py        # Tracing tests
    └── test_strategy/
        ├── conftest.py        # Strategy fixtures
        ├── test_endpoints.py  # Strategy endpoints
        └── test_manager.py    # StrategyManager tests
```

---

## Fixtures

### Global Fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def sample_persona_data():
    """Sample persona data for testing."""
    return {
        "name": "TestAgent",
        "role": "Test assistant",
        "capabilities": ["Testing", "Validation"],
        "tone": "professional",
        "verbosity": "concise",
    }

@pytest.fixture
def sample_human_data():
    """Sample human data for testing."""
    return {
        "name": "TestUser",
        "role": "Developer",
        "current_task": "Running tests",
        "preferences": ["Clear output", "Fast response"],
    }

@pytest.fixture
def sample_agent_template_data():
    """Sample agent template data for testing."""
    return {
        "type_id": "custom",
        "display_name": "Custom Agent",
        "persona": PersonaBlock(...),
        "human": HumanBlock(),
    }
```

### Server Fixtures (`tests/test_server/conftest.py`)

```python
@pytest.fixture
def app():
    """Create test FastAPI app."""
    from letta_starter.server.main import create_app
    return create_app()

@pytest.fixture
def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)
```

---

## Writing Tests

### Memory Block Test Example

```python
# tests/test_memory.py

def test_persona_block_serialization(sample_persona_data):
    """Test PersonaBlock serializes to memory string."""
    persona = PersonaBlock(**sample_persona_data)
    result = persona.to_memory_string()

    assert "[IDENTITY]" in result
    assert "TestAgent" in result
    assert "[CAPABILITIES]" in result

def test_human_block_add_context():
    """Test context note rolling window."""
    human = HumanBlock()

    for i in range(15):
        human.add_context_note(f"Note {i}")

    # Only keeps last 10
    assert len(human.context_notes) == 10
    assert "Note 14" in human.context_notes
```

### HTTP Endpoint Test Example

```python
# tests/test_server/test_endpoints.py

def test_health_endpoint(client):
    """Test /health returns ok."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")

def test_create_agent(client, mock_letta):
    """Test POST /agents creates agent."""
    response = client.post("/agents", json={
        "user_id": "test-user",
        "agent_type": "tutor",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "test-user"
    assert data["agent_type"] == "tutor"
```

### Async Test Example

```python
# tests/test_server/test_agents.py

import pytest

@pytest.mark.asyncio
async def test_agent_manager_cache():
    """Test AgentManager caches agent IDs."""
    manager = AgentManager(mock_client)

    # First call creates
    agent_id = await manager.get_or_create_agent("user1", "tutor")

    # Second call uses cache
    cached_id = await manager.get_or_create_agent("user1", "tutor")

    assert agent_id == cached_id
```

---

## Mocking Letta

For tests that don't need a real Letta server:

```python
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_letta_client():
    """Mock Letta client for isolated tests."""
    client = MagicMock()
    client.agents = MagicMock()
    client.agents.create = AsyncMock(return_value=MagicMock(id="agent-123"))
    client.agents.list = AsyncMock(return_value=[])
    return client
```

---

## Test Categories

### Unit Tests

Test individual components in isolation:

- `test_memory.py` - Memory block logic
- `test_templates.py` - Template validation
- `test_schemas.py` - Schema serialization

### Integration Tests

Test component interactions:

- `test_endpoints.py` - Full HTTP request/response
- `test_agents.py` - AgentManager with mocked Letta
- `test_strategy/` - Strategy agent flow

---

## Configuration

### pytest.ini (in pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = [
    "--cov=src/letta_starter",
    "--cov-branch",
    "--cov-report=term-missing",
]
```

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["src/letta_starter"]
branch = true
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

---

## CI Integration

Tests run automatically via pre-commit hooks before each commit:

```bash
# Pre-commit runs:
make verify
```

If tests fail, the commit is blocked.

---

## Related Pages

- [[Development]] - Development workflow
- [[Tooling]] - Test tools configuration
- [[Schemas]] - Schema definitions

