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
                    ┌──────────────────────────┐
                    │        Completed         │
                    └──────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: HTTP Service                                          │
│  ════════════════════                                           │
│  ✓ FastAPI server with /health, /agents, /chat endpoints        │
│  ✓ SSE streaming with proper event types                        │
│  ✓ AgentManager with caching                                    │
│  ✓ Agent template system                                        │
│  ✓ Strategy agent with RAG                                      │
│  ✓ Langfuse tracing integration                                 │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────────┐
                    │        In Progress       │
                    └──────────────────────────┘
```

---

## Phase Overview

| Phase | Name | Status | Dependencies |
|-------|------|--------|--------------|
| 1 | HTTP Service | **Complete** | - |
| 2 | User Identity & Routing | Planned | Phase 1 |
| 3 | Honcho Integration | Planned | Phase 2 |
| 4 | Thread Context | Planned | Phase 2 |
| 5 | Curriculum Parser | Planned | Phase 4 |
| 6 | Background Worker | Planned | Phase 3 |
| 7 | Student Onboarding | Planned | Phase 5 |

### Dependency Graph

```
Phase 1: HTTP Service
    │
    └── Phase 2: User Identity
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

## Phase 2: User Identity & Routing

Ensure each student gets their own persistent agent.

### Goals

- First-interaction detection
- Onboarding trigger hooks
- Memory block extensions for course data

### Remaining Work

Phase 1 now handles most of this:
- User ID extraction (`__user__["id"]`)
- Agent creation and lookup
- Caching

Phase 2 adds:
- First-interaction detection
- Course-specific memory fields

---

## Phase 3: Honcho Integration

Persist all messages to Honcho for theory-of-mind modeling.

### Goals

- Every message flows through Honcho
- Dialectic queries inform agent behavior
- Working representation captures student model

### Components to Add

```
src/letta_starter/honcho/
├── client.py     # Honcho API wrapper
└── __init__.py
```

### New Environment Variables

```env
HONCHO_WORKSPACE_ID=youlab
HONCHO_API_KEY=
HONCHO_ENVIRONMENT=production
```

---

## Phase 4: Thread Context Management

Parse chat titles to determine module/lesson context.

### Goals

- Parse "Module 1 / Lesson 2" format
- Update memory blocks when context changes
- Handle "student went back" scenario

### Components to Add

```
src/letta_starter/context/
├── parser.py    # Title parsing
├── cache.py     # Context caching
└── updater.py   # Memory block updates
```

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

