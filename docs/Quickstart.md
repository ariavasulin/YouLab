# Quick Start

[[README|← Back to Overview]]

Get YouLab running locally in 5 minutes.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for Letta server)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/youlab/youlab.git
cd youlab

# Install dependencies
make setup
```

This installs all dependencies and configures pre-commit hooks.

## Step 2: Start Letta Server

Letta server runs in Docker:

```bash
# Pull and run Letta
docker run -d \
  --name letta-server \
  -p 8283:8283 \
  -v letta-data:/root/.letta \
  lettaai/letta:latest
```

Verify it's running:

```bash
curl http://localhost:8283/v1/health
# Should return: {"status": "ok"}
```

## Step 3: Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your API keys
vim .env
```

**Required settings**:

```bash
# Letta connection
LETTA_BASE_URL=http://localhost:8283

# LLM provider (OpenAI or Anthropic)
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

## Step 4: Start HTTP Service

```bash
# Start the YouLab service
uv run letta-server
```

The service starts on `http://localhost:8100`.

## Step 5: Test the API

### Create an Agent

```bash
curl -X POST http://localhost:8100/agents \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user", "agent_type": "tutor"}'
```

Response:
```json
{
  "agent_id": "agent-abc123",
  "user_id": "test-user",
  "agent_type": "tutor",
  "agent_name": "youlab_test-user_tutor"
}
```

### Send a Message

```bash
curl -X POST http://localhost:8100/chat \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-abc123",
    "message": "Help me brainstorm essay topics about my identity"
  }'
```

### Stream a Response

```bash
curl -N -X POST http://localhost:8100/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-abc123",
    "message": "What makes a compelling personal narrative?"
  }'
```

## Step 6: Connect OpenWebUI (Optional)

If using OpenWebUI as the frontend:

1. Start OpenWebUI (see [[Pipeline]] for details)
2. Add the Pipe function from `src/letta_starter/pipelines/letta_pipe.py`
3. Configure the Pipe valves:
   - `LETTA_SERVICE_URL`: `http://host.docker.internal:8100`
   - `AGENT_TYPE`: `tutor`

## Verify Everything Works

Run the test suite:

```bash
make verify-agent
```

Expected output:
```
✓ Ruff check
✓ Ruff format
✓ Typecheck
✓ Tests (45 tests in 2.1s)
```

## Next Steps

- [[Architecture]] - Understand the system design
- [[HTTP-Service]] - Explore all endpoints
- [[Development]] - Set up your development environment
- [[Configuration]] - All configuration options

## Troubleshooting

### Letta server not responding

```bash
# Check if container is running
docker ps | grep letta

# View logs
docker logs letta-server

# Restart
docker restart letta-server
```

### Agent creation fails

```bash
# Verify Letta health
curl http://localhost:8283/v1/health

# Check service logs
uv run letta-server --log-level DEBUG
```

### Tests failing

```bash
# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_server/test_endpoints.py -v
```
