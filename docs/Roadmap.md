# Roadmap

[[README|<- Back to Overview]]

Implementation roadmap for YouLab's AI tutoring platform.

## Current Status

| Phase | Status |
|-------|--------|
| 1-6 | **Complete** - HTTP Service, Honcho, Curriculum, Background Workers |
| 7: Onboarding | Not Started |

---

## Next: Phase 7 - Student Onboarding

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
4. First step setup

---

## Completed Phases Summary

### Phase 1: HTTP Service
FastAPI service with agent management, streaming chat, strategy agent.

### Phase 2: User Identity
Per-user agents via OpenWebUI integration, agent naming convention.

### Phase 3: Honcho Integration
Message persistence for theory-of-mind modeling, graceful degradation.

### Phase 4: Thread Context
Chat title extraction and metadata flow.

### Phase 5: Curriculum System
TOML-based course definitions with hot-reload.

### Phase 6: Background Worker
Scheduled Honcho queries with memory enrichment.

---

## Out of Scope

- Full user management UI
- Multi-facilitator support
- Course marketplace
- Production deployment infrastructure
- Automated pedagogical testing

---

## Version History

| Version | Date | Milestone |
|---------|------|-----------|
| 0.1.0 | 2025-12-31 | Phase 1: HTTP Service |
| - | 2026-01 | Phases 2-6 complete |

---

## Related Pages

- [[Architecture]] - System design
- [[HTTP-Service]] - Service implementation
