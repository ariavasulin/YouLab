# API Reference

[[README|← Back to Overview]]

Complete HTTP API reference for the YouLab service.

## Base URL

```
http://localhost:8100
```

## Authentication

Currently no authentication required. Optional API key support via `YOULAB_SERVICE_API_KEY`.

---

## Health

### GET /health

Check service health and Letta connection.

**Response**:
```json
{
  "status": "ok",
  "letta_connected": true,
  "version": "0.1.0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` or `"degraded"` |
| `letta_connected` | boolean | Letta server reachable |
| `version` | string | Service version (e.g., `"0.1.0"`) |

---

## Agents

### POST /agents

Create a new agent for a user.

**Request**:
```json
{
  "user_id": "user123",
  "agent_type": "tutor",
  "user_name": "Alice"
}
```

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `user_id` | string | Yes | - |
| `agent_type` | string | No | `"tutor"` |
| `user_name` | string | No | `null` |

**Response** (201):
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
- `500` - Agent created but info retrieval failed
- `503` - Letta unavailable

---

### GET /agents/{agent_id}

Get agent by ID.

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

### GET /agents

List agents.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string | Filter by user |

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

## Chat

### POST /chat

Send message (synchronous).

**Request**:
```json
{
  "agent_id": "agent-abc123",
  "message": "Help me brainstorm essay topics",
  "chat_id": "chat-xyz",
  "chat_title": "Essay Brainstorming"
}
```

| Field | Type | Required |
|-------|------|----------|
| `agent_id` | string | Yes |
| `message` | string | Yes |
| `chat_id` | string | No |
| `chat_title` | string | No |

**Response**:
```json
{
  "response": "Great! Let's explore some essay topics...",
  "agent_id": "agent-abc123"
}
```

**Errors**:
- `404` - Agent not found
- `503` - Communication failed

---

### POST /chat/stream

Send message with SSE streaming.

**Request**:
```json
{
  "agent_id": "agent-abc123",
  "message": "What makes a compelling narrative?",
  "chat_id": "chat-xyz",
  "chat_title": "Essay Writing",
  "enable_thinking": true
}
```

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `agent_id` | string | Yes | - |
| `message` | string | Yes | - |
| `chat_id` | string | No | `null` |
| `chat_title` | string | No | `null` |
| `enable_thinking` | boolean | No | `true` |

**Response** (SSE):
```
data: {"type": "status", "content": "Thinking..."}

data: {"type": "message", "content": "A compelling narrative..."}

data: {"type": "done"}
```

**Event Types**:
| Type | Description |
|------|-------------|
| `status` | Processing indicator |
| `message` | Response content |
| `done` | Stream complete |
| `error` | Error message |

---

## Strategy

### POST /strategy/documents

Upload document to archival memory.

**Request**:
```json
{
  "content": "# Architecture\n\nYouLab uses...",
  "tags": ["architecture", "design"]
}
```

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `content` | string | Yes | - |
| `tags` | array[string] | No | `[]` |

**Response** (201):
```json
{
  "success": true
}
```

**Errors**:
- `503` - Letta unavailable

---

### POST /strategy/ask

Query strategy agent.

**Request**:
```json
{
  "question": "What is the YouLab architecture?"
}
```

**Response**:
```json
{
  "response": "Based on the documentation..."
}
```

**Errors**:
- `503` - Letta unavailable

---

### GET /strategy/documents

Search archival memory.

**Query Parameters**:
| Parameter | Type | Default |
|-----------|------|---------|
| `query` | string | Required |
| `limit` | integer | `5` |

**Response**:
```json
{
  "documents": [
    "[TAGS: architecture]\n# Architecture\n..."
  ]
}
```

**Errors**:
- `503` - Letta unavailable

---

### GET /strategy/health

Check strategy agent status.

**Response**:
```json
{
  "status": "ready",
  "agent_exists": true
}
```

| Status | Meaning |
|--------|---------|
| `ready` | Agent exists |
| `not_ready` | Agent not created |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

| Code | Meaning |
|------|---------|
| `400` | Bad request (invalid input) |
| `404` | Resource not found |
| `500` | Internal server error |
| `503` | Service unavailable (Letta down) |

---

## cURL Examples

### Create Agent
```bash
curl -X POST http://localhost:8100/agents \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "agent_type": "tutor"}'
```

### Send Message
```bash
curl -X POST http://localhost:8100/chat \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "...", "message": "Hello"}'
```

### Stream Response
```bash
curl -N -X POST http://localhost:8100/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "...", "message": "Hello"}'
```

### Upload Document
```bash
curl -X POST http://localhost:8100/strategy/documents \
  -H "Content-Type: application/json" \
  -d '{"content": "# Docs", "tags": ["docs"]}'
```

---

## Related Pages

- [[HTTP-Service]] - Implementation details
- [[Schemas]] - Request/response models
- [[Quickstart]] - Getting started
