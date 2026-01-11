# YouLab

> AI-powered course delivery platform with state of the art theory of mind

YouLab is a course-agnostic learning platform built on [Letta](https://github.com/letta-ai/letta) (formerly MemGPT) that provides personalized AI tutoring with persistent memory. The first course is **college essay coaching**.

## What is YouLab?

YouLab combines a chat-based interface with sophisticated memory management to create tutors that truly remember and understand each student. Unlike stateless chatbots, YouLab agents maintain:

- **Persona memory** - Who the tutor is, their expertise, and teaching style
- **Human memory** - What they know about the student, preferences, and progress
- **Archival memory** - Long-term storage for completed tasks and historical context

## Architecture

```
OpenWebUI (Chat UI)
       |
       v
  Pipeline (Pipe)  ---> Extract user context, route to agent
       |
       v
HTTP Service (FastAPI:8100)
       |
       +---> AgentManager (per-user agents)
       |
       +---> StrategyManager (shared RAG agent)
       |
       v
 Letta Server (:8283)  ---> Claude API
```

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: HTTP Service | **Complete** | FastAPI service with agent management and streaming |
| Phase 2: User Identity | **Complete** | Per-user agents via OpenWebUI integration |
| Phase 3: Honcho | **Complete** | Message persistence for theory-of-mind modeling |
| Phase 4: Thread Context | **Complete** | Chat title extraction and metadata flow |
| Phase 5: Curriculum | **Complete** | TOML-based course definitions with hot-reload |
| Phase 6: Background Worker | **Complete** | Scheduled Honcho queries with memory enrichment |
| Phase 7: Onboarding | Not Started | Student setup flow |

## Start Here

| I want to... | Read |
|--------------|------|
| Get running quickly | [[Quickstart]] |
| Understand the system | [[Architecture]] |
| Add/modify a course | [[config-schema]] |
| Contribute code | [[Development]] |
| Use the API | [[API]] |
| Understand Letta | [[Letta-Integration]] |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | OpenWebUI |
| Pipeline | Python Pipe extension |
| HTTP Service | FastAPI + Uvicorn |
| Agent Framework | Letta v0.16.1 |
| LLM | Claude (via OpenAI compat) |
| Observability | Langfuse + structlog |
| Type Checking | basedpyright |
| Linting | Ruff |
| Testing | pytest + pytest-asyncio |
