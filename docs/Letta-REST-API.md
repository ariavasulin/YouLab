# Letta REST API Reference

[[README|← Back to Overview]]

Complete REST API reference for the Letta server.

## Base URL

| Environment | URL |
|-------------|-----|
| Self-hosted (default) | `http://localhost:8283` |
| Letta Cloud | `https://api.letta.com` |

---

## Authentication

```http
Authorization: Bearer <token>
```

- **Self-hosted**: No authentication required by default
- **Letta Cloud**: Requires API key from [Letta Dashboard](https://app.letta.com)

---

## Agents

### List Agents

```http
GET /v1/agents/
```

**Response**: Array of agent objects

### Create Agent

```http
POST /v1/agents/
```

**Request Body**:

```json
{
  "name": "youlab_user123_tutor",
  "model": "openai/gpt-4o-mini",
  "embedding": "openai/text-embedding-ada-002",
  "memory_blocks": [
    {
      "label": "persona",
      "value": "I am a helpful tutor.",
      "limit": 2000
    },
    {
      "label": "human",
      "value": "User information here.",
      "limit": 2000
    }
  ],
  "tools": ["tool_name"],
  "tool_ids": ["tool-xxx"],
  "metadata": {
    "youlab_user_id": "user123",
    "youlab_agent_type": "tutor"
  },
  "tags": ["youlab", "tutor"]
}
```

**Response**: Created agent object

### Retrieve Agent

```http
GET /v1/agents/{agent_id}
```

### Update Agent

```http
PATCH /v1/agents/{agent_id}
```

### Delete Agent

```http
DELETE /v1/agents/{agent_id}
```

### Export/Import Agent

```http
GET /v1/agents/{agent_id}/export
POST /v1/agents/import
```

---

## Messages

### List Messages

```http
GET /v1/agents/{agent_id}/messages
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max messages to return |
| `before` | string | Cursor for pagination |

### Send Message (Synchronous)

```http
POST /v1/agents/{agent_id}/messages
```

**Request Body**:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hello!"
    }
  ]
}
```

Or shorthand:

```json
{
  "input": "Hello!"
}
```

**Response**:

```json
{
  "messages": [
    {
      "id": "msg-xxx",
      "message_type": "assistant_message",
      "content": "Hello! How can I help?"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 20,
    "total_tokens": 170
  }
}
```

### Send Message (Streaming)

```http
POST /v1/agents/{agent_id}/messages/stream
```

**Request Body**:

```json
{
  "input": "Hello!",
  "stream_tokens": false,
  "include_pings": true
}
```

**Response**: Server-Sent Events stream

```
data: {"message_type":"reasoning_message","reasoning":"User greeted me..."}

data: {"message_type":"assistant_message","content":"Hello!"}

data: {"message_type":"stop_reason","stop_reason":"end_turn"}

data: {"message_type":"usage_statistics","total_tokens":170}
```

### Reset Messages

```http
PATCH /v1/agents/{agent_id}/reset-messages
```

### Cancel Message

```http
POST /v1/agents/{agent_id}/messages/cancel
```

---

## Memory Blocks

### List Blocks

```http
GET /v1/agents/{agent_id}/core-memory/blocks
```

### Get Block by Label

```http
GET /v1/agents/{agent_id}/core-memory/blocks/{block_label}
```

### Update Block

```http
PATCH /v1/agents/{agent_id}/core-memory/blocks/{block_label}
```

**Request Body**:

```json
{
  "value": "Updated content..."
}
```

### Attach Block

```http
PATCH /v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}
```

### Detach Block

```http
PATCH /v1/agents/{agent_id}/core-memory/blocks/detach/{block_id}
```

---

## Global Blocks

Create standalone blocks that can be shared across agents.

### List Blocks

```http
GET /v1/blocks/
```

### Create Block

```http
POST /v1/blocks/
```

**Request Body**:

```json
{
  "label": "shared_context",
  "value": "Shared information...",
  "description": "Context shared across agents",
  "limit": 2000
}
```

### Retrieve Block

```http
GET /v1/blocks/{block_id}
```

### Update Block

```http
PATCH /v1/blocks/{block_id}
```

### Delete Block

```http
DELETE /v1/blocks/{block_id}
```

### List Agents Using Block

```http
GET /v1/blocks/{block_id}/agents
```

---

## Archival Memory (Passages)

### Insert Passage

```http
POST /v1/agents/{agent_id}/archival
```

**Request Body**:

```json
{
  "text": "Important fact to remember",
  "tags": ["category", "important"]
}
```

### List Passages

```http
GET /v1/agents/{agent_id}/archival
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | int | Max passages |
| `ascending` | bool | Sort order |

### Delete Passage

```http
DELETE /v1/agents/{agent_id}/archival/{passage_id}
```

### Search Passages

```http
POST /v1/passages/search
```

**Request Body**:

```json
{
  "agent_id": "agent-xxx",
  "query": "search query",
  "tags": ["category"],
  "page": 0,
  "start_datetime": "2025-01-01T00:00:00Z",
  "end_datetime": "2025-12-31T23:59:59Z"
}
```

**Response**:

```json
{
  "passages": [
    {
      "content": "Matching content...",
      "tags": ["category"],
      "timestamp": "2025-06-15T10:30:00Z",
      "rrf_score": 0.85,
      "vector_rank": 2,
      "fts_rank": 1
    }
  ]
}
```

---

## Tools

### List Tools

```http
GET /v1/tools/
```

### Create Tool

```http
POST /v1/tools/
```

**Request Body**:

```json
{
  "source_code": "def my_tool(arg: str) -> str:\n    \"\"\"Tool description.\"\"\"\n    return f'Result: {arg}'",
  "source_type": "python",
  "tags": ["custom"]
}
```

### Upsert Tool

```http
PUT /v1/tools/
```

### Retrieve Tool

```http
GET /v1/tools/{tool_id}
```

### Update Tool

```http
PATCH /v1/tools/{tool_id}
```

### Delete Tool

```http
DELETE /v1/tools/{tool_id}
```

### Search Tools

```http
POST /v1/tools/search
```

---

## Agent Tools

### List Agent Tools

```http
GET /v1/agents/{agent_id}/tools
```

### Attach Tool

```http
PATCH /v1/agents/{agent_id}/tools/attach/{tool_id}
```

### Detach Tool

```http
PATCH /v1/agents/{agent_id}/tools/detach/{tool_id}
```

### Run Tool

```http
POST /v1/agents/{agent_id}/tools/{tool_name}/run
```

**Request Body**:

```json
{
  "args": {
    "arg1": "value1"
  }
}
```

---

## Runs & Steps (Observability)

### List Runs

```http
GET /v1/runs/
```

### Get Run

```http
GET /v1/runs/{run_id}
```

### Get Run Messages

```http
GET /v1/runs/{run_id}/messages
```

### Get Run Usage

```http
GET /v1/runs/{run_id}/usage
```

### List Steps

```http
GET /v1/steps/
```

### Get Step

```http
GET /v1/steps/{step_id}
```

### Get Step Metrics

```http
GET /v1/steps/{step_id}/metrics
```

### Submit Feedback

```http
PATCH /v1/steps/{step_id}/feedback
```

---

## Models

### List LLM Models

```http
GET /v1/models/
```

### List Embedding Models

```http
GET /v1/models/embedding
```

---

## Health

### Health Check

```http
GET /v1/health
```

**Response**:

```json
{
  "status": "ok"
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

Common status codes:

| Code | Meaning |
|------|---------|
| 400 | Bad request (invalid parameters) |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | Internal server error |

---

## Rate Limits

- **Letta Cloud**: Subject to plan limits
- **Self-hosted**: No limits

---

## External Resources

- [Letta API Reference](https://docs.letta.com/api/)
- [API Overview](https://docs.letta.com/api-reference/overview/)
- [OpenAPI Spec](https://github.com/letta-ai/letta) (generated when running server)

---

## Related Pages

- [[Letta-Concepts]] - Core architecture
- [[Letta-SDK]] - Python SDK patterns
- [[Letta-Streaming]] - Streaming details
- [[API]] - YouLab HTTP service API
