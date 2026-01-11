# Pipeline Integration

[[README|← Back to Overview]]

The Pipeline (Pipe) connects OpenWebUI to the YouLab HTTP service.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        OpenWebUI                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  User       │  │  Chat       │  │  __event_emitter__  │  │
│  │  Context    │  │  Context    │  │  (SSE to UI)        │  │
│  │  __user__   │  │  __metadata │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────▲──────────┘  │
│         │                │                     │             │
└─────────┼────────────────┼─────────────────────┼─────────────┘
          │                │                     │
          ▼                ▼                     │
┌─────────────────────────────────────────────────────────────┐
│                      Pipe.pipe()                             │
│                                                              │
│  1. Extract user_id, user_name from __user__                │
│  2. Extract chat_id from __metadata__                       │
│  3. Get chat_title via Chats.get_chat_by_id()               │
│  4. Ensure agent exists (GET/POST /agents)                  │
│  5. Stream from POST /chat/stream                           │
│  6. Transform SSE events for OpenWebUI                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│              HTTP Service (localhost:8100)                   │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

The Pipe class exposes configuration through Valves:

**Location**: `src/youlab_server/pipelines/letta_pipe.py:21-39`

```python
class Valves(BaseModel):
    LETTA_SERVICE_URL: str = "http://host.docker.internal:8100"
    AGENT_TYPE: str = "tutor"
    ENABLE_LOGGING: bool = True
    ENABLE_THINKING: bool = True
```

| Valve | Default | Description |
|-------|---------|-------------|
| `LETTA_SERVICE_URL` | `host.docker.internal:8100` | HTTP service URL |
| `AGENT_TYPE` | `tutor` | Agent template to use |
| `ENABLE_LOGGING` | `true` | Debug logging |
| `ENABLE_THINKING` | `true` | Show thinking indicators |

> **Note**: Use `host.docker.internal` when OpenWebUI runs in Docker but the HTTP service runs on the host.

## Context Extraction

### User Context

```python
# From __user__ parameter
user_id = __user__.get("id")    # Unique user identifier
user_name = __user__.get("name") # Display name
```

### Chat Context

```python
# From __metadata__ parameter
chat_id = __metadata__.get("chat_id")

# From OpenWebUI database
from open_webui.models.chats import Chats
chat = Chats.get_chat_by_id(chat_id)
chat_title = chat.title if chat else None
```

> **Note**: `chat_id` starting with `local:` indicates a temporary chat - title lookup returns `None`.

## Agent Provisioning

The Pipe ensures an agent exists before each message:

```python
async def _ensure_agent_exists(client, user_id, user_name):
    # 1. Check for existing agent
    response = await client.get(
        f"{LETTA_SERVICE_URL}/agents",
        params={"user_id": user_id}
    )
    for agent in response.json()["agents"]:
        if agent["agent_type"] == AGENT_TYPE:
            return agent["agent_id"]

    # 2. Create new agent
    response = await client.post(
        f"{LETTA_SERVICE_URL}/agents",
        json={
            "user_id": user_id,
            "agent_type": AGENT_TYPE,
            "user_name": user_name,
        }
    )
    return response.json()["agent_id"]
```

## Streaming Flow

### 1. Connect to HTTP Service

```python
async with aconnect_sse(
    client,
    "POST",
    f"{LETTA_SERVICE_URL}/chat/stream",
    json={
        "agent_id": agent_id,
        "message": user_message,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "enable_thinking": ENABLE_THINKING,
    }
) as event_source:
    async for sse in event_source.aiter_sse():
        await _handle_sse_event(sse.data, __event_emitter__)
```

### 2. Transform Events

```python
async def _handle_sse_event(data, emitter):
    event = json.loads(data)
    event_type = event.get("type")

    if event_type == "status":
        await emitter({
            "type": "status",
            "data": {
                "description": event.get("content", "Processing..."),
                "done": False,
            }
        })
    elif event_type == "message":
        await emitter({
            "type": "message",
            "data": {"content": event.get("content", "")}
        })
    elif event_type == "done":
        await emitter({
            "type": "status",
            "data": {"description": "Complete", "done": True}
        })
    elif event_type == "error":
        await emitter({
            "type": "message",
            "data": {"content": f"Error: {event.get('message', 'Unknown')}"}
        })
```

### Event Mapping

| HTTP Service Event | OpenWebUI Event |
|--------------------|-----------------|
| `{"type": "status", "content": "Thinking..."}` | `{"type": "status", "data": {"description": "Thinking...", "done": false}}` |
| `{"type": "message", "content": "..."}` | `{"type": "message", "data": {"content": "..."}}` |
| `{"type": "done"}` | `{"type": "status", "data": {"description": "Complete", "done": true}}` |
| `{"type": "error", "message": "..."}` | `{"type": "message", "data": {"content": "Error: ..."}}` |

## Error Handling

### Timeout

```python
except httpx.TimeoutException:
    await __event_emitter__({
        "type": "message",
        "data": {"content": "Error: Request timed out."}
    })
```

### Connection Error

```python
except httpx.ConnectError:
    await __event_emitter__({
        "type": "message",
        "data": {"content": "Error: Could not connect to tutor service."}
    })
```

### General Error

```python
except Exception as e:
    if ENABLE_LOGGING:
        print(f"YouLab error: {e}")
    await __event_emitter__({
        "type": "message",
        "data": {"content": f"Error: {str(e)}"}
    })
```

## Lifecycle Hooks

```python
async def on_startup(self):
    if self.valves.ENABLE_LOGGING:
        print(f"YouLab Pipe started. Service: {self.valves.LETTA_SERVICE_URL}")

async def on_shutdown(self):
    if self.valves.ENABLE_LOGGING:
        print("YouLab Pipe stopped")

async def on_valves_updated(self):
    if self.valves.ENABLE_LOGGING:
        print("YouLab Pipe valves updated")
```

## Installation

### 1. Copy the Pipe File

Copy `src/youlab_server/pipelines/letta_pipe.py` to OpenWebUI's functions directory.

### 2. Register in OpenWebUI

In OpenWebUI Admin:
1. Go to Functions > Pipes
2. Add new Pipe
3. Paste the Pipe code
4. Configure Valves

### 3. Configure Valves

Set the appropriate values:

```
LETTA_SERVICE_URL: http://localhost:8100  # If not using Docker
# or
LETTA_SERVICE_URL: http://host.docker.internal:8100  # If OpenWebUI in Docker
```

## Debugging

Enable logging to see detailed flow:

```
ENABLE_LOGGING: true
```

Logs will show:
- Service URL on startup
- User and chat IDs for each message
- Errors with full details

## Related Pages

- [[HTTP-Service]] - Backend endpoints
- [[Architecture]] - System overview
- [[Configuration]] - Environment setup
