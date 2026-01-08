# Honcho Integration

[[README|← Back to Overview]]

Honcho provides message persistence for theory-of-mind (ToM) modeling in YouLab.

## Overview

Honcho captures all chat messages for long-term analysis:
- **User messages** - What students say
- **Agent responses** - What the tutor replies
- **Session context** - Chat IDs, titles, agent types

This enables future ToM features like:
- Student behavior modeling
- Learning pattern analysis
- Personalized recommendations

```
┌─────────────────────────────────────────────────────────────┐
│                      Chat Flow                               │
│                                                              │
│  User Message ──► HTTP Service ──► Letta Server             │
│                        │                                     │
│                        ▼                                     │
│                   HonchoClient                               │
│                   (fire-and-forget)                          │
│                        │                                     │
│                        ▼                                     │
│                  Honcho Service                              │
│              (message persistence)                           │
└─────────────────────────────────────────────────────────────┘
```

## Architecture

### Honcho Concepts

| Concept | YouLab Mapping | Example |
|---------|---------------|---------|
| Workspace | Application | `youlab` |
| Peer | Message sender | `student_{user_id}`, `tutor` |
| Session | Chat thread | `chat_{chat_id}` |
| Message | Individual message | User or agent content |

### Data Model

```
Workspace: "youlab"
├── Peer: "student_user123"
│   └── Messages from this student
├── Peer: "student_user456"
│   └── Messages from this student
├── Peer: "tutor"
│   └── All agent responses
└── Session: "chat_abc123"
    └── Messages in this chat thread
```

---

## HonchoClient

**Location**: `src/letta_starter/honcho/client.py`

### Initialization

```python
from letta_starter.honcho import HonchoClient

client = HonchoClient(
    workspace_id="youlab",
    api_key=None,  # Required for production
    environment="demo",  # demo, local, or production
)
```

### Lazy Loading

The Honcho SDK client is lazily initialized on first use:

```python
@property
def client(self) -> Honcho | None:
    if self._client is None and not self._initialized:
        self._initialized = True
        # Initialize Honcho SDK...
    return self._client
```

If initialization fails (network error, invalid credentials), `client` returns `None` and persistence is silently skipped.

### Methods

#### persist_user_message()

Persist a user's message:

```python
await client.persist_user_message(
    user_id="user123",
    chat_id="chat456",
    message="Help me brainstorm essay topics",
    chat_title="Essay Brainstorming",
    agent_type="tutor",
)
```

#### persist_agent_message()

Persist an agent's response:

```python
await client.persist_agent_message(
    user_id="user123",  # Which student this was for
    chat_id="chat456",
    message="Great! Let's explore some topics...",
    chat_title="Essay Brainstorming",
    agent_type="tutor",
)
```

#### check_connection()

Verify Honcho is reachable:

```python
if client.check_connection():
    print("Honcho is available")
```

#### query_dialectic()

Query Honcho for insights about a student (theory-of-mind):

```python
from letta_starter.honcho.client import SessionScope

response = await client.query_dialectic(
    user_id="user123",
    question="What learning style works best for this student?",
    session_scope=SessionScope.ALL,
    recent_limit=5,
)

if response:
    print(response.insight)  # "This student prefers hands-on examples..."
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | string | Required | Student identifier |
| `question` | string | Required | Natural language question |
| `session_scope` | SessionScope | `ALL` | Which sessions to include |
| `session_id` | string | `None` | Specific session (reserved) |
| `recent_limit` | int | `5` | Number of recent sessions (reserved) |

**SessionScope enum**:

| Value | Description |
|-------|-------------|
| `ALL` | All sessions for this user |
| `RECENT` | Last N sessions |
| `CURRENT` | Current/active session only |
| `SPECIFIC` | Explicit session ID |

**Returns**: `DialecticResponse` or `None` if unavailable.

```python
@dataclass
class DialecticResponse:
    insight: str        # Honcho's analysis
    session_scope: SessionScope
    query: str          # Original question
```

---

## Fire-and-Forget Pattern

**Location**: `src/letta_starter/honcho/client.py:220-272`

Messages are persisted asynchronously without blocking the chat response:

```python
from letta_starter.honcho.client import create_persist_task

# In chat endpoint - doesn't block response
create_persist_task(
    honcho_client=honcho,
    user_id="user123",
    chat_id="chat456",
    message="User's message",
    is_user=True,
    chat_title="My Chat",
    agent_type="tutor",
)
```

### Graceful Degradation

- If `honcho_client` is `None`, persistence is skipped
- If `chat_id` is empty, persistence is skipped
- If Honcho is unreachable, errors are logged but not raised
- Chat functionality continues regardless of Honcho status

---

## HTTP Service Integration

**Location**: `src/letta_starter/server/main.py`

### Initialization

Honcho is initialized during service startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... other initialization ...

    if settings.honcho_enabled:
        app.state.honcho_client = HonchoClient(
            workspace_id=settings.honcho_workspace_id,
            api_key=settings.honcho_api_key,
            environment=settings.honcho_environment,
        )
        honcho_ok = app.state.honcho_client.check_connection()
        log.info("honcho_initialized", connected=honcho_ok)
    else:
        app.state.honcho_client = None
        log.info("honcho_disabled")
```

### Health Endpoint

The `/health` endpoint reports Honcho status:

```json
{
  "status": "ok",
  "letta_connected": true,
  "honcho_connected": true,
  "version": "0.1.0"
}
```

### Chat Endpoints

Both `/chat` and `/chat/stream` persist messages:

1. **User message** - Persisted before sending to Letta
2. **Agent response** - Persisted after receiving from Letta

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YOULAB_SERVICE_HONCHO_ENABLED` | `true` | Enable persistence |
| `YOULAB_SERVICE_HONCHO_WORKSPACE_ID` | `youlab` | Workspace ID |
| `YOULAB_SERVICE_HONCHO_API_KEY` | `null` | API key (production) |
| `YOULAB_SERVICE_HONCHO_ENVIRONMENT` | `demo` | Environment |

### Environments

| Environment | Use Case | API Key |
|-------------|----------|---------|
| `demo` | Development/testing | Not required |
| `local` | Local Honcho server | Not required |
| `production` | Production deployment | Required |

---

## Metadata

Messages include metadata for context:

```python
metadata = {
    "chat_id": "chat456",
    "agent_type": "tutor",
    "chat_title": "Essay Brainstorming",  # Optional
    "user_id": "user123",  # Agent messages only
}
```

---

## Related Pages

- [[Architecture]] - System overview with Honcho
- [[HTTP-Service]] - Chat endpoint details
- [[Background-Agents]] - Background agents using dialectic queries
- [[Agent-Tools]] - Agent tools including query_honcho
- [[Configuration]] - Environment variables
- [[Roadmap]] - ToM integration plans
