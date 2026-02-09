# YouLab

**Introspective AI tutoring with transparent, user-controlled context.**

YouLab is an AI tutoring platform that makes AI personalization visible, editable, and portable. When the AI tutor learns something about you, it writes it down in a version-controlled memory block. You see every change, approve or reject edits, and own your context.

## The Core Idea

Most AI personalization happens invisibly in model weights or hidden embeddings. YouLab stores context as plain text that you can read, edit, and take with you.

When our AI tutor notices something about you—your learning style, your goals, a pattern in how you work—it proposes an edit to your profile. You see exactly what changed and why. You approve it, modify it, or reject it.

This isn't just a feature. It's the foundation of how we think about AI tutoring.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         OpenWebUI                                │
│                     (Chat Interface)                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │ SSE Stream
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Ralph Server                               │
│                    (FastAPI + Agno Agent)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Per-Request Agent with Workspace-Scoped Tools           │   │
│  │  • FileTools (read/write files in workspace)             │   │
│  │  • ShellTools (execute commands in workspace)            │   │
│  │  • HonchoTools (query conversation history)              │   │
│  │  • MemoryBlockTools (propose edits to student profile)   │   │
│  │  • LaTeXTools (generate PDF notes)                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
           ▼                      ▼
┌─────────────────────┐  ┌────────────────────────────────────────┐
│       Honcho        │  │                Dolt                     │
│ (Message Persistence│  │     (Version-Controlled Database)       │
│  & Dialectic Query) │  │                                        │
│                     │  │  • Memory blocks with git-like history │
│                     │  │  • Proposals as branches                │
│                     │  │  • Approve = merge, Reject = delete    │
└─────────────────────┘  └────────────────────────────────────────┘
```

YouLab uses a modular architecture where each component has a specific job:

- **OpenWebUI** serves the chat interface. Students interact with a familiar ChatGPT-like UI.
- **Ralph** orchestrates AI agents. Each chat request creates a fresh Agno agent with tools scoped to the student's workspace.
- **Honcho** provides long-term memory. Every message is persisted, and agents can query for historical insights about the student.
- **Dolt** stores memory blocks with git-like versioning. When an agent proposes an edit, it creates a database branch. Approval merges the branch; rejection deletes it.

## Memory Blocks

Memory blocks are the heart of YouLab's transparency model. Each block is a named piece of markdown that the AI can read and propose edits to.

### Example: Student Profile

```markdown
## About Me

I'm a junior at Berkeley studying cognitive science with a minor in
CS. I'm interested in the intersection of AI and education—how we
can build learning systems that actually understand students as
individuals, not just metrics.

I work best in the morning. I need to see the big picture before
diving into details. I learn by doing, not by watching.

## Current Goals

- Finish personal statement draft by Friday
- Research three potential topics for supplemental essays
- Figure out my "why Berkeley" story
```

This isn't a hidden embedding or an opaque representation. It's text you can read and modify. When the AI tutor notices something new about you, it proposes an edit:

```diff
  ## About Me

  I'm a junior at Berkeley studying cognitive science with a minor in
  CS. I'm interested in the intersection of AI and education—how we
  can build learning systems that actually understand students as
  individuals, not just metrics.

- I work best in the morning. I need to see the big picture before
+ I work best in the morning, especially with coffee. I need to see
+ the big picture before diving into details. When I'm stuck,
+ stepping away for a walk usually helps more than pushing through.
- diving into details. I learn by doing, not by watching.
+ I learn by doing, not by watching.
```

You see the diff. You see the agent's reasoning ("Student mentioned walking helps when stuck during our last conversation"). You approve, edit, or reject.

### The Proposal Workflow

Agents don't directly modify memory blocks. They propose changes through a branch-based workflow:

1. **Agent calls `propose_memory_edit()`** with the block label, the text to find, the replacement text, and reasoning.

2. **Dolt creates a branch** named `agent/{user_id}/{block_label}` containing the proposed change.

3. **Frontend displays the diff** with the agent's reasoning and confidence level.

4. **User approves or rejects**:
   - **Approve**: Branch merges to main, change is permanent
   - **Reject**: Branch is deleted, no change

This workflow ensures you always know what the AI "thinks" about you and have final say over your profile.

## Agent Configuration

Agents are defined declaratively in TOML files. Each course or domain gets an `agents.toml` that specifies agents, their tools, memory blocks, and background tasks.

### Example: College Essay Tutor

```toml
# config/courses/college-essay/agents.toml

[agent]
name = "Essay Coach"
model = "anthropic/claude-sonnet-4"
system_prompt = """
You are a college essay coach helping students discover and articulate
their authentic stories. You don't write essays for students—you help
them find what to write about.

Focus on:
- Drawing out specific memories and experiences
- Identifying patterns in what energizes them
- Challenging generic or expected narratives
- Asking questions that reveal character

Review the student's profile before each session. Propose updates when
you learn something significant about them.
"""

tools = [
  "file_tools",      # Read/write workspace files
  "honcho_tools",    # Query conversation history
  "memory_blocks",   # Read and propose edits to student profile
  "latex_tools",     # Generate PDF notes
]

blocks = ["student", "journey", "essays"]


[[block]]
label = "student"
title = "Student Profile"
template = """
## About Me

[Background, interests, personality]

## How I Work

[Learning style, preferences, schedule]

## Current Goals

[What they're working toward]
"""

[[block]]
label = "journey"
title = "Discovery Journey"
template = """
## Key Experiences

[Significant moments and stories]

## Themes & Patterns

[Recurring interests, values, contradictions]

## Essay Ideas

[Potential topics with notes]
"""

[[block]]
label = "essays"
title = "Essay Tracker"
template = """
## Schools

| School | Prompt | Status | Notes |
|--------|--------|--------|-------|

## Drafts

[Links to draft files in workspace]
"""


[[task]]
name = "weekly-reflection"
trigger = { type = "cron", schedule = "0 9 * * 1" }  # Monday 9 AM
system_prompt = """
Review this student's activity from the past week. Look for:
- Progress on essays
- New insights about their story
- Areas where they seem stuck

Write a brief reflection in their workspace and propose any
updates to their profile based on what you've observed.
"""
tools = ["honcho_tools", "memory_blocks", "file_tools"]
blocks = ["student", "journey"]


[[task]]
name = "idle-checkin"
trigger = { type = "idle", idle_minutes = 4320, cooldown_minutes = 10080 }  # 3 days idle, 1 week cooldown
system_prompt = """
This student hasn't been active in a few days. Review their
current progress and draft a friendly check-in message suggesting
a next step they could take.
"""
tools = ["honcho_tools", "file_tools"]
blocks = ["student", "essays"]
```

### How It Works

**Agents** define the tutor persona, model, available tools, and which memory blocks they can access. The system prompt sets behavior; tools enable capabilities.

**Blocks** define the schema for memory blocks. Each block has a label, title, and template. When a new student starts, blocks are initialized from templates. If a student already has a block (from another course), it's reused—not overwritten.

**Tasks** define background agents that run on schedules or triggers. They get their own system prompts and tool subsets, enabling automated workflows like weekly reviews or idle check-ins.

### Block Sharing Across Courses

Multiple `agents.toml` files can reference the same block label:

```toml
# config/courses/college-essay/agents.toml
blocks = ["student", "journey", "essays"]

[[block]]
label = "student"
# ... full schema definition
```

```toml
# config/courses/math-tutoring/agents.toml
blocks = ["student", "math-progress"]

# No [[block]] for "student" - uses existing definition
[[block]]
label = "math-progress"
# ... math-specific schema
```

Rules:
- Only one `agents.toml` can define a `[[block]]` schema for a given label
- Conflicting schema definitions are flagged at startup
- Blocks check if the user already has content before initializing from template
- This enables shared context (like "student") across different tutoring domains

## Tools and Capabilities

Ralph agents come equipped with tools that enable a "Claude Code-like" experience for tutoring:

### File and Shell Tools

Students get a personal workspace—a sandboxed filesystem where they can store notes, code, drafts, and resources. The AI tutor has full access to read and write files, execute shell commands, and help with technical work.

```
/data/ralph/users/{user_id}/workspace/
├── essays/
│   ├── personal-statement-v1.md
│   └── why-berkeley-notes.md
├── research/
│   └── topic-ideas.md
└── CLAUDE.md  # Project-specific instructions
```

The `CLAUDE.md` file lets students customize how the tutor behaves for their specific projects.

### Honcho: Conversation Memory

Honcho provides two capabilities:

1. **Message Persistence**: Every message is stored with the student's peer identity. Conversations are durable across sessions.

2. **Dialectic Queries**: Agents can ask questions like "What topics has this student struggled with?" and receive synthesized insights based on conversation history.

This enables tutors that remember context across sessions without stuffing everything into the prompt.

### LaTeX Tools

For subjects requiring mathematical notation or formal documents, the agent can generate PDF notes using LaTeX:

```python
render_notes(
    title="Integration by Parts Summary",
    content=r"""
    \section{The Formula}
    $$\int u \, dv = uv - \int v \, du$$

    \section{How to Choose $u$ and $dv$}
    Use LIATE (Logs, Inverse trig, Algebraic, Trig, Exponential)...
    """
)
```

The PDF renders inline in the chat as an interactive artifact with zoom, navigation, and download.

## Background Tasks

Beyond real-time tutoring, YouLab supports scheduled background agents that can:

- **Review student progress** on a cron schedule
- **Re-engage idle students** who haven't chatted recently
- **Update memory blocks** based on accumulated insights

Background tasks are defined with triggers, system prompts, and tool access:

```python
BackgroundTask(
    name="daily-progress-review",
    system_prompt="Review this student's recent activity...",
    tools=["query_honcho"],
    memory_blocks=["student", "journey"],
    trigger=CronTrigger(schedule="0 3 * * *"),  # 3 AM daily
    user_ids=["student-1", "student-2"],
)
```

Each task run creates a versioned record in Dolt with per-user results, enabling full auditability of automated memory updates.

## Workspace Sync

Student workspaces sync bidirectionally with OpenWebUI's knowledge base:

- **To OpenWebUI**: Files in the workspace become searchable in the KB
- **From OpenWebUI**: Files uploaded to the KB appear in the workspace

Sync uses SHA256 content hashing to detect changes, only transferring files that have actually been modified.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (for Dolt database)
- Tectonic (for LaTeX PDF generation, optional)

### Quick Start

```bash
# Clone and setup
git clone https://github.com/ariavasulin/youlab
cd youlab
make setup

# Start Dolt database
docker compose up -d dolt

# Configure environment
cp .env.example .env
# Edit .env with your OpenRouter API key

# Run Ralph server
uv run ralph-server
```

The server starts on port 8200. Connect OpenWebUI with the Ralph pipe to start chatting.

### Environment Variables

```bash
# Required
RALPH_OPENROUTER_API_KEY=sk-...  # OpenRouter API key

# Optional
RALPH_OPENROUTER_MODEL=anthropic/claude-sonnet-4-20250514
RALPH_USER_DATA_DIR=/data/ralph/users
RALPH_HONCHO_WORKSPACE_ID=ralph
RALPH_HONCHO_ENVIRONMENT=demo  # demo, local, production
```

## Project Structure

```
src/ralph/                      # Main application
├── server.py                   # FastAPI endpoints + Agno agent
├── pipe.py                     # OpenWebUI pipe (HTTP client)
├── config.py                   # Environment configuration
├── dolt.py                     # Dolt database client
├── memory.py                   # Memory context builder
├── honcho.py                   # Honcho message persistence
├── api/
│   ├── blocks.py               # Memory block REST API
│   ├── background.py           # Background task API
│   ├── workspace.py            # Workspace file API
│   └── notes_adapter.py        # OpenWebUI notes bridge
├── tools/
│   ├── memory_blocks.py        # Claude Code-style block editing
│   ├── honcho_tools.py         # Conversation history queries
│   └── latex_tools.py          # PDF note generation
├── background/
│   ├── models.py               # Task and run data models
│   ├── scheduler.py            # Cron and idle triggers
│   ├── executor.py             # Agent execution per user
│   └── registry.py             # Task registration
└── sync/
    ├── workspace_sync.py       # Bidirectional file sync
    ├── openwebui_client.py     # OpenWebUI API client
    └── knowledge.py            # Knowledge base management

src/youlab_server/              # Legacy Letta-based stack (deprecated)
config/courses/                 # TOML course configs (legacy)
```

## Development

```bash
# Run all checks (lint + typecheck + tests)
make verify-agent

# Quick check (lint + typecheck only)
make check-agent

# Auto-fix lint issues
make lint-fix

# Run tests
make test-agent
```

Pre-commit hooks run `make verify` automatically. Commits are blocked if checks fail.

## The Vision

YouLab bets that users care about the integrity of their AI profiles.

Most AI companies assume personalization should be invisible—a black box that just works. We think the best tutors already share their observations: "I notice you light up when you talk about robotics but go quiet when you mention pre-med. What's that about?"

That transparency isn't a bug. It's the whole point.

When AI systems know things about you, you should know what they know. When they want to update that knowledge, you should have a say. When you leave, you should be able to take your context with you.

This is what we're building.

---

*YouLab is in active development. For questions, issues, or to follow along, visit the [GitHub repository](https://github.com/ariavasulin/youlab).*
