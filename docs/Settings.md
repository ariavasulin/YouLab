# Settings Classes

[[README|← Back to Overview]]

Pydantic settings classes for type-safe configuration.

## Overview

YouLab uses two settings classes:

| Class | Prefix | Use Case |
|-------|--------|----------|
| `Settings` | (none) | CLI and library |
| `ServiceSettings` | `YOULAB_SERVICE_` | HTTP service |

**Location**: `src/letta_starter/config/settings.py`

---

## Settings Class

General application settings.

```python
from letta_starter.config import get_settings

settings = get_settings()

# Access settings
print(settings.letta_base_url)
print(settings.log_level)
```

### Configuration

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

- Loads from `.env` file
- No environment variable prefix
- Ignores unknown variables

### Fields

```python
# Letta Connection
letta_base_url: str = "http://localhost:8283"
letta_api_key: str | None = None

# LLM Configuration
llm_provider: str = "openai"
llm_model: str = "gpt-4"
openai_api_key: str | None = None
anthropic_api_key: str | None = None

# Observability
log_level: str = "INFO"
log_json: bool = True
service_name: str = "letta-starter"

# Langfuse
langfuse_enabled: bool = False
langfuse_public_key: str | None = None
langfuse_secret_key: str | None = None
langfuse_host: str = "https://cloud.langfuse.com"

# Memory
core_memory_max_chars: int = 1500
archival_rotation_threshold: float = 0.8

# Agent
default_agent_name: str = "default"
```

### Cached Getter

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Single instance pattern - settings are loaded once.

---

## ServiceSettings Class

HTTP service-specific settings.

```python
from letta_starter.config.settings import ServiceSettings

settings = ServiceSettings()

# Start server
uvicorn.run(app, host=settings.host, port=settings.port)
```

### Configuration

```python
class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="YOULAB_SERVICE_",
        env_file=".env",
        extra="ignore",
    )
```

- Uses `YOULAB_SERVICE_` prefix
- Example: `YOULAB_SERVICE_PORT=8100`

### Fields

```python
# HTTP Server
host: str = "127.0.0.1"
port: int = 8100
api_key: str | None = None
log_level: str = "INFO"

# Letta
letta_base_url: str = "http://localhost:8283"

# Langfuse (defaults to enabled for service)
langfuse_enabled: bool = True
langfuse_public_key: str | None = None
langfuse_secret_key: str | None = None
langfuse_host: str = "https://cloud.langfuse.com"
```

---

## Usage Patterns

### CLI Application

```python
# src/letta_starter/main.py

def main():
    settings = get_settings()

    # Configure logging
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json,
    )

    # Initialize tracing
    if settings.langfuse_enabled:
        init_langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    # Create client
    client = Letta(base_url=settings.letta_base_url)
```

### HTTP Service

```python
# src/letta_starter/server/main.py

settings = ServiceSettings()  # Module-level

app = FastAPI(...)

@asynccontextmanager
async def lifespan(app):
    log.info("starting_service", host=settings.host, port=settings.port)
    app.state.agent_manager = AgentManager(
        letta_base_url=settings.letta_base_url
    )
    yield
```

### Tracing Module

```python
# src/letta_starter/server/tracing.py

settings = ServiceSettings()  # Module-level for patching in tests

def get_langfuse() -> Langfuse | None:
    if not settings.langfuse_enabled:
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
```

---

## Runtime Override

CLI arguments can override settings:

```python
# src/letta_starter/main.py

settings = get_settings()

# Parse CLI args
if args.log_level:
    settings.log_level = args.log_level
if args.json_logs:
    settings.log_json = True
```

---

## Testing

Patch settings for tests:

```python
import pytest
from unittest.mock import patch

def test_with_custom_settings():
    with patch.object(settings, "langfuse_enabled", False):
        result = get_langfuse()
        assert result is None
```

Or use a fixture:

```python
@pytest.fixture
def mock_settings():
    return ServiceSettings(
        letta_base_url="http://test:8283",
        langfuse_enabled=False,
    )
```

---

## Related Pages

- [[Configuration]] - All environment variables
- [[Development]] - Local setup
