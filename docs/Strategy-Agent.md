# Strategy Agent

[[README|← Back to Overview]]

The Strategy Agent is a singleton RAG-enabled agent for project-wide knowledge queries.

## Overview

Unlike per-user tutor agents, the Strategy Agent:
- Is **shared** across all users
- Uses **archival memory** for document storage
- **Searches before answering** (RAG pattern)
- Serves **developer/admin** use cases

```
┌─────────────────────────────────────────────────────────────┐
│                    StrategyManager                           │
│                                                              │
│  Agent Name: "YouLab-Support"                               │
│  Type: Singleton (one per system)                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                Archival Memory                       │   │
│  │                                                      │   │
│  │  [TAGS: architecture, design]                       │   │
│  │  # Architecture                                      │   │
│  │  YouLab uses a layered architecture...              │   │
│  │                                                      │   │
│  │  [TAGS: api, reference]                             │   │
│  │  # API Reference                                     │   │
│  │  POST /agents - Create agent...                     │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## StrategyManager

**Location**: `src/letta_starter/server/strategy/manager.py`

### Initialization

```python
manager = StrategyManager(letta_base_url="http://localhost:8283")

# Ensure agent exists
agent_id = manager.ensure_agent()
```

### Persona

The strategy agent has a special persona that instructs it to search archival memory:

```python
STRATEGY_PERSONA = """You are a YouLab project strategist with comprehensive knowledge stored in your archival memory.

CRITICAL: Before answering ANY question about YouLab:
1. Use archival_memory_search to find relevant documentation
2. Cite the sources you found in your response
3. If no relevant documents found, say so explicitly

Your archival memory contains:
- Architecture documentation
- Roadmap and phase plans
- Design decisions and rationale
- Technical specifications

Be concise, accurate, and always reference your archival knowledge."""
```

### Methods

#### ensure_agent()

Gets or creates the singleton agent:

```python
agent_id = manager.ensure_agent()
```

1. Check cache for existing ID
2. Search Letta for "YouLab-Support" agent
3. Create if not found
4. Cache and return ID

#### upload_document()

Add content to archival memory:

```python
manager.upload_document(
    content="# Architecture\n\nYouLab uses a layered architecture...",
    tags=["architecture", "design"],
)
```

Tags are prepended for searchability:
```
[TAGS: architecture, design]
# Architecture
YouLab uses a layered architecture...
```

#### ask()

Query with RAG:

```python
response = manager.ask("What is the YouLab architecture?")
# Agent searches archival, then responds with citations
```

#### search_documents()

Direct archival search:

```python
results = manager.search_documents(
    query="architecture",
    limit=5,
)
# Returns list of matching document texts
```

#### check_agent_exists()

Check without creating:

```python
exists = manager.check_agent_exists()
```

---

## HTTP Endpoints

**Location**: `src/letta_starter/server/strategy/router.py`

### POST /strategy/documents

Upload document to archival memory.

**Request**:
```json
{
  "content": "# My Document\n\nContent here...",
  "tags": ["category", "topic"]
}
```

**Response** (201):
```json
{
  "success": true
}
```

### POST /strategy/ask

Query the strategy agent.

**Request**:
```json
{
  "question": "What is the YouLab architecture?"
}
```

**Response**:
```json
{
  "response": "Based on the architecture documentation, YouLab uses a layered architecture consisting of..."
}
```

### GET /strategy/documents

Search archival memory directly.

**Request**:
```
GET /strategy/documents?query=architecture&limit=5
```

**Response**:
```json
{
  "documents": [
    "[TAGS: architecture, design]\n# Architecture\n...",
    "[TAGS: overview]\n# System Overview\n..."
  ]
}
```

### GET /strategy/health

Check strategy agent status.

**Response**:
```json
{
  "status": "ready",
  "agent_exists": true
}
```

---

## Comparison: Strategy vs User Agents

| Aspect | Strategy Agent | User Agents |
|--------|---------------|-------------|
| **Count** | 1 per system | 1 per user |
| **Name** | `YouLab-Support` | `youlab_{user_id}_{type}` |
| **Purpose** | Project knowledge | Tutoring |
| **Memory** | Archival (RAG) | Core + Archival |
| **Manager** | StrategyManager | AgentManager |
| **Endpoints** | `/strategy/*` | `/agents/*`, `/chat/*` |

---

## Use Cases

### Documentation Repository

Upload project documentation:

```bash
curl -X POST http://localhost:8100/strategy/documents \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# API Reference\n\n## Endpoints\n...",
    "tags": ["api", "reference"]
  }'
```

### Developer Queries

Ask about the project:

```bash
curl -X POST http://localhost:8100/strategy/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How does streaming work in YouLab?"}'
```

### Knowledge Search

Find specific documents:

```bash
curl "http://localhost:8100/strategy/documents?query=streaming&limit=3"
```

---

## Initialization

The strategy manager is initialized during HTTP service startup:

```python
# src/letta_starter/server/main.py

@asynccontextmanager
async def lifespan(app):
    # Initialize strategy manager
    init_strategy_manager(letta_base_url=settings.letta_base_url)
    yield
```

The agent is created lazily on first use (not at startup).

---

## Implementation Details

### Singleton Pattern

```python
# Module-level state
_strategy_manager: StrategyManager | None = None

def init_strategy_manager(letta_base_url: str):
    global _strategy_manager
    _strategy_manager = StrategyManager(letta_base_url)

def get_strategy_manager() -> StrategyManager:
    if _strategy_manager is None:
        raise RuntimeError("Strategy manager not initialized")
    return _strategy_manager
```

### Lazy Client

```python
class StrategyManager:
    @property
    def client(self) -> Letta:
        if self._client is None:
            self._client = Letta(base_url=self.letta_base_url)
        return self._client
```

### Agent Caching

```python
def ensure_agent(self) -> str:
    # Return cached if available
    if self._agent_id is not None:
        return self._agent_id

    # Search for existing
    existing = self._find_existing_agent()
    if existing:
        self._agent_id = existing
        return existing

    # Create new
    agent = self.client.create_agent(...)
    self._agent_id = agent.id
    return agent.id
```

---

## Related Pages

- [[HTTP-Service]] - All service endpoints
- [[Architecture]] - System overview
- [[Letta-SDK]] - Letta archival memory API
