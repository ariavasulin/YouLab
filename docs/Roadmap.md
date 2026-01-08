# Roadmap

[[README|← Back to Overview]]

Implementation roadmap for YouLab's AI tutoring platform.

## Vision

A complete system where:
1. Students log into OpenWebUI, each routed to their personal Letta agent
2. All messages persisted to Honcho for long-term ToM modeling
3. Agent context adapts based on which chat/module student is in
4. Curriculum defined in markdown, hot-reloadable without redeploy
5. Background process periodically enriches agent memory from Honcho insights
6. New students smoothly onboarded with initial setup flow

---

## Current Status

```
┌─────────────────────────────────────────────────────────────────┐
│                         Completed                                │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: HTTP Service ✓                                        │
│  Phase 2: User Identity ✓ (absorbed into Phase 1)               │
│  Phase 3: Honcho Integration ✓                                  │
│  Phase 4: Thread Context ✓                                      │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────────┐
                    │     Next: Phase 5, 6     │
                    └──────────────────────────┘
```

---

## Phase Overview

| Phase | Name | Status | Dependencies |
|-------|------|--------|--------------|
| 1 | HTTP Service | **Complete** | - |
| 2 | User Identity & Routing | **Complete** (absorbed into Phase 1) | Phase 1 |
| 3 | Honcho Integration | **Complete** | Phase 1 |
| 4 | Thread Context | **Complete** | Phase 1 |
| 5 | Curriculum Parser | Planned | Phase 4 |
| 6 | Background Worker | Planned | Phase 3 |
| 7 | Student Onboarding | Planned | Phase 5 |

### Dependency Graph

```
Phase 1: HTTP Service (includes Phase 2)
    │
    ├── Phase 3: Honcho ──────┐
    │       │                 │
    │       └── Phase 6: Background Worker
    │
    └── Phase 4: Thread Context
            │
            └── Phase 5: Curriculum
                    │
                    └── Phase 7: Onboarding
```

---

## Phase 1: HTTP Service (Complete)

Convert LettaStarter from a library to an HTTP service.

### Deliverables

- [x] FastAPI application on port 8100
- [x] Health endpoint with Letta connection status
- [x] Agent CRUD endpoints
- [x] Synchronous chat endpoint
- [x] SSE streaming chat endpoint
- [x] Agent template system
- [x] Strategy agent for RAG
- [x] Langfuse tracing

### Key Files

- `src/letta_starter/server/main.py`
- `src/letta_starter/server/agents.py`
- `src/letta_starter/agents/templates.py`

---

## Phase 2: User Identity & Routing (Complete)

Ensure each student gets their own persistent agent.

> **Note**: This phase was absorbed into Phase 1 during implementation.

### Deliverables

- [x] User ID extraction (`__user__["id"]`)
- [x] Agent creation and lookup
- [x] Agent caching for fast lookups
- [x] Per-user agent naming convention (`youlab_{user_id}_{agent_type}`)

### Deferred to Future Phases

- First-interaction detection (Phase 7: Onboarding)
- Course-specific memory fields (Phase 4: Thread Context)

---

## Phase 3: Honcho Integration (Complete)

Persist all messages to Honcho for theory-of-mind modeling.

### Deliverables

- [x] HonchoClient with lazy initialization
- [x] Fire-and-forget message persistence
- [x] Integration with `/chat` endpoint
- [x] Integration with `/chat/stream` endpoint
- [x] Health endpoint reports Honcho status
- [x] Graceful degradation when Honcho unavailable
- [x] Configuration via environment variables
- [x] Unit and integration tests

### Key Files

- `src/letta_starter/honcho/client.py`
- `src/letta_starter/config/settings.py` (ServiceSettings)
- `src/letta_starter/server/main.py` (lifespan, endpoints)
- `tests/test_honcho.py`
- `tests/test_server_honcho.py`

### What's NOT Included (Future Work)

- Dialectic queries from Honcho (Phase 6)
- Working representation updates (Phase 6)
- ToM-informed agent behavior (Phase 6)

---

## Phase 4: Thread Context (Complete)

Chat title extraction and management for thread context.

### Deliverables

- [x] Chat title extraction from OpenWebUI database (`_get_chat_title`)
- [x] Chat title passed to HTTP service in requests
- [x] Chat title stored in Honcho as message metadata
- [x] Chat title rename capability (`_set_chat_title`)
- [x] Unit tests for title operations

### Key Files

- `src/letta_starter/pipelines/letta_pipe.py` (`_get_chat_title`, `_set_chat_title`)
- `tests/test_pipe.py` (`TestGetChatTitle`, `TestSetChatTitle`)

### What's NOT Included (Simplified Scope)

Original plan included complex title parsing ("Module 1 / Lesson 2" format), context caching, and memory block updates. These were deferred as:
- 1:1 OpenWebUI→Honcho thread mapping simplifies architecture
- Primary course uses single thread
- Title metadata already flows through system

---

## Phase 5: Curriculum Parser

Load course definitions from markdown files.

### Goals

- Define curriculum in markdown
- Parse into structured data
- Hot-reload on file changes

### Proposed Format

```markdown
# courses/college-essay/module-1.md
---
name: Self-Discovery
lessons:
  - strengths-assessment
  - processing-results
---

## Lesson: strengths-assessment
trigger: module_start
objectives:
  - Complete Clifton StrengthsFinder
  - Initial reaction conversation

### Agent Instructions
[Instructions for agent behavior]

### Completion Criteria
- Articulated one resonant strength
- Minimum 3 turns
```

---

## Phase 6: Background Worker

Query Honcho dialectic and update agent memory on idle.

### Goals

- Detect idle students
- Query dialectic for insights
- Update memory blocks
- Enrich agent behavior

### Trigger Conditions

- Idle timeout (configurable, e.g., 10 minutes)
- Manual endpoint (`POST /background/run`)

---

## Phase 7: Student Onboarding

Handle new student first-time experience.

### Goals

- Detect new students
- Initialize agent with onboarding context
- Guide through setup flow
- Transition to Module 1

### Onboarding Flow

1. Welcome message
2. Collect basic info (name, goals)
3. Explain system capabilities
4. First lesson setup

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
3. Verify isolation (different agents)
4. Verify continuity (same agent across sessions)
5. Check Honcho dashboard for messages
6. Trigger background process, verify updates
7. Modify curriculum, verify hot-reload
8. New user goes through onboarding

---

## Related Pages

- [[Architecture]] - System design
- [[HTTP-Service]] - Phase 1 implementation
- [[Memory-System]] - Memory management
- [[Agent-System]] - Agent templates

