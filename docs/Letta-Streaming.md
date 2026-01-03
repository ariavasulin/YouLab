# Letta Streaming & Messages

[[README|← Back to Overview]]

Complete reference for Letta message handling and streaming.

## Overview

Letta supports two messaging modes:

| Mode | Method | Use Case |
|------|--------|----------|
| Synchronous | `messages.create()` | Simple requests, scripts |
| Streaming | `messages.stream()` | Real-time UI, chat apps |

---

## Synchronous Messages

### SDK Pattern

```python
response = client.agents.messages.create(
    agent_id=agent.id,
    messages=[{"role": "user", "content": "Hello!"}]
)

# Or shorthand
response = client.agents.messages.create(
    agent_id=agent.id,
    input="Hello!"
)

# Process response
for msg in response.messages:
    if msg.message_type == "assistant_message":
        print(msg.content)
```

### Response Structure

```python
response.messages    # List of message objects
response.usage       # Token statistics
response.stop_reason # "end_turn", "max_steps", "error"
```

---

## Streaming Messages

### SDK Pattern

```python
with client.agents.messages.stream(
    agent_id=agent.id,
    input="Hello!",
    stream_tokens=False,   # Step-level streaming
    include_pings=True,    # Keepalive pings
) as stream:
    for chunk in stream:
        if chunk.message_type == "assistant_message":
            print(chunk.content)
```

### Streaming Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_id` | str | Required | Agent identifier |
| `input` | str | - | User message (shorthand) |
| `messages` | list | - | Full message array |
| `stream_tokens` | bool | `False` | Token-level streaming |
| `include_pings` | bool | `False` | Include keepalive pings |
| `enable_thinking` | str | - | `"true"` or `"false"` |

### Streaming Modes

**Step Streaming** (default):
- Complete messages after each agent step
- Simpler to process

**Token Streaming** (`stream_tokens=True`):
- Character-by-character output
- ChatGPT-like real-time text

---

## Message Types

### Complete Reference

| Type | When Sent | Key Fields |
|------|-----------|------------|
| `user_message` | User input echo | `content`, `sender_id` |
| `system_message` | System context | `content` |
| `reasoning_message` | Agent thinking | `reasoning`, `source` |
| `hidden_reasoning_message` | Redacted thinking | `state` |
| `assistant_message` | Agent response | `content` |
| `tool_call_message` | Tool request | `tool_call.name`, `tool_call.arguments` |
| `tool_return_message` | Tool result | `tool_return`, `status`, `stdout`, `stderr` |
| `stop_reason` | Stream complete | `stop_reason` |
| `usage_statistics` | Token counts | `prompt_tokens`, `completion_tokens` |
| `ping` | Keepalive | - |
| `error_message` | Error occurred | `message` |

### Message Processing Example

```python
for chunk in stream:
    msg_type = chunk.message_type

    if msg_type == "reasoning_message":
        print(f"Thinking: {chunk.reasoning}")

    elif msg_type == "tool_call_message":
        tool = chunk.tool_call
        print(f"Calling: {tool.name}({tool.arguments})")

    elif msg_type == "tool_return_message":
        print(f"Result: {chunk.tool_return}")
        if chunk.status != "success":
            print(f"Error: {chunk.stderr}")

    elif msg_type == "assistant_message":
        print(f"Response: {chunk.content}")

    elif msg_type == "stop_reason":
        print(f"Done: {chunk.stop_reason}")

    elif msg_type == "usage_statistics":
        print(f"Tokens: {chunk.total_tokens}")
```

---

## Server-Sent Events (SSE) Format

Streaming uses SSE format over HTTP:

```
data: {"id":"msg-123","message_type":"reasoning_message","reasoning":"..."}

data: {"id":"msg-456","message_type":"assistant_message","content":"Hello!"}

data: {"message_type":"stop_reason","stop_reason":"end_turn"}

data: {"message_type":"usage_statistics","prompt_tokens":150,"completion_tokens":20}
```

### SSE Event Structure

```
data: {JSON}\n\n
```

Each event is:
- Prefixed with `data: `
- Contains JSON payload
- Terminated with double newline

### Keepalive Pings

When `include_pings=True`:

```
: keepalive

```

(SSE comment format - colon prefix, no `data:`)

---

## YouLab SSE Conversion

YouLab converts Letta chunks to a simplified SSE format:

### Chunk Conversion

```python
def _chunk_to_sse_event(chunk) -> str:
    msg_type = chunk.message_type

    if msg_type == "reasoning_message":
        return {"type": "status", "content": "Thinking...", "reasoning": chunk.reasoning}

    elif msg_type == "tool_call_message":
        return {"type": "status", "content": f"Using {chunk.tool_call.name}..."}

    elif msg_type == "assistant_message":
        return {"type": "message", "content": strip_metadata(chunk.content)}

    elif msg_type == "stop_reason":
        return {"type": "done"}

    elif msg_type == "ping":
        return ": keepalive\n\n"

    elif msg_type == "error_message":
        return {"type": "error", "message": chunk.message}
```

### YouLab Event Types

| YouLab Type | Letta Source | Purpose |
|-------------|--------------|---------|
| `status` | reasoning, tool_call | Progress updates |
| `message` | assistant_message | Actual response |
| `done` | stop_reason | Stream complete |
| `error` | error_message | Error occurred |

### Ignored Letta Types

These types are not forwarded to clients:

- `tool_return_message` - Internal tool results
- `usage_statistics` - Token metrics
- `hidden_reasoning_message` - Redacted thinking
- `system_message` - System context
- `user_message` - Input echo

---

## Metadata Stripping

Letta may append JSON metadata to messages:

```
Hello! How can I help?{"follow_ups": ["Tell me more", "Change topic"]}{"title": "Greeting"}
```

YouLab strips these:

```python
def _strip_letta_metadata(content: str) -> str:
    while content:
        last_brace = content.rfind("{")
        if last_brace == -1:
            break
        try:
            parsed = json.loads(content[last_brace:])
            if any(k in parsed for k in ("follow_ups", "title", "tags")):
                content = content[:last_brace].rstrip()
            else:
                break
        except json.JSONDecodeError:
            break
    return content
```

---

## Response Extraction

### From Sync Response

```python
def extract_response(response) -> str:
    texts = []
    for msg in response.messages:
        if msg.message_type == "assistant_message":
            texts.append(msg.content)
        elif hasattr(msg, "text") and msg.text:
            texts.append(msg.text)
    return "\n".join(texts)
```

### From Streaming

```python
def collect_stream(stream) -> str:
    texts = []
    for chunk in stream:
        if chunk.message_type == "assistant_message":
            texts.append(chunk.content)
    return "".join(texts)
```

---

## Typical Message Flows

### Simple Response

```
1. reasoning_message    (agent thinking)
2. assistant_message    (response)
3. stop_reason          (end_turn)
4. usage_statistics     (tokens)
```

### With Tool Use

```
1. reasoning_message     (deciding to use tool)
2. tool_call_message     (calling tool)
3. tool_return_message   (tool result)
4. reasoning_message     (processing result)
5. assistant_message     (response)
6. stop_reason           (end_turn)
7. usage_statistics      (tokens)
```

### Multi-Step Reasoning

```
1. reasoning_message     (step 1)
2. tool_call_message     (memory search)
3. tool_return_message   (search results)
4. reasoning_message     (step 2)
5. tool_call_message     (web search)
6. tool_return_message   (web results)
7. reasoning_message     (synthesizing)
8. assistant_message     (final response)
9. stop_reason           (end_turn)
```

---

## HTTP Headers for Streaming

When returning streaming responses:

```python
from fastapi.responses import StreamingResponse

return StreamingResponse(
    stream_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
    }
)
```

---

## Error Handling

### Stream Errors

```python
try:
    with client.agents.messages.stream(...) as stream:
        for chunk in stream:
            process(chunk)
except Exception as e:
    yield f'data: {{"type":"error","message":"{str(e)}"}}\n\n'
```

### Timeout Handling

```python
from httpx import ReadTimeout

try:
    with client.agents.messages.stream(...) as stream:
        for chunk in stream:
            yield process(chunk)
except ReadTimeout:
    yield 'data: {"type":"error","message":"Request timed out"}\n\n'
```

---

## External Resources

- [Streaming Guide](https://docs.letta.com/guides/agents/streaming/)
- [Message Types](https://docs.letta.com/guides/agents/message-types)
- [Messages API](https://docs.letta.com/api-reference/agents/messages/create)

---

## Related Pages

- [[Letta-Concepts]] - Core architecture
- [[Letta-REST-API]] - API endpoints
- [[HTTP-Service]] - YouLab streaming implementation
