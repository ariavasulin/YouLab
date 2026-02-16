# Roadmap

[[README|← Back to Overview]]

Implementation roadmap for YouLab's AI tutoring platform.

## Vision

A complete system where:
1. Students log into OpenWebUI, each routed to a per-request Agno agent with their memory context
2. All messages persisted to Honcho for long-term theory-of-mind modeling
3. Agent context adapts based on Dolt memory blocks and workspace files
4. Agents defined declaratively in TOML (`config/courses/*/agents.toml`)
5. Background scheduler periodically enriches agent memory from Honcho insights
6. New students smoothly onboarded with initial setup flow

---

## Current Status

The core tutoring platform is built and running on the Ralph/Agno stack:

- **Chat pipeline**: OpenWebUI → Pipe → Ralph Server (FastAPI + Agno) → SSE streaming
- **Memory**: Dolt (version-controlled blocks with proposal/approval workflow) + Honcho (conversation persistence + dialectic queries)
- **Tools**: FileTools, ShellTools, HonchoTools, MemoryBlockTools, LaTeXTools
- **Background**: Cron and idle-triggered tasks via scheduler + executor
- **Workspace sync**: Bidirectional OpenWebUI KB ↔ local file sync

See [Architecture](Architecture.md) for full technical details.

---

## Next: Student Onboarding

Handle new student first-time experience.

### Goals

- Detect new students
- Initialize agent with onboarding context
- Guide through setup flow
- Transition to first course content

### Onboarding Flow

1. Welcome message
2. Collect basic info (name, goals)
3. Explain system capabilities
4. First step setup

---

## What We're NOT Doing

Out of scope for current roadmap:

- Full user management UI (admin dashboard)
- Multi-facilitator support
- Course marketplace / multi-course
- Production deployment infrastructure
- Automated pedagogical testing
- Mobile-specific optimizations

---

## Verification Plan

### Automated

- Unit tests for each component
- Integration tests for message flow
- Pre-commit verification

### Manual

1. Create two test users in OpenWebUI
2. Each sends messages in multiple chats
3. Verify isolation (different workspaces)
4. Verify continuity (same memory blocks across sessions)
5. Check Honcho dashboard for messages
6. Trigger background process, verify updates
7. New user goes through onboarding

---

## Related Pages

- [[Architecture]] - System design
- [[HTTP-Service]] - Server implementation
- [[Memory-System]] - Memory management
- [[Agent-System]] - Agent templates
