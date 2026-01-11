# Schemas

[[README|← Back to Overview]]

Pydantic models for API requests and responses.

## Location

- Main schemas: `src/youlab_server/server/schemas.py`
- Strategy schemas: `src/youlab_server/server/strategy/schemas.py`

---

## Agent Schemas

### CreateAgentRequest

```python
class CreateAgentRequest(BaseModel):
    user_id: str
    agent_type: str = "tutor"
    user_name: str | None = None
```

### AgentResponse

```python
class AgentResponse(BaseModel):
    agent_id: str
    user_id: str
    agent_type: str
    agent_name: str
    created_at: datetime | int | None = None
```

### AgentListResponse

```python
class AgentListResponse(BaseModel):
    agents: list[AgentResponse]
```

---

## Chat Schemas

### ChatRequest

```python
class ChatRequest(BaseModel):
    agent_id: str
    message: str
    chat_id: str | None = None
    chat_title: str | None = None
```

### ChatResponse

```python
class ChatResponse(BaseModel):
    response: str
    agent_id: str
```

### StreamChatRequest

```python
class StreamChatRequest(BaseModel):
    agent_id: str
    message: str
    chat_id: str | None = None
    chat_title: str | None = None
    enable_thinking: bool = True
```

---

## Health Schemas

### HealthResponse

```python
class HealthResponse(BaseModel):
    status: str
    letta_connected: bool
    honcho_connected: bool = False
    version: str = "0.1.0"
```

---

## Strategy Schemas

### UploadDocumentRequest

```python
class UploadDocumentRequest(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
```

### UploadDocumentResponse

```python
class UploadDocumentResponse(BaseModel):
    success: bool
```

### AskRequest

```python
class AskRequest(BaseModel):
    question: str
```

### AskResponse

```python
class AskResponse(BaseModel):
    response: str
```

### SearchDocumentsResponse

```python
class SearchDocumentsResponse(BaseModel):
    documents: list[str]
```

### HealthResponse (Strategy)

```python
class HealthResponse(BaseModel):
    status: str
    agent_exists: bool
```

---

## Memory Schemas

### PersonaBlock

```python
class PersonaBlock(BaseModel):
    name: str = "Assistant"
    role: str
    capabilities: list[str] = Field(default_factory=list)
    tone: str = "professional"
    verbosity: str = "concise"
    constraints: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
```

### HumanBlock

```python
class HumanBlock(BaseModel):
    name: str | None = None
    role: str | None = None
    current_task: str | None = None
    session_state: SessionState = SessionState.IDLE
    preferences: list[str] = Field(default_factory=list)
    context_notes: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
```

### SessionState

```python
class SessionState(str, Enum):
    IDLE = "idle"
    ACTIVE_TASK = "active_task"
    WAITING_INPUT = "waiting_input"
    THINKING = "thinking"
    ERROR_RECOVERY = "error_recovery"
```

---

## Template Schemas

### AgentTemplate

```python
class AgentTemplate(BaseModel):
    type_id: str
    display_name: str
    description: str = ""
    persona: PersonaBlock
    human: HumanBlock = Field(default_factory=HumanBlock)
```

---

## Metrics Schemas

### ContextMetrics

```python
@dataclass
class ContextMetrics:
    persona_chars: int
    human_chars: int
    persona_max: int
    human_max: int

    @property
    def persona_usage(self) -> float
    @property
    def human_usage(self) -> float
    @property
    def total_usage(self) -> float
```

### LLMMetrics

```python
@dataclass
class LLMMetrics:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0
    model: str = ""
```

---

## Related Pages

- [[API]] - Endpoint reference
- [[Memory-System]] - Memory block details
- [[Agent-System]] - Template details
