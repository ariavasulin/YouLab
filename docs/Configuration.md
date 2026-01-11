# Configuration

[[README|← Back to Overview]]

YouLab uses Pydantic Settings for type-safe environment configuration.

## Quick Reference

### Essential Variables

```bash
# Letta Server
LETTA_BASE_URL=http://localhost:8283

# LLM Provider (choose one)
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...

# HTTP Service
YOULAB_SERVICE_HOST=127.0.0.1
YOULAB_SERVICE_PORT=8100
```

### Environment File

Copy the example and configure:

```bash
cp .env.example .env
vim .env
```

---

## All Environment Variables

### Letta Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `LETTA_BASE_URL` | `http://localhost:8283` | Letta server URL |
| `LETTA_API_KEY` | `null` | API key (if required) |

### LLM Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | Provider: `openai`, `anthropic`, `local` |
| `LLM_MODEL` | `gpt-4` | Default model |
| `OPENAI_API_KEY` | `null` | OpenAI API key |
| `ANTHROPIC_API_KEY` | `null` | Anthropic API key |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_JSON` | `true` | JSON format (true for production) |
| `SERVICE_NAME` | `youlab` | Service identifier |

### Langfuse Tracing

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_ENABLED` | `false` | Enable Langfuse |
| `LANGFUSE_PUBLIC_KEY` | `null` | Public API key |
| `LANGFUSE_SECRET_KEY` | `null` | Secret API key |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host |

### Memory Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CORE_MEMORY_MAX_CHARS` | `1500` | Max chars per memory block |
| `ARCHIVAL_ROTATION_THRESHOLD` | `0.8` | Rotation threshold (0-1) |

### Agent Defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_AGENT_NAME` | `default` | Default agent name |

---

## HTTP Service Variables

All prefixed with `YOULAB_SERVICE_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `YOULAB_SERVICE_HOST` | `127.0.0.1` | Bind host |
| `YOULAB_SERVICE_PORT` | `8100` | Bind port |
| `YOULAB_SERVICE_API_KEY` | `null` | Service authentication |
| `YOULAB_SERVICE_LOG_LEVEL` | `INFO` | Service log level |
| `YOULAB_SERVICE_LETTA_BASE_URL` | `http://localhost:8283` | Letta URL |
| `YOULAB_SERVICE_LANGFUSE_ENABLED` | `true` | Enable tracing |
| `YOULAB_SERVICE_LANGFUSE_PUBLIC_KEY` | `null` | Langfuse public key |
| `YOULAB_SERVICE_LANGFUSE_SECRET_KEY` | `null` | Langfuse secret key |
| `YOULAB_SERVICE_LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host |

### Honcho Message Persistence

| Variable | Default | Description |
|----------|---------|-------------|
| `YOULAB_SERVICE_HONCHO_ENABLED` | `true` | Enable Honcho message persistence |
| `YOULAB_SERVICE_HONCHO_WORKSPACE_ID` | `youlab` | Honcho workspace identifier |
| `YOULAB_SERVICE_HONCHO_API_KEY` | `null` | Honcho API key (required for production) |
| `YOULAB_SERVICE_HONCHO_ENVIRONMENT` | `demo` | Environment: `demo`, `local`, or `production` |

---

## Example Configurations

### Development

```bash
# .env for development
LETTA_BASE_URL=http://localhost:8283
OPENAI_API_KEY=sk-dev-key-here
LOG_LEVEL=DEBUG
LOG_JSON=false
LANGFUSE_ENABLED=false
```

### Production

```bash
# .env for production
LETTA_BASE_URL=http://youlab-server:8283
OPENAI_API_KEY=sk-prod-key-here

LOG_LEVEL=INFO
LOG_JSON=true
SERVICE_NAME=youlab-production

LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx

# Honcho (Theory of Mind)
YOULAB_SERVICE_HONCHO_ENABLED=true
YOULAB_SERVICE_HONCHO_ENVIRONMENT=production
YOULAB_SERVICE_HONCHO_API_KEY=your-honcho-api-key

YOULAB_SERVICE_HOST=0.0.0.0
YOULAB_SERVICE_PORT=8100
```

### Docker

```bash
# When OpenWebUI runs in Docker
YOULAB_SERVICE_HOST=0.0.0.0
# Pipe uses: http://host.docker.internal:8100
```

---

## Settings Classes

YouLab uses two Pydantic settings classes for type-safe configuration.

**Location**: `src/youlab_server/config/settings.py`

| Class | Prefix | Use Case |
|-------|--------|----------|
| `Settings` | (none) | CLI and library |
| `ServiceSettings` | `YOULAB_SERVICE_` | HTTP service |

### Settings Class

General application settings, loaded from `.env`:

```python
from youlab_server.config import get_settings

settings = get_settings()
print(settings.letta_base_url)
```

### ServiceSettings Class

HTTP service-specific settings with `YOULAB_SERVICE_` prefix:

```python
from youlab_server.config.settings import ServiceSettings

settings = ServiceSettings()
uvicorn.run(app, host=settings.host, port=settings.port)
```

### Testing with Settings

```python
from unittest.mock import patch

def test_with_custom_settings():
    with patch.object(settings, "langfuse_enabled", False):
        result = get_langfuse()
        assert result is None
```

---

## Related Pages

- [[Development]] - Local setup
- [[Quickstart]] - Getting started
