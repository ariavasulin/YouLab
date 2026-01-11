# Quick Start

[[README|← Back to Overview]]

Get the full YouLab stack running locally.

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- [Docker](https://docs.docker.com/get-docker/) (for OpenWebUI, Ollama, and Letta)

## Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| OpenWebUI | 3000 | Chat frontend |
| Ollama | 11434 | Local LLM inference (optional) |
| Letta Server | 8283 | Agent framework with persistent memory |
| HTTP Service | 8100 | FastAPI bridge (AgentManager, StrategyManager) |

```
Browser → OpenWebUI:3000 → HTTP Service:8100 → Letta:8283 → Claude API
```

---

## Step 1: Clone and Setup

```bash
git clone https://github.com/youlab/youlab.git
cd youlab

# Install dependencies and pre-commit hooks
make setup
```

---

## Step 2: Start Docker Services

### Option A: Full Stack (Recommended)

Start OpenWebUI, Ollama, and Letta together:

```bash
# Start OpenWebUI + Ollama
cd OpenWebUI/open-webui
docker compose up -d

# Start Letta (from project root)
cd ../..
docker run -d \
  --name letta \
  -p 8283:8283 \
  -v letta-data:/root/.letta \
  letta/letta:latest
```

### Option B: Letta Only (API Development)

If you only need the backend API without the chat UI:

```bash
docker run -d \
  --name letta \
  -p 8283:8283 \
  -v letta-data:/root/.letta \
  letta/letta:latest
```

### Verify Docker Services

```bash
# Check all containers are running
docker ps

# Expected output:
# CONTAINER ID   IMAGE                        PORTS                    NAMES
# ...            ghcr.io/open-webui/open-webui   0.0.0.0:3000->8080/tcp   open-webui
# ...            ollama/ollama                   11434/tcp                ollama
# ...            letta/letta                     0.0.0.0:8283->8283/tcp   letta

# Test Letta health
curl http://localhost:8283/v1/health
# Should return: {"status": "ok"}
```

---

## Step 3: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Letta connection
LETTA_BASE_URL=http://localhost:8283

# LLM provider (choose one)
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Step 4: Start HTTP Service

```bash
uv run youlab-server
```

The service starts on `http://localhost:8100`.

```bash
# Verify it's running
curl http://localhost:8100/health
# Should return: {"status": "ok", "letta_connected": true, ...}
```

---

## Step 5: Access the UI

Open http://localhost:3000 in your browser.

**First-time setup**:
1. Create an admin account (first user becomes admin)
2. Go to Admin Panel → Settings → Functions → Pipes
3. Add the YouLab Pipe from `src/youlab_server/pipelines/letta_pipe.py`
4. Configure the Pipe valves:
   - `LETTA_SERVICE_URL`: `http://host.docker.internal:8100`
   - `AGENT_TYPE`: `tutor`

---

## Step 6: Test the API

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

---

## Quick Reference

### Start Everything

```bash
# Docker services
cd OpenWebUI/open-webui && docker compose up -d && cd ../..
docker start letta  # if already created

# HTTP service
uv run youlab-server
```

### Stop Everything

```bash
# Stop HTTP service: Ctrl+C

# Stop Docker
docker stop open-webui ollama letta
```

### Restart After Reboot

```bash
# Containers may be stopped or paused after reboot
docker start open-webui ollama letta

# If containers show as "Up" but are unreachable:
docker unpause open-webui ollama letta

# Start HTTP service
uv run youlab-server
```

---

## Troubleshooting

### OpenWebUI not reachable (localhost:3000)

```bash
# Check container status
docker ps

# If status shows "(Paused)":
docker unpause open-webui

# If container isn't running:
docker start open-webui

# Check logs
docker logs open-webui --tail 50
```

### Letta server not responding

```bash
# Check if container is running
docker ps | grep letta

# View logs
docker logs letta --tail 50

# Restart
docker restart letta
```

### HTTP service port already in use

```bash
# Check what's using port 8100
lsof -i :8100

# Kill the process if needed
kill -9 <PID>
```

### Agent creation fails

```bash
# Verify Letta health
curl http://localhost:8283/v1/health

# Check service logs (run with debug)
LOG_LEVEL=DEBUG uv run youlab-server
```

### Port 3000 conflict with docs server

OpenWebUI uses port 3000. If you need to serve docs simultaneously:

```bash
npx serve docs -p 3001
```

---

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

---

## Next Steps

- [[Architecture]] - Understand the system design
- [[HTTP-Service]] - Explore all API endpoints
- [[Pipeline]] - OpenWebUI Pipe integration details
- [[Configuration]] - All environment variables
