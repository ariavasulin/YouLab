# Letta Archival Memory

[[README|← Back to Overview]]

Complete reference for Letta's archival memory system (passages).

## Overview

Archival memory is a **semantically searchable vector database** for long-term storage. Unlike core memory (always visible), archival memory requires explicit search to retrieve.

| Feature | Core Memory | Archival Memory |
|---------|-------------|-----------------|
| Location | In-context | Vector database |
| Access | Always visible | Search required |
| Size | ~2000 chars/block | Unlimited |
| Agent Ops | Insert, Replace, Rethink | Insert, Search |

---

## Key Characteristics

- **Hybrid Search**: Combines semantic (vector) and keyword matching
- **RRF Scoring**: Reciprocal Rank Fusion ranks results
- **Tag Filtering**: Organize and filter by tags
- **Date Filtering**: Query by creation time
- **Persistent**: Survives server restarts

---

## SDK Operations

### Insert Passage

```python
client.agents.passages.insert(
    agent_id=agent.id,
    content="Important fact to remember",
    tags=["category", "important"]
)
```

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | str | Yes | Agent identifier |
| `content` | str | Yes | Text to store |
| `tags` | list[str] | No | Organization tags |
| `created_at` | datetime | No | Backdate the passage |

### Search Passages

```python
results = client.agents.passages.search(
    agent_id=agent.id,
    query="search query",
    tags=["category"],              # Optional filter
    page=0,                         # Pagination
    start_datetime="2025-01-01",    # Optional date filter
    end_datetime="2025-12-31"
)
```

**Response Fields**:

| Field | Description |
|-------|-------------|
| `content` | Stored text |
| `tags` | Associated tags |
| `timestamp` | Creation time |
| `rrf_score` | Combined relevance score |
| `vector_rank` | Semantic search rank |
| `fts_rank` | Full-text search rank |

### List All Passages

```python
passages = client.agents.passages.list(
    agent_id=agent.id,
    limit=100,
    ascending=True
)
```

### Get Specific Passage

```python
passage = client.agents.passages.get(
    agent_id=agent.id,
    passage_id=passage_id
)
```

### Delete Passage

```python
client.agents.passages.delete(
    agent_id=agent.id,
    passage_id=passage_id
)
```

> **Note**: Agents cannot delete passages. Only SDK/API calls can delete.

---

## Agent Tools

During conversations, agents use these tools:

### archival_memory_insert

```python
# Called by agent
archival_memory_insert(
    content="User prefers Python for data science",
    tags=["preferences", "programming"]
)
```

### archival_memory_search

```python
# Called by agent
results = archival_memory_search(
    query="user programming preferences",
    tags=["preferences"],
    page=0
)
```

### conversation_search

Search past messages:

```python
results = conversation_search(
    query="essay topics",
    page=0
)
```

### conversation_search_date

Time-bounded message search:

```python
results = conversation_search_date(
    start_date="2025-01-01",
    end_date="2025-01-31",
    page=0
)
```

---

## Search Behavior

### Hybrid Search

Combines two methods:

1. **Semantic Search**: Vector similarity using embeddings
   - Finds conceptually similar content
   - "artificial memories" matches "implanted memories"

2. **Full-Text Search**: Keyword matching
   - Exact word matching
   - "API" matches "API"

### Reciprocal Rank Fusion (RRF)

Results are ranked by combining both methods:

```
RRF_score = 1/(k + vector_rank) + 1/(k + fts_rank)
```

Higher scores = more relevant.

### Query Types That Work Well

```python
# Natural language (best)
search("How does the authentication system work?")

# Keywords
search("API rate limits")

# Concepts (semantic understanding)
search("artificial memories")  # Finds "implanted memories"

# Time-filtered
search("meeting notes", start_datetime="2025-09-29")
```

---

## Tag Organization

### Common Tag Patterns

```python
tags = [
    # User information
    "user_info", "preferences", "personal_history",

    # Content types
    "documentation", "technical", "reference",

    # Temporal
    "conversation", "milestone", "event",

    # Domain-specific
    "essay_topic", "feedback", "brainstorming"
]
```

### Using Tags Effectively

```python
# Insert with multiple tags
client.agents.passages.insert(
    agent_id=agent.id,
    content="User prefers Socratic questioning style",
    tags=["user_info", "preferences", "tutoring_style"]
)

# Search with tag filter
results = client.agents.passages.search(
    agent_id=agent.id,
    query="tutoring preferences",
    tags=["preferences"]  # Only search in this category
)
```

---

## Bulk Loading

### Pattern for Loading Documents

```python
def load_documents(client, agent_id, documents):
    """Load multiple documents into archival memory."""
    for doc in documents:
        client.agents.passages.insert(
            agent_id=agent_id,
            content=doc["content"],
            tags=doc.get("tags", [])
        )
    print(f"Loaded {len(documents)} documents")

# Usage
documents = [
    {"content": "Fact 1...", "tags": ["category"]},
    {"content": "Fact 2...", "tags": ["category"]},
]
load_documents(client, agent.id, documents)
```

### Chunking Large Documents

```python
def chunk_document(text, chunk_size=500, overlap=50):
    """Split document into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def load_large_document(client, agent_id, text, base_tags=None):
    """Load a large document by chunking."""
    chunks = chunk_document(text)
    for i, chunk in enumerate(chunks):
        tags = (base_tags or []) + [f"chunk_{i}"]
        client.agents.passages.insert(
            agent_id=agent_id,
            content=chunk,
            tags=tags
        )
    return len(chunks)
```

---

## YouLab Integration

### Memory Rotation

When core memory exceeds threshold, YouLab rotates to archival:

```python
def _rotate_human_to_archival(self):
    timestamp = datetime.now().isoformat()
    archival_entry = f"[ARCHIVED {timestamp}]\n{memory_str}"

    self.client.insert_archival_memory(
        agent_id=self.agent_id,
        memory=archival_entry,
    )
```

### Task Archival

When tasks complete:

```python
def _archive_task_context(self, human):
    task_summary = f"""[TASK COMPLETED {timestamp}]
Task: {human.current_task}
Context:
- {context_note_1}
- {context_note_2}
"""
    self.client.insert_archival_memory(
        agent_id=self.agent_id,
        memory=task_summary,
    )
```

### Archival Search

```python
results = manager.search_archival("essay topics", limit=5)
for result in results:
    print(result)
```

---

## Configuration

### Embedding Models

| Environment | Default | Changeable |
|-------------|---------|------------|
| Letta Cloud | `text-embedding-3-small` | No |
| Self-hosted | `text-embedding-3-small` | Yes (at agent creation) |

```python
# Set at agent creation
agent = client.agents.create(
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",  # Or other model
    memory_blocks=[...]
)
```

> **Warning**: Changing embedding model requires re-embedding all data.

### Vector Database Backends

| Environment | Backend | Notes |
|-------------|---------|-------|
| Letta Cloud | TurboPuffer | Very fast, scales to 100k+ |
| Self-hosted | pgvector (PostgreSQL) | Good with proper indexing |
| Letta Desktop | SQLite + extensions | Personal use |

---

## Best Practices

### 1. Keep Passages Atomic

```python
# Good - single fact
"User prefers Socratic questioning style"

# Bad - multiple facts
"User prefers Socratic questioning, is studying CS, and likes examples"
```

### 2. Use Descriptive Tags

```python
# Good - specific tags
tags=["user_preference", "communication_style", "tutoring"]

# Bad - vague tags
tags=["info", "user"]
```

### 3. Memory Blocks vs Archival

| Use Case | Best Location |
|----------|---------------|
| Current preferences | Memory Block |
| Preference history | Archival |
| Active task | Memory Block |
| Completed tasks | Archival |
| Agent persona | Memory Block (read-only) |
| Reference docs | Archival |

### 4. Search Before Insert

Avoid duplicates:

```python
# Check if already exists
results = client.agents.passages.search(
    agent_id=agent.id,
    query="specific fact to check"
)

if not results or results[0].rrf_score < 0.9:
    client.agents.passages.insert(...)
```

---

## Limitations

1. **Agents Cannot Delete**: Only insert and search via tools
2. **Embedding Lock-in**: Changing model requires re-embedding
3. **No Updates**: Must delete and re-insert to modify
4. **Pagination**: Large result sets are paginated

---

## External Resources

- [Archival Memory Guide](https://docs.letta.com/guides/agents/archival-memory/)
- [Searching & Querying](https://docs.letta.com/guides/agents/archival-search/)
- [Best Practices](https://docs.letta.com/guides/agents/archival-best-practices/)
- [Memory Overview](https://docs.letta.com/guides/agents/memory/)

---

## Related Pages

- [[Letta-Concepts]] - Core architecture
- [[Memory-System]] - YouLab's memory implementation
- [[Letta-SDK]] - SDK patterns
