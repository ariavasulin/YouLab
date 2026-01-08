# Changelog

[[README|← Back to Overview]]

All notable changes to YouLab.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- **Thread Context Management**: Chat title operations for thread context
  - `_set_chat_title()` method to rename chats programmatically
  - Uses OpenWebUI's `Chats.update_chat_title_by_id()` API
  - Unit tests for title get/set operations
- **Honcho Integration**: Message persistence for theory-of-mind modeling
  - `HonchoClient` for async message persistence
  - Fire-and-forget pattern for non-blocking chat
  - Health endpoint reports Honcho connection status
  - Configuration via `YOULAB_SERVICE_HONCHO_*` environment variables
  - Graceful degradation when Honcho unavailable
- Documentation site using Docsify
- Complete API reference
- Development and testing guides

---

## [0.1.0] - 2025-12-31

Initial release with Phase 1 complete.

### Added

#### HTTP Service
- FastAPI server on port 8100
- Health endpoint (`GET /health`) with Letta connection status
- Agent management endpoints (`POST/GET /agents`)
- Synchronous chat endpoint (`POST /chat`)
- SSE streaming chat endpoint (`POST /chat/stream`)
- Request/response schemas with Pydantic
- Agent template system for different agent types

#### Strategy Agent
- Singleton RAG-enabled agent (YouLab-Support)
- Document upload endpoint (`POST /strategy/documents`)
- Question answering endpoint (`POST /strategy/ask`)
- Document search endpoint (`GET /strategy/documents`)
- Strategy health endpoint (`GET /strategy/health`)

#### Memory System
- PersonaBlock for agent identity
- HumanBlock for user context
- Rotation strategies (Aggressive, Preservative, Adaptive)
- MemoryManager for lifecycle orchestration
- Archival memory integration

#### Agent System
- AgentTemplate for defining agent types
- AgentTemplateRegistry for managing templates
- TUTOR_TEMPLATE for essay coaching
- BaseAgent with integrated memory and tracing

#### Pipeline
- OpenWebUI Pipe integration
- User context extraction
- Chat context extraction
- SSE event transformation

#### Observability
- Langfuse tracing integration
- Structlog logging
- Context-aware tracing

#### Development
- Makefile with agent-optimized commands
- Pre-commit hooks
- Ruff linting and formatting
- Basedpyright type checking
- Pytest test suite

### Technical Decisions

| Decision | Choice |
|----------|--------|
| API Framework | FastAPI |
| Port | 8100 |
| Agent Naming | `youlab_{user_id}_{agent_type}` |
| Agent Creation | Explicit `POST /agents` endpoint |
| Authentication | Trust localhost (API key designed for later) |
| Memory Format | Token-efficient bracket notation |
| Rotation Threshold | 80% (adaptive) |

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2025-12-31 | Phase 1: HTTP Service |

---

## Migration Notes

### From Library to HTTP Service

Prior versions used LettaStarter as an imported library. Version 0.1.0 introduces the HTTP service architecture:

**Before**:
```python
from letta_starter import create_agent
agent = create_agent(user_id="...")
```

**After**:
```bash
# Start the service
uv run letta-server

# Call via HTTP
curl -X POST http://localhost:8100/agents \
  -H "Content-Type: application/json" \
  -d '{"user_id": "...", "agent_type": "tutor"}'
```

### Pipeline Changes

The OpenWebUI Pipe now calls the HTTP service instead of importing LettaStarter:

**Before**:
```python
# Pipe imported and called LettaStarter directly
from letta_starter import send_message
response = send_message(agent_id, message)
```

**After**:
```python
# Pipe calls HTTP service
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{LETTA_SERVICE_URL}/chat/stream",
        json={"agent_id": agent_id, "message": message}
    )
```

---

## Related Pages

- [[Roadmap]] - Future plans
- [[Architecture]] - System design
- [[HTTP-Service]] - Service details

