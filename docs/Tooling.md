# Tooling

[[README|← Back to Overview]]

Development tools and configuration for YouLab.

## Overview

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| uv | Package manager | `pyproject.toml` |
| ruff | Linter + formatter | `pyproject.toml` |
| basedpyright | Type checker | `pyproject.toml` |
| pytest | Test framework | `pyproject.toml` |
| pre-commit | Git hooks | `.pre-commit-config.yaml` |

---

## uv (Package Manager)

[uv](https://docs.astral.sh/uv/) is an extremely fast Python package manager.

### Commands

```bash
# Install all dependencies
uv sync

# Install with dev extras
uv sync --all-extras

# Run a command
uv run <command>

# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>
```

### Configuration

```toml
# pyproject.toml

[project]
dependencies = [
    "letta>=0.6.0",
    "fastapi>=0.115.0",
    # ...
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.4.0",
    # ...
]
```

---

## Ruff (Linter + Formatter)

[Ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter and formatter.

### Commands

```bash
# Check for issues
make lint
# or
uv run ruff check src/ tests/

# Auto-fix issues
make lint-fix
# or
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

### Configuration

```toml
# pyproject.toml

[tool.ruff]
line-length = 100
target-version = "py311"
exclude = ["OpenWebUI", "hack"]

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    # Formatting (handled by ruff format)
    "W191", "E111", "E501", # ...

    # Docstrings (too strict)
    "D100", "D101", # ...

    # Too opinionated
    "ANN401", "TD002", # ...
]

[tool.ruff.lint.isort]
known-first-party = ["letta_starter"]
```

### Key Rule Categories

| Category | Rules | Notes |
|----------|-------|-------|
| E, W | pycodestyle | Basic style |
| F | pyflakes | Errors and warnings |
| I | isort | Import sorting |
| D | pydocstyle | Docstrings (partially disabled) |
| ANN | annotations | Type annotations |
| S | bandit | Security |
| B | bugbear | Bug detection |

### Per-File Ignores

```toml
[tool.ruff.lint.per-file-ignores]
"tests/*" = [
    "S101",    # assert allowed in tests
    "D",       # docstrings not required
    "ANN",     # annotations not required
    "PLR2004", # magic values in assertions ok
]
```

---

## Basedpyright (Type Checker)

[Basedpyright](https://docs.basedpyright.com/) is a fork of Pyright with additional features.

### Commands

```bash
make typecheck
# or
uv run basedpyright src/
```

### Configuration

```toml
# pyproject.toml

[tool.basedpyright]
pythonVersion = "3.11"
typeCheckingMode = "strict"
include = ["src/letta_starter", "tests"]
exclude = [".venv", "__pycache__", "OpenWebUI"]

# External library handling
reportMissingImports = false
reportMissingTypeStubs = false
reportUnknownMemberType = false
```

### Common Type Patterns

```python
# Optional with default
def func(value: str | None = None) -> str:
    return value or "default"

# Generic types
def get_agent(agent_id: str) -> AgentResponse | None:
    ...

# Async functions
async def create_agent(request: CreateAgentRequest) -> AgentResponse:
    ...
```

---

## Pytest (Testing)

See [[Testing]] for detailed test documentation.

### Commands

```bash
# Run all tests
make test
# or
uv run pytest

# Run with coverage
make coverage

# Agent-optimized (minimal output)
make test-agent
```

### Configuration

```toml
# pyproject.toml

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = [
    "--cov=src/letta_starter",
    "--cov-branch",
    "--cov-report=term-missing",
]
```

---

## Pre-commit (Git Hooks)

Pre-commit runs checks before each commit.

### Setup

```bash
make setup
# Installs pre-commit hooks
```

### Configuration

```yaml
# .pre-commit-config.yaml

repos:
  - repo: local
    hooks:
      - id: verify
        name: verify
        entry: make verify
        language: system
        pass_filenames: false
```

### Bypassing (Emergency Only)

```bash
git commit --no-verify -m "emergency fix"
```

---

## Make Commands

Complete reference for all Makefile targets:

### Setup

| Command | Description |
|---------|-------------|
| `make setup` | Install deps + pre-commit hooks |
| `make clean` | Remove cache directories |

### Verification

| Command | Description |
|---------|-------------|
| `make lint` | Run ruff check |
| `make lint-fix` | Auto-fix lint issues |
| `make typecheck` | Run basedpyright |
| `make test` | Run pytest with coverage |
| `make check` | Lint + typecheck |
| `make verify` | Full verification (lint + typecheck + tests) |

### Agent-Optimized

| Command | Description |
|---------|-------------|
| `make check-agent` | Quick verification, minimal output |
| `make test-agent` | Tests only, fail-fast |
| `make verify-agent` | Full verification, minimal output |

### Coverage

| Command | Description |
|---------|-------------|
| `make coverage` | Terminal coverage report |
| `make coverage-html` | HTML coverage report |

---

## IDE Integration

### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)

Settings:
```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.analysis.typeCheckingMode": "strict",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff plugin for formatting
3. Configure basedpyright as external tool

---

## Related Pages

- [[Development]] - Development workflow
- [[Testing]] - Test suite documentation
- [[Configuration]] - Environment variables

