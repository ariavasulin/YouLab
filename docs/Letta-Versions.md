# Letta Version Compatibility

[[README|← Back to Overview]]

Version history, compatibility notes, and migration guidance.

## Current Versions

| Package | Version | Released |
|---------|---------|----------|
| `letta` (server) | **0.10.0** | Latest on PyPI |
| `letta-client` (SDK) | **1.6.2** | Dec 2025 |

> **Note**: GitHub releases (0.16.x) use different versioning than PyPI packages.

---

## YouLab Compatibility

```toml
# pyproject.toml
"letta>=0.6.0"
```

This specifies a minimum version floor. The actual installed version is the latest compatible (currently 0.10.0).

---

## Package History

### letta (Server Package)

| Version | Key Changes |
|---------|-------------|
| 0.10.0 | Current stable |
| 0.9.x | Stability improvements |
| 0.8.x | Feature additions |
| 0.7.x | Multiple iterations |
| 0.6.x | Python 3.13 support, TypeScript SDK alpha |
| 0.5.x | Dynamic model listing, Alembic migrations |

### letta-client (Python SDK)

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.6.2 | Dec 2025 | Request-id for steps, zai provider |
| 1.6.1 | Dec 2025 | Summary message fix for compaction |
| 1.6.0 | Dec 2025 | Compaction response feature |
| 1.5.0 | Dec 2025 | Message ID in search |
| 1.4.0 | Dec 2025 | Agent_id in search, compaction settings |
| 1.3.x | Nov-Dec 2025 | Structured outputs, template endpoints |
| 1.2.0 | Nov 2025 | Search routes, new model support |

---

## Breaking Changes

### v0.12 (Major Architecture Change)

**New Agent Architecture**:
- `letta_v1_agent` introduced
- No `send_message` tool required
- Heartbeat system removed
- Works with any chat model (including non-tool-calling)

**API Changes**:
- `sources` routes renamed to `folders`
- `get_folder_by_name` deprecated → use `client.folders.list(name=...)`

### v0.5

**Deprecated**:
- `letta configure` command
- `letta quickstart` command
- `~/.letta/config` file

**New Pattern**:
- Environment variable configuration
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

---

## Agent Architecture Evolution

| Architecture | Status | Key Features |
|--------------|--------|--------------|
| `memgpt_agent` | Deprecated | `send_message` tool, heartbeats |
| `memgpt_v2_agent` | Deprecated | Sleep-time agents, file tools |
| `letta_v1_agent` | Legacy | Native reasoning, no heartbeats |
| (no agent_type) | **Current** | Full native reasoning, any LLM |

### Recommendation

Create agents without `agent_type`:

```python
# Current (recommended)
agent = client.agents.create(
    model="openai/gpt-4o-mini",
    memory_blocks=[...],
    # No agent_type specified
)

# Legacy (avoid)
agent = client.agents.create(
    agent_type="letta_v1_agent",  # Don't do this
    ...
)
```

---

## SDK Package Names

### Current (Recommended)

```python
# Modern SDK
from letta_client import Letta

client = Letta(base_url="http://localhost:8283")
```

Install: `pip install letta-client`

### Legacy

```python
# Old pattern (still works in letta package)
from letta import create_client

client = create_client(base_url="http://localhost:8283")
```

The `letta` package includes both server and a legacy client.

---

## Environment Variables

### v0.5+ Configuration

```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
VLLM_API_BASE=http://localhost:8000

# Letta Connection
LETTA_BASE_URL=http://localhost:8283
LETTA_API_KEY=...  # For Letta Cloud
```

### Legacy (Deprecated)

```bash
# These no longer work
# ~/.letta/config
# letta configure
```

---

## Model Format Changes

### Current Format

```python
model = "provider/model-name"

# Examples
"openai/gpt-4o-mini"
"anthropic/claude-3-5-sonnet"
"ollama/llama2:7b"
```

### Old Format (Some Contexts)

```python
# Without provider prefix
model = "gpt-4o-mini"
```

---

## Migration Checklist

### From v0.5.x to v0.10.x

1. **Update imports**:
   ```python
   # Old
   from letta import RESTClient

   # New
   from letta_client import Letta
   ```

2. **Use environment variables**:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```

3. **Remove deprecated config**:
   - Delete `~/.letta/config` if exists
   - Stop using `letta configure`

4. **Update agent creation**:
   - Remove `agent_type` parameter
   - Use model handle format: `provider/model-name`

### From Legacy SDK to letta-client

1. **Install new package**:
   ```bash
   pip install letta-client
   ```

2. **Update client initialization**:
   ```python
   # Old
   client = create_client(base_url=...)

   # New
   client = Letta(base_url=...)
   ```

3. **Update method calls**:
   ```python
   # Old patterns may differ
   client.create_agent(...)

   # New
   client.agents.create(...)
   ```

---

## Checking Versions

```bash
# Check installed versions
pip show letta
pip show letta-client

# Or with uv
uv pip show letta
uv pip list | grep letta
```

```python
# In code
import letta_client
print(letta_client.__version__)
```

---

## Known Issues

### Upgrade Crashes

[GitHub Issue #2211](https://github.com/letta-ai/letta/issues/2211): Some environments experienced crashes upgrading from 0.6.1 to 0.6.2.

**Workaround**: Clean install in fresh virtual environment.

### Database Migrations

Upgrading may require database migrations:

```bash
# Migrations run automatically on server start
letta server
```

If issues occur:
1. Backup database
2. Check migration logs
3. Consider fresh database for major upgrades

---

## Staying Updated

### Watch Releases

- [GitHub Releases](https://github.com/letta-ai/letta/releases)
- [PyPI letta](https://pypi.org/project/letta/)
- [PyPI letta-client](https://pypi.org/project/letta-client/)

### Update Commands

```bash
# Update to latest
pip install --upgrade letta letta-client

# Or with uv
uv pip install --upgrade letta letta-client
```

---

## External Resources

- [Letta GitHub](https://github.com/letta-ai/letta)
- [letta-python SDK](https://github.com/letta-ai/letta-python)
- [Legacy Architectures Guide](https://docs.letta.com/guides/legacy/architectures_overview)
- [API Changelog](https://docs.letta.com/api-reference/changelog)

---

## Related Pages

- [[Letta-Concepts]] - Core architecture
- [[Letta-SDK]] - SDK patterns
- [[Configuration]] - YouLab settings
