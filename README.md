# LettaStarter

Context-engineered Letta agents with comprehensive observability, exposed via Open WebUI.

## Features

- **Schema-driven Memory Blocks** - Pydantic-validated `PersonaBlock` and `HumanBlock` with efficient serialization
- **Memory Lifecycle Management** - Automatic context rotation, archival, and optimization strategies
- **Structured Logging** - JSON logging with structlog for production observability
- **LLM Tracing** - Built-in metrics collection with optional Langfuse integration
- **Open WebUI Pipeline** - Ready-to-deploy pipeline for Open WebUI integration
- **Multi-Agent Ready** - Agent registry and factory patterns for building multi-agent systems

## Quick Start

### Prerequisites

1. **UV Package Manager** (recommended):
   ```bash
   # Install UV
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Letta Server** running locally:
   ```bash
   # Install and run Letta server
   pip install letta
   letta server
   ```

### Installation

```bash
# Clone the repository
cd LettaStarter

# Install with UV
uv sync

# Or with pip
pip install -e .

# Install with dev dependencies
uv sync --all-extras
# Or: pip install -e ".[dev,observability]"
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit with your settings
# Required: OPENAI_API_KEY (or other LLM provider key)
```

### Usage

#### Interactive CLI

```bash
# Run interactive session
uv run letta-starter

# Or with specific agent
uv run letta-starter --agent my-agent

# With debug logging
uv run letta-starter --log-level DEBUG
```

#### Python API

```python
from letta import create_client
from letta_starter import (
    configure_logging,
    get_tracer,
    create_default_agent,
    PersonaBlock,
    HumanBlock,
)

# Initialize
configure_logging(level="INFO", json_output=False)
tracer = get_tracer()
client = create_client()

# Create agent
agent = create_default_agent(client, name="my-agent", tracer=tracer)

# Start session
tracer.start_session("session-001")

# Chat
response = agent.send_message("Hello! What can you help me with?")
print(response)

# Update context
agent.update_context(task="Building a multi-agent system")
agent.learn(preference="Prefers code examples")

# Check memory
print(agent.get_memory_summary())

# End session
tracer.end_session()
```

#### Custom Agent

```python
from letta_starter import BaseAgent, PersonaBlock, HumanBlock

# Define custom persona
persona = PersonaBlock(
    name="DataAnalyst",
    role="Data analysis specialist",
    capabilities=["Python analysis", "SQL queries", "Visualization"],
    expertise=["pandas", "matplotlib", "statistics"],
    tone="professional",
    verbosity="detailed",
)

# Create agent
agent = BaseAgent(
    name="data-analyst",
    persona=persona,
    human=HumanBlock(name="Alice", role="Product Manager"),
    client=client,
)
```

## Project Structure

```
src/letta_starter/
├── agents/           # Agent definitions
│   ├── base.py       # BaseAgent with observability
│   ├── default.py    # Pre-configured agents
│   └── templates.py  # AgentTemplate for creating tutor agents
├── memory/           # Memory management (core focus)
│   ├── blocks.py     # PersonaBlock, HumanBlock schemas
│   ├── manager.py    # Memory lifecycle manager
│   └── strategies.py # Context rotation strategies
├── observability/    # Logging & tracing
│   ├── logging.py    # Structlog configuration
│   ├── metrics.py    # Usage metrics collection
│   └── tracing.py    # LLM call tracing
├── pipelines/        # Open WebUI integration
│   └── letta_pipe.py # Pipeline class
├── server/           # HTTP service
│   ├── main.py       # FastAPI app
│   ├── agents.py     # AgentManager for per-user agents
│   ├── schemas.py    # Request/response schemas
│   └── tracing.py    # Langfuse integration
├── config/           # Configuration
│   └── settings.py   # Pydantic settings
└── main.py           # CLI entry point
```

## Memory Management

The core of this project is sophisticated memory block management:

### Memory Block Schemas

```python
# Persona defines WHO the agent is
persona = PersonaBlock(
    name="Expert",
    role="Domain expert",
    capabilities=["Task 1", "Task 2"],
    constraints=["Never do X"],
)

# Serializes to compact format:
# [IDENTITY] Expert | Domain expert
# [CAPABILITIES] Task 1, Task 2
# [CONSTRAINTS] Never do X
```

### Context Rotation Strategies

```python
from letta_starter.memory.strategies import (
    AggressiveRotation,    # Rotate at 70% capacity
    PreservativeRotation,  # Rotate at 90% capacity
    AdaptiveRotation,      # Learn optimal threshold
)

# Memory manager handles rotation automatically
manager = MemoryManager(
    client=client,
    agent_id=agent_id,
    strategy=AdaptiveRotation(),
)
```

## Open WebUI Integration

### Option 1: Copy Pipeline

Copy `src/letta_starter/pipelines/letta_pipe.py` to Open WebUI's pipelines directory.

### Option 2: Upload via Admin

1. Go to Open WebUI Admin > Pipelines
2. Upload `letta_pipe.py`
3. Configure the Valves:
   - `LETTA_BASE_URL`: Your Letta server URL
   - `LETTA_AGENT_NAME`: Agent name to use

## Observability

### Logging

```python
from letta_starter import configure_logging, get_logger

# Production (JSON logs)
configure_logging(level="INFO", json_output=True)

# Development (pretty console)
configure_logging(level="DEBUG", json_output=False)

logger = get_logger("my-module")
logger.info("event_name", key="value", number=42)
```

### Metrics

```python
from letta_starter.observability.metrics import get_metrics_collector

collector = get_metrics_collector()
collector.start_session("session-001")

# Metrics are automatically collected during agent calls

session = collector.end_session()
print(session.to_dict())
# {
#   "total_calls": 5,
#   "total_tokens": 1234,
#   "total_cost_usd": 0.0234,
#   "avg_latency_ms": 450.2,
# }
```

### Langfuse Integration (Optional)

```bash
# Enable in .env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src/

# Type check
uv run basedpyright src/

# Run HTTP server
uv run letta-server
```

## License

MIT
