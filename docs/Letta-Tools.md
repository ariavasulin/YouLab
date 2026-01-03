# Letta Tool System

[[README|← Back to Overview]]

Complete reference for Letta's tool/function system.

## Overview

Letta agents perform actions through tool calls. The LLM decides which tools to call based on the conversation context.

```
User Input → LLM Reasoning → Tool Selection → Execution → Result → Response
```

---

## Tool Categories

### Built-in Tools

**Memory Tools** (always available):

| Tool | Purpose |
|------|---------|
| `memory_insert` | Add text at specific line in memory block |
| `memory_replace` | Find and replace text in memory block |
| `memory_rethink` | Completely rewrite a memory block |
| `memory_finish_edits` | Signal completion of memory editing |
| `archival_memory_insert` | Store content in archival memory |
| `archival_memory_search` | Search archival memory |
| `conversation_search` | Search conversation history |
| `conversation_search_date` | Time-filtered conversation search |

**Utility Tools** (pre-built, optional):

| Tool | Purpose |
|------|---------|
| `web_search` | Semantic web search via Exa |
| `run_code` | Execute code in sandbox |
| `fetch_webpage` | Get LLM-friendly webpage content |

### Custom Tools

Tools you define for your specific use case.

### MCP Tools

Tools from external Model Context Protocol servers.

---

## Creating Custom Tools

### Method 1: From Function

```python
def roll_dice(num_dice: int, num_sides: int) -> str:
    """
    Roll dice and return results.

    Args:
        num_dice: Number of dice to roll
        num_sides: Number of sides per die

    Returns:
        String with roll results
    """
    import random
    results = [random.randint(1, num_sides) for _ in range(num_dice)]
    return f"Rolled: {results}, Total: {sum(results)}"

# Create tool from function
tool = client.tools.upsert_from_function(func=roll_dice)
```

**Requirements**:
- Google-style docstring (description, Args, Returns)
- Type hints on parameters
- Return type annotation

### Method 2: With Pydantic Schema

```python
from pydantic import BaseModel, Field

class DiceArgs(BaseModel):
    num_dice: int = Field(description="Number of dice to roll")
    num_sides: int = Field(default=6, description="Sides per die")

def roll_dice(num_dice: int, num_sides: int = 6) -> str:
    """Roll dice and return results."""
    import random
    results = [random.randint(1, num_sides) for _ in range(num_dice)]
    return str(results)

tool = client.tools.upsert_from_function(
    func=roll_dice,
    args_schema=DiceArgs
)
```

### Method 3: From Source Code

```python
source = '''
def my_tool(arg: str) -> str:
    """
    Tool description.

    Args:
        arg: Input argument

    Returns:
        Result string
    """
    return f"Processed: {arg}"
'''

tool = client.tools.create(source_code=source)
```

### Method 4: BaseTool Class

```python
from letta_client.client import BaseTool
from pydantic import BaseModel
from typing import Type

class TaskArgs(BaseModel):
    title: str
    priority: int

class CreateTaskTool(BaseTool):
    name: str = "create_task"
    args_schema: Type[BaseModel] = TaskArgs
    description: str = "Create a new task"
    tags: list[str] = ["productivity"]

    def run(self, title: str, priority: int) -> str:
        return f"Created task: {title} (priority {priority})"

tool = client.tools.add(tool=CreateTaskTool())
```

---

## Attaching Tools to Agents

### At Creation

```python
agent = client.agents.create(
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-ada-002",
    memory_blocks=[...],
    tools=["roll_dice", "create_task"],    # By name
    tool_ids=[tool1.id, tool2.id],          # By ID
    include_base_tools=True,                # Memory tools
)
```

### After Creation

```python
# Attach
client.agents.tools.attach(agent_id=agent.id, tool_id=tool.id)

# Detach
client.agents.tools.detach(agent_id=agent.id, tool_id=tool.id)

# List
tools = client.agents.tools.list(agent_id=agent.id)
```

---

## Tool Execution

### How Tools Run

1. LLM outputs tool call with name and arguments
2. Letta validates against tool schema
3. Tool executes in configured environment
4. Result returned to agent
5. Agent continues reasoning

### Execution Environments

| Environment | Description | Use Case |
|-------------|-------------|----------|
| Sandbox (E2B) | Isolated cloud container | Untrusted code |
| Local Sandbox | Docker container | Development |
| Client-Side | Your application | Full permissions |
| Built-in | Letta server | Memory tools |
| MCP | External server | Third-party tools |

### Local Execution Requirements

When running tools locally:

```python
def my_tool(arg: str) -> str:
    """Tool description."""
    # Imports MUST be inside the function
    import requests

    response = requests.get(f"https://api.example.com/{arg}")
    return response.text
```

> **Important**: All imports must be inside the function body.

---

## Tool Rules

Control tool execution flow:

### TerminalToolRule

Agent ends after calling this tool:

```python
from letta_client import TerminalToolRule

agent = client.agents.create(
    ...,
    tool_rules=[
        TerminalToolRule(tool_name="submit_answer")
    ]
)
```

### InitToolRule

Tool must be called first:

```python
from letta_client import InitToolRule

agent = client.agents.create(
    ...,
    tool_rules=[
        InitToolRule(tool_name="load_context")
    ]
)
```

### ChildToolRule / ParentToolRule

Define execution order:

```python
from letta_client import ChildToolRule

# search must be called before summarize
agent = client.agents.create(
    ...,
    tool_rules=[
        ChildToolRule(
            tool_name="search",
            children=["summarize"]
        )
    ]
)
```

### MaxCountPerStepToolRule

Limit calls per step:

```python
from letta_client import MaxCountPerStepToolRule

agent = client.agents.create(
    ...,
    tool_rules=[
        MaxCountPerStepToolRule(
            tool_name="web_search",
            max_count=3
        )
    ]
)
```

---

## Tool Variables

Pass environment variables to tools:

```python
agent = client.agents.create(
    ...,
    tool_exec_environment_variables={
        "API_KEY": "secret-key",
        "DATABASE_URL": "postgres://..."
    }
)
```

Access in tool:

```python
import os

def my_tool(query: str) -> str:
    """Query external API."""
    api_key = os.environ["API_KEY"]
    # Use api_key...
```

---

## Multi-Agent Tools

Built-in tools for agent-to-agent communication:

| Tool | Behavior |
|------|----------|
| `send_message_to_agent_async` | Fire and forget |
| `send_message_to_agent_and_wait_for_reply` | Synchronous call |
| `send_message_to_agents_matching_all_tags` | Broadcast to tagged agents |

Enable with:

```python
agent = client.agents.create(
    ...,
    include_multi_agent_tools=True
)
```

---

## Tool Response Format

Tools should return strings:

```python
# Good - string return
def my_tool(arg: str) -> str:
    result = {"status": "ok", "data": [...]}
    return json.dumps(result)

# Also good - simple string
def my_tool(arg: str) -> str:
    return "Operation completed successfully"
```

### Error Handling

```python
def my_tool(arg: str) -> str:
    """Tool with error handling."""
    try:
        result = process(arg)
        return f"Success: {result}"
    except ValueError as e:
        return f"Error: Invalid input - {e}"
    except Exception as e:
        return f"Error: {e}"
```

---

## Tool Schema Generation

Letta automatically generates OpenAI-compatible JSON schemas:

```python
# From this function
def greet(name: str, formal: bool = False) -> str:
    """
    Greet a person.

    Args:
        name: Person's name
        formal: Use formal greeting

    Returns:
        Greeting message
    """
    ...

# Letta generates
{
    "name": "greet",
    "description": "Greet a person.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Person's name"
            },
            "formal": {
                "type": "boolean",
                "description": "Use formal greeting",
                "default": false
            }
        },
        "required": ["name"]
    }
}
```

---

## Human-in-the-Loop

Require approval before execution:

```python
# Mark tool as requiring approval
client.agents.tools.update_approval(
    agent_id=agent.id,
    tool_name="delete_file",
    require_approval=True
)
```

During execution:
1. Agent calls tool
2. `approval_request_message` sent
3. Wait for `approval_response_message`
4. If approved, execute; otherwise skip

---

## Debugging Tools

### Run Tool Directly

```python
result = client.agents.tools.run(
    agent_id=agent.id,
    tool_name="my_tool",
    args={"arg1": "value1"}
)
print(result)
```

### View Tool Schema

```python
tool = client.tools.get(tool_id)
print(tool.json_schema)
```

---

## External Resources

- [Connecting Agents to Tools](https://docs.letta.com/guides/agents/tools)
- [Custom Tools Guide](https://docs.letta.com/guides/agents/custom-tools)
- [Tool Rules](https://docs.letta.com/guides/agents/tool-rules)
- [Base Tools](https://docs.letta.com/guides/agents/base-tools/)
- [Local Execution](https://docs.letta.com/guides/agents/tool-execution-local/)
- [Multi-Agent Tools](https://docs.letta.com/guides/agents/multi-agent-custom-tools)

---

## Related Pages

- [[Letta-Concepts]] - Core architecture
- [[Letta-SDK]] - SDK patterns
- [[Letta-REST-API]] - API endpoints
