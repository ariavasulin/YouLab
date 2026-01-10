# HTTP Service

[[README|← Back to Overview]]

The HTTP service is a FastAPI application that provides RESTful endpoints for agent management and chat functionality.

## Overview

| Property | Value |
|----------|-------|
| Default Host | `127.0.0.1` |
| Default Port | `8100` |
| Framework | FastAPI |
| Entry Point | `src/letta_starter/server/main.py` |

## Starting the Service

```bash
# Using the CLI
uv run letta-server

# With custom settings
YOULAB_SERVICE_HOST=0.0.0.0 \
YOULAB_SERVICE_PORT=8000 \
uv run letta-server
```

## Endpoints

### Health Check

```http
GET /health
```

Returns service health status and Letta connection state.

**Response**:
```json
{
  "status": "ok",
  "letta_connected": true,
  "honcho_connected": true,
  "version": "0.1.0"
}
```

| Status | Meaning |
|--------|---------|
| `ok` | Service healthy, Letta connected |
| `degraded` | Service running, Letta unavailable |

> **Note**: `honcho_connected` indicates whether Honcho message persistence is available. The service functions without Honcho (messages won't be persisted for ToM analysis).

---

### Create Agent

```http
POST /agents
```

Creates a new agent for a user from a template.

**Request Body**:
```json
{
  "user_id": "user123",
  "agent_type": "tutor",
  "user_name": "Alice"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `user_id` | string | Yes | - | Unique user identifier |
| `agent_type` | string | No | `"tutor"` | Template to use |
| `user_name` | string | No | `null` | User's display name |

**Response** (201 Created):
```json
{
  "agent_id": "agent-abc123",
  "user_id": "user123",
  "agent_type": "tutor",
  "agent_name": "youlab_user123_tutor",
  "created_at": "2025-12-31T10:00:00Z"
}
```

**Errors**:
- `400` - Unknown agent type
- `503` - Letta unavailable

---

### Get Agent

```http
GET /agents/{agent_id}
```

Retrieves agent information by ID.

**Response**:
```json
{
  "agent_id": "agent-abc123",
  "user_id": "user123",
  "agent_type": "tutor",
  "agent_name": "youlab_user123_tutor",
  "created_at": "2025-12-31T10:00:00Z"
}
```

**Errors**:
- `404` - Agent not found

---

### List Agents

```http
GET /agents
GET /agents?user_id=user123
```

Lists agents, optionally filtered by user.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string | Filter by user ID |

**Response**:
```json
{
  "agents": [
    {
      "agent_id": "agent-abc123",
      "user_id": "user123",
      "agent_type": "tutor",
      "agent_name": "youlab_user123_tutor",
      "created_at": "2025-12-31T10:00:00Z"
    }
  ]
}
```

---

### Chat (Synchronous)

```http
POST /chat
```

Sends a message and waits for complete response.

**Request Body**:
```json
{
  "agent_id": "agent-abc123",
  "message": "Help me brainstorm essay topics",
  "chat_id": "chat-xyz",
  "chat_title": "Essay Brainstorming"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | Target agent |
| `message` | string | Yes | User's message |
| `chat_id` | string | No | OpenWebUI chat ID |
| `chat_title` | string | No | Current chat title |

**Response**:
```json
{
  "response": "Great! Let's explore some essay topics...",
  "agent_id": "agent-abc123"
}
```

**Errors**:
- `404` - Agent not found
- `503` - Failed to communicate with agent

---

### Chat (Streaming)

```http
POST /chat/stream
```

Sends a message with Server-Sent Events (SSE) response.

**Request Body**:
```json
{
  "agent_id": "agent-abc123",
  "message": "What makes a compelling personal narrative?",
  "chat_id": "chat-xyz",
  "chat_title": "Essay Writing",
  "enable_thinking": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `agent_id` | string | Yes | - | Target agent |
| `message` | string | Yes | - | User's message |
| `chat_id` | string | No | `null` | Chat ID |
| `chat_title` | string | No | `null` | Chat title |
| `enable_thinking` | bool | No | `true` | Show thinking indicators |

**Response** (SSE stream):
```
data: {"type": "status", "content": "Thinking..."}

data: {"type": "status", "content": "Using memory_search..."}

data: {"type": "message", "content": "A compelling personal narrative has..."}

data: {"type": "done"}
```

**Event Types**:

| Type | Description |
|------|-------------|
| `status` | Processing indicator (thinking, tool use) |
| `message` | Actual response content |
| `done` | Stream complete |
| `error` | Error occurred |

---

## Strategy Endpoints

The strategy agent provides RAG capabilities for project knowledge.

### Upload Document

```http
POST /strategy/documents
```

Uploads content to the strategy agent's archival memory.

**Request Body**:
```json
{
  "content": "# Architecture\n\nYouLab uses a layered architecture...",
  "tags": ["architecture", "design"]
}
```

**Response** (201 Created):
```json
{
  "success": true
}
```

---

### Ask Question

```http
POST /strategy/ask
```

Queries the strategy agent (searches archival memory first).

**Request Body**:
```json
{
  "question": "What is the YouLab architecture?"
}
```

**Response**:
```json
{
  "response": "Based on the documentation, YouLab uses..."
}
```

---

### Search Documents

```http
GET /strategy/documents?query=architecture&limit=5
```

Searches archival memory directly.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | Required | Search query |
| `limit` | int | `5` | Max results |

**Response**:
```json
{
  "documents": [
    "[TAGS: architecture, design]\n# Architecture\n...",
    "[TAGS: overview]\n# System Overview\n..."
  ]
}
```

---

### Strategy Health

```http
GET /strategy/health
```

Checks strategy agent status.

**Response**:
```json
{
  "status": "ready",
  "agent_exists": true
}
```

---

## Background Endpoints

Background agents run scheduled or manual tasks to enrich agent memory using Honcho dialectic queries. See [[Background-Agents]] for full documentation.

**Location**: `src/letta_starter/server/background.py`

### List Background Agents

```http
GET /background/agents
```

Lists all configured background agents across all courses.

**Response**:
```json
[
  {
    "id": "insight-harvester",
    "name": "Student Insight Harvester",
    "course_id": "college-essay",
    "enabled": true,
    "triggers": {
      "schedule": "0 3 * * *",
      "idle_enabled": false,
      "manual": true
    },
    "query_count": 3
  }
]
```

---

### Run Background Agent

```http
POST /background/{agent_id}/run
```

Manually triggers a background agent run.

**Path Parameters**:
| Parameter | Description |
|-----------|-------------|
| `agent_id` | Background agent ID (e.g., `insight-harvester`) |

**Request Body** (optional):
```json
{
  "user_ids": ["user123", "user456"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_ids` | array | No | Specific users to process (null = all) |

**Response**:
```json
{
  "agent_id": "insight-harvester",
  "started_at": "2025-01-08T03:00:00Z",
  "completed_at": "2025-01-08T03:05:00Z",
  "users_processed": 25,
  "queries_executed": 75,
  "enrichments_applied": 68,
  "error_count": 7,
  "errors": ["Enrichment failed for user789/learning_style: ..."]
}
```

**Errors**:
- `404` - Background agent not found
- `500` - Background system not initialized

---

### Reload Configuration

```http
POST /background/config/reload
```

Hot-reloads TOML configuration files from disk.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_dir` | string | `config/courses` | Directory to load from |

**Response**:
```json
{
  "success": true,
  "courses_loaded": 1,
  "course_ids": ["college-essay"],
  "message": "Configuration reloaded successfully"
}
```

---

## Curriculum Endpoints

The curriculum system provides course configuration management.

**Location**: `src/letta_starter/server/curriculum.py`

### List Courses

```http
GET /curriculum/courses
```

Lists all available courses.

**Response**:
```json
{
  "courses": ["default", "college-essay"],
  "count": 2
}
```

---

### Get Course Details

```http
GET /curriculum/courses/{course_id}
```

Returns course metadata and structure.

**Response**:
```json
{
  "id": "college-essay",
  "name": "College Essay Coaching",
  "version": "1.0.0",
  "description": "AI-powered tutoring for college application essays",
  "modules": [
    {"id": "01-self-discovery", "name": "Self-Discovery", "step_count": 3}
  ],
  "blocks": [
    {"name": "persona", "label": "persona", "field_count": 7}
  ],
  "background_agents": ["insight-harvester"],
  "tool_count": 3
}
```

---

### Get Full Course Config

```http
GET /curriculum/courses/{course_id}/full
```

Returns complete course configuration as JSON (useful for debugging or UI editors).

**Response**: Full `CourseConfig` serialized to JSON.

---

### Get Course Modules

```http
GET /curriculum/courses/{course_id}/modules
```

Returns all modules with full step details.

**Response**: List of `ModuleConfig` serialized to JSON.

---

### Reload Configuration

```http
POST /curriculum/reload
```

Hot-reloads all curriculum configurations from disk.

**Response**:
```json
{
  "success": true,
  "courses_loaded": 2,
  "courses": ["default", "college-essay"],
  "message": "Configuration reloaded successfully"
}
```

---

## AgentManager

The `AgentManager` class handles all agent operations.

### Agent Naming

```python
agent_name = f"youlab_{user_id}_{agent_type}"
# Example: youlab_user123_tutor
```

### Agent Metadata

```python
metadata = {
    "youlab_user_id": user_id,
    "youlab_agent_type": agent_type,
}
```

### Caching

```python
# Cache structure
_cache: dict[tuple[str, str], str]  # (user_id, agent_type) -> agent_id

# Lookup order
1. Check cache
2. Query Letta by agent name
3. Return None if not found
```

### Cache Rebuild

On service startup, the cache is rebuilt from Letta:

```python
async def lifespan(app):
    count = await app.state.agent_manager.rebuild_cache()
    log.info("startup_complete", cached_agents=count)
```

### Curriculum-Based Agent Creation

Agents can be created from TOML course configurations:

```python
agent_id = manager.create_agent_from_curriculum(
    user_id="user123",
    course_id="college-essay",
    user_name="Alice",
    block_overrides={"human": {"name": "Alice"}},
)
```

This method:
- Loads configuration from `config/courses/{course_id}/course.toml`
- Builds memory blocks from TOML schema definitions
- Configures tools and tool rules from course config
- Uses course-specified model and embedding
- Adds course metadata to agent

---

## Streaming Implementation

### Letta Chunk Types

The service translates Letta streaming chunks to SSE events:

| Letta Type | SSE Event |
|------------|-----------|
| `reasoning_message` | `{"type": "status", "content": "Thinking..."}` |
| `tool_call_message` | `{"type": "status", "content": "Using {tool}..."}` |
| `assistant_message` | `{"type": "message", "content": "..."}` |
| `stop_reason` | `{"type": "done"}` |
| `ping` | `": keepalive\n\n"` |
| `error_message` | `{"type": "error", "message": "..."}` |

### Metadata Stripping

Letta appends JSON metadata to messages. The service strips it:

```python
# Before: "Here are some topics...{"follow_ups": ["What about..."]}"
# After:  "Here are some topics..."
```

---

## Tracing

All chat requests are traced via Langfuse:

```python
with trace_chat(
    user_id=user_id,
    agent_id=request.agent_id,
    chat_id=request.chat_id,
    metadata={"chat_title": request.chat_title},
) as trace_ctx:
    response_text = manager.send_message(...)
    trace_generation(trace_ctx, ...)
```

See [[Configuration]] for Langfuse settings.

---

## Error Handling

| Status | Condition |
|--------|-----------|
| `400` | Invalid request (unknown agent type) |
| `404` | Agent not found |
| `500` | Internal error |
| `503` | Letta unavailable |

All errors include a `detail` field:

```json
{
  "detail": "Agent not found: agent-abc123"
}
```

---

## Related Pages

- [[API]] - Complete API reference
- [[Schemas]] - Request/response models
- [[Configuration]] - Service settings
- [[Strategy-Agent]] - Strategy agent details
- [[Background-Agents]] - Background agent system details
- [[Honcho]] - Honcho integration and dialectic queries
