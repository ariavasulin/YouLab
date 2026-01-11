# HTTP Service

[[README|<- Back to Overview]]

The HTTP service is a FastAPI application providing agent management and chat functionality.

## Quick Reference

| Property | Value |
|----------|-------|
| Default Host | `127.0.0.1` |
| Default Port | `8100` |
| Framework | FastAPI |
| Entry Point | `src/letta_starter/server/main.py` |

```bash
# Start the service
uv run letta-server

# With custom settings
YOULAB_SERVICE_HOST=0.0.0.0 YOULAB_SERVICE_PORT=8000 uv run letta-server
```

For complete API reference, see [[API]].

---

## Service Architecture

```
HTTP Service (FastAPI)
|- /health           - Health check
|- /agents/*         - Agent CRUD (AgentManager)
|- /chat/*           - Chat endpoints
|- /strategy/*       - Strategy agent (StrategyManager)
|- /background/*     - Background agents
|- /curriculum/*     - Course management
|- /sync/*           - File sync (OpenWebUI -> Letta)
```

---

## AgentManager

Manages per-user agents with caching.

**Location**: `src/letta_starter/server/agents.py`

### Naming Convention

```python
agent_name = f"youlab_{user_id}_{course_id}"
# Example: youlab_user123_college-essay
```

### Caching

```python
# Cache structure
_cache: dict[tuple[str, str], str]  # (user_id, course_id) -> agent_id

# On startup, cache is rebuilt from Letta
async def lifespan(app):
    count = await app.state.agent_manager.rebuild_cache()
```

---

## Strategy Agent

A singleton RAG-enabled agent for project-wide knowledge queries.

**Location**: `src/letta_starter/server/strategy/`

| Aspect | User Agents | Strategy Agent |
|--------|-------------|----------------|
| Count | 1 per user | 1 per system |
| Name | `youlab_{user_id}_{course}` | `YouLab-Support` |
| Purpose | Tutoring | Project knowledge |
| Endpoints | `/agents/*`, `/chat/*` | `/strategy/*` |

### StrategyManager

```python
manager = StrategyManager(letta_base_url="http://localhost:8283")
agent_id = manager.ensure_agent()  # Gets or creates singleton
manager.upload_document(content="...", tags=["docs"])
response = manager.ask("How does streaming work?")
```

---

## Streaming Implementation

The service translates Letta streaming chunks to SSE events.

### Chunk Mapping

| Letta Type | SSE Event |
|------------|-----------|
| `reasoning_message` | `{"type": "status", "content": "Thinking..."}` |
| `tool_call_message` | `{"type": "status", "content": "Using {tool}..."}` |
| `assistant_message` | `{"type": "message", "content": "..."}` |
| `stop_reason` | `{"type": "done"}` |
| `ping` | `": keepalive\n\n"` |

### Metadata Stripping

Letta appends JSON metadata to messages. The service strips it:

```python
# Before: "Hello!{"follow_ups": ["Tell me more"]}"
# After:  "Hello!"
```

---

## Tracing

All chat requests are traced via Langfuse:

```python
with trace_chat(
    user_id=user_id,
    agent_id=request.agent_id,
    chat_id=request.chat_id,
) as trace_ctx:
    response = manager.send_message(...)
```

See [[Configuration]] for Langfuse settings.

---

## Related Pages

- [[API]] - Complete endpoint reference
- [[Schemas]] - Request/response models
- [[Configuration]] - Service settings
- [[Background-Agents]] - Background agent system
