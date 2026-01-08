# Architecture

[[README|← Back to Overview]]

## System Overview

YouLab is built as a layered architecture where each component has a single responsibility:

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenWebUI                               │
│                   (Chat Interface)                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline (Pipe)                           │
│  • Extract user_id, chat_id from OpenWebUI                  │
│  • Ensure agent exists for user                              │
│  • Stream SSE responses back to UI                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              HTTP Service (FastAPI :8100)                    │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │  AgentManager    │  │ StrategyManager  │                 │
│  │  (per-user)      │  │ (singleton RAG)  │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
│           │                     │                            │
│           └──────────┬──────────┘                            │
│                      │                                       │
│           ┌──────────┴──────────┐                            │
│           │    HonchoClient     │                            │
│           │ (message persist)   │                            │
│           └──────────┬──────────┘                            │
└──────────────────────┼──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│  Letta Server       │   │   Honcho Service    │
│  (:8283)            │   │   (ToM Layer)       │
│  • Agent lifecycle  │   │   • Message store   │
│  • Core memory      │   │   • Session mgmt    │
│  • Archival memory  │   │   • Peer tracking   │
│  • Tool execution   │   │                     │
└─────────┬───────────┘   └─────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Claude API                                │
│              (via OpenAI compatibility)                      │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### OpenWebUI

The chat frontend that users interact with. Provides:
- Chat interface with message history
- User authentication and sessions
- Pipe extension system for custom backends
- Chat title management

### Pipeline (Pipe)

The bridge between OpenWebUI and the HTTP service:

| Responsibility | Implementation |
|---------------|----------------|
| User context extraction | `__user__["id"]`, `__user__["name"]` |
| Chat context | `__metadata__["chat_id"]`, `Chats.get_chat_by_id()` |
| Agent provisioning | `POST /agents` on first message |
| Response streaming | SSE via `httpx-sse` |

**Location**: `src/letta_starter/pipelines/letta_pipe.py`

### HTTP Service

FastAPI application providing RESTful endpoints:

| Domain | Endpoints | Manager |
|--------|-----------|---------|
| Agent CRUD | `/agents`, `/agents/{id}` | AgentManager |
| Chat | `/chat`, `/chat/stream` | AgentManager |
| Strategy | `/strategy/*` | StrategyManager |
| Background | `/background/*` | BackgroundAgentRunner |
| Health | `/health` | - |

**Location**: `src/letta_starter/server/`

### AgentManager

Manages per-user Letta agents:

```python
# Agent naming convention
agent_name = f"youlab_{user_id}_{agent_type}"
# Example: youlab_user123_tutor

# Cache structure
cache: dict[tuple[str, str], str]  # (user_id, agent_type) -> agent_id
```

**Key Features**:
- Lazy agent creation from templates
- Agent caching for fast lookups
- Cache rebuild on service startup
- Streaming with Letta metadata stripping

### StrategyManager

Singleton RAG agent for project knowledge:

```python
# Single shared agent
AGENT_NAME = "YouLab-Support"

# Persona instructs archival search
"CRITICAL: Before answering ANY question about YouLab:
1. Use archival_memory_search to find relevant documentation"
```

**Use Cases**:
- Upload project documentation
- Query project knowledge
- Search archival memory

### Letta Server

The underlying agent framework:

| Feature | Purpose |
|---------|---------|
| Core Memory | Persona + Human blocks in context |
| Archival Memory | Vector-indexed long-term storage |
| Tool System | Function calling for agents |
| Streaming | Real-time response generation |

## Data Flow

### Message Flow

```
User types "Help me brainstorm essay topics"
         │
         ▼
┌─────────────────┐
│    OpenWebUI    │ 1. Captures message
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Pipe.pipe()  │ 2. Extracts user_id="user123"
│                 │ 3. Calls _ensure_agent_exists()
│                 │ 4. POSTs to /chat/stream
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   HTTP Service  │ 5. Validates agent exists
│                 │ 6. Calls stream_message()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Letta Server   │ 7. Loads agent with memory
│                 │ 8. Generates response via Claude
│                 │ 9. Streams chunks back
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Pipeline     │ 10. Transforms to OpenWebUI events
│                 │ 11. Emits via __event_emitter__
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    OpenWebUI    │ 12. Displays streaming response
└─────────────────┘
```

### Memory Flow

```
┌─────────────────────────────────────────┐
│              Core Memory                 │
│  ┌─────────────┐  ┌─────────────┐       │
│  │   Persona   │  │    Human    │       │
│  │   Block     │  │    Block    │       │
│  │             │  │             │       │
│  │ [IDENTITY]  │  │ [USER]      │       │
│  │ [CAPS]      │  │ [TASK]      │       │
│  │ [STYLE]     │  │ [CONTEXT]   │       │
│  └─────────────┘  └──────┬──────┘       │
│                          │               │
│         Rotation when >80% capacity      │
│                          │               │
└──────────────────────────┼──────────────┘
                           │
                           ▼
┌─────────────────────────────────────────┐
│           Archival Memory                │
│                                          │
│  [ARCHIVED 2025-12-31T10:00:00]         │
│  Previous context notes and tasks        │
│                                          │
│  [TASK COMPLETED 2025-12-30T15:00:00]   │
│  Brainstormed 5 essay topics             │
│                                          │
└─────────────────────────────────────────┘
```

## Project Structure

```
src/letta_starter/
├── agents/              # Agent creation and management
│   ├── base.py          # BaseAgent class
│   ├── default.py       # Factory functions, AgentRegistry
│   └── templates.py     # AgentTemplate, TUTOR_TEMPLATE
│
├── background/          # Background agent system
│   ├── schema.py        # TOML config schemas (CourseConfig, etc.)
│   └── runner.py        # BackgroundAgentRunner execution engine
│
├── config/              # Configuration
│   └── settings.py      # Settings, ServiceSettings
│
├── honcho/              # Message persistence + dialectic
│   ├── __init__.py      # Exports HonchoClient
│   └── client.py        # HonchoClient, query_dialectic
│
├── memory/              # Memory system
│   ├── blocks.py        # PersonaBlock, HumanBlock
│   ├── manager.py       # MemoryManager
│   ├── strategies.py    # Rotation strategies
│   └── enricher.py      # MemoryEnricher for external updates
│
├── observability/       # Logging and tracing
│   ├── logging.py       # Structured logging
│   ├── metrics.py       # LLMMetrics
│   └── tracing.py       # Tracer context manager
│
├── pipelines/           # OpenWebUI integration
│   └── letta_pipe.py    # Pipe class
│
├── server/              # HTTP service
│   ├── main.py          # FastAPI app
│   ├── agents.py        # AgentManager
│   ├── background.py    # Background agent endpoints
│   ├── schemas.py       # Request/response models
│   ├── tracing.py       # Langfuse integration
│   └── strategy/        # Strategy agent subsystem
│
├── tools/               # Agent tools
│   ├── dialectic.py     # query_honcho tool
│   └── memory.py        # edit_memory_block tool
│
└── main.py              # CLI entry point

config/
└── courses/             # TOML course configurations
    └── college-essay.toml
```

## Design Decisions

### Why Letta?

Letta provides:
- **Persistent memory** - Core and archival memory that survives sessions
- **Structured memory blocks** - Type-safe memory with validation
- **Tool system** - Agents can call functions
- **Streaming** - Real-time response generation

### Why Separate HTTP Service?

- **Decoupling** - Pipeline doesn't directly depend on Letta SDK
- **Testability** - HTTP endpoints are easy to test
- **Flexibility** - Multiple clients can use the service
- **Observability** - Centralized tracing and logging

### Why Per-User Agents?

Each student gets their own agent with:
- Personal context (name, preferences, facts)
- Session history
- Progress tracking
- Isolated memory

### Why Strategy Agent?

A shared RAG agent for:
- Project documentation
- FAQ responses
- Developer queries
- Knowledge that doesn't belong to a user

## Related Pages

- [[HTTP-Service]] - Endpoint details
- [[Memory-System]] - Memory architecture
- [[Pipeline]] - OpenWebUI integration
- [[Background-Agents]] - Background agent system
- [[Agent-Tools]] - Agent tool implementations
- [[Honcho]] - Honcho integration and dialectic queries
- [[Letta-SDK]] - SDK patterns
