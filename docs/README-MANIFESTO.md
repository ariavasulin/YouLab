# YouLab

**Who controls your AI's context?**

---

You have probally heard that for LLMs, context is everything. Especially context about YOU.

And yet: **Who controls it?**

- What context does your AI have about you?
- How has that context changed over time?
- What motivated those changes?
- Who decided what gets written?

If you can't answer these questions, you don't have a relationship with AI. You have a product experience designed by someone else. OpenAI, Google, are on the presepece of selling not just your attention, but [https://hdsr.mitpress.mit.edu/pub/ujvharkk/release/1 | Intention].
---

## Three Principles for Personalize User Context

### 1. Transparency

**What is your context? How has it changed? What motivated the changes?**

Most AI systems are black boxes. They "personalize" but you can't see how. They "learn" but you can't see what. The context that shapes every response you receive is invisible to you.

This isn't a privacy problem. It's a trust problem.

YouLab makes context visible:

```
.data/users/{you}/
    memory-blocks/
        student.md          ← What the AI "knows" about you
        journey.md          ← Your progress and insights
    pending_diffs/
        {diff_id}.json      ← Proposed changes, awaiting your approval
```

Every change is a git commit. Every commit has a reason. Every reason you can read.

When an AI tutor thinks it's learned something about you—that you engage better with examples, that you seem anxious about deadlines, that creative prompts spark your best work—it doesn't silently update its model. It creates a **pending diff**:

```json
{
  "block_label": "student",
  "field": "insights",
  "operation": "append",
  "proposed_value": "Responds well to Socratic questioning...",
  "reasoning": "Observed during problem-solving discussion",
  "status": "pending"
}
```

You review. You approve or reject. The AI's understanding of you is authored by you.

### 2. Portability

**Where can you take your context?**

Your learning history shouldn't be trapped in one platform, one model, one company. Context stored in text outlives context stored in weights.

YouLab stores memory in token-space, not weight-space:

- **Export everything** at any time (JSON, markdown, full git clone)
- **Upgrade models** without losing who you are to the AI
- **Switch providers** without starting over
- **Self-host** the entire system

When the next breakthrough model arrives, your context comes with you.

### 3. Authority

**Who decides what gets written to context? You? A software engineer? An algorithm?**

The shift from attention economy to intent economy means AI systems will increasingly act on your behalf. But whose intent? Whose values?

YouLab's answer: **yours**.

- Agents can *propose* changes to memory
- Only *you* can approve them
- Conflicts are resolved by the person the context describes
- No silent updates, no hidden personalization

This isn't just user control—it's a different power relationship between humans and AI systems.

---

## Why This Matters for Education

We're building YouLab as an AI tutoring platform because education makes the stakes concrete.

A tutor who "personalizes" your learning but won't tell you what they think they know about you? That's surveillance, not teaching.

A system that "adapts" to your learning style but you can't see or correct its model? That's manipulation, not education.

The best human tutors are transparent about their understanding. They say "I notice you learn better with examples" and you can correct them: "Actually, I prefer to struggle with theory first." The relationship improves because the model is shared.

AI tutoring should work the same way.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Chat Interface                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      YouLab Service                              │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────────┐
│   │  Chat Agent                                                 │
│   │  Tools: edit_memory_block, query_history, advance_lesson    │
│   └─────────────────────────────────────────────────────────────┘
│                                                                 │
│   ┌─────────────────────────────────────────────────────────────┐
│   │  Background Agents                                          │
│   │  Proactive analysis → pending diffs → your approval         │
│   └─────────────────────────────────────────────────────────────┘
│                                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  ┌───────────┐     ┌───────────┐     ┌───────────┐
  │   Dolt    │     │  Honcho   │     │    LLM    │
  └───────────┘     └───────────┘     └───────────┘
   Version-          Theory of         Inference
   controlled        mind              (stateless)
   context
```

**Why these pieces:**

- **Dolt**: MySQL with git semantics. Every context change is a commit with full history.
- **Honcho**: Ask natural language questions about conversation history. "How does this student learn best?" → synthesized insight.
- **LLM**: Stateless inference. The intelligence is in the context, not locked in the model.

All open source. All self-hostable.

---

## The Memory System

### Your Context, Structured

Context is organized into **blocks**—structured markdown files that the AI reads and (with your approval) writes:

```toml
[block.student]
label = "human"
description = "Who this student is"
field.profile = { type = "string", description = "Rich narrative understanding" }
field.insights = { type = "string", description = "Key observations" }

[block.journey]
label = "journey"
description = "Learning progress"
field.module_id = { type = "string", description = "Current position" }
field.grader_notes = { type = "string", description = "Background observations" }
```

These aren't hidden embeddings. They're readable files you can open, edit, and version control.

### Background Agents

AI that works for you between sessions:

```toml
[[task]]
name = "progression-grader"
on_idle = true
idle_threshold_minutes = 5

system = """Review recent conversations and assess progress
toward learning objectives."""

tools = ["query_honcho", "edit_memory_block"]
```

Background agents observe your learning and *propose* updates to context. You decide what sticks.

When you return, your tutor has been thinking about you—but hasn't changed its understanding without your sign-off.

---

## Current State

YouLab is in active development. First course: **college essay coaching**.

**Working today:**
- Per-user context with full version history
- TOML-based course configuration
- Pending diffs for all agent-proposed changes
- Background agents (manual triggers)
- Conversation persistence via Honcho

**Coming next:**
- Scheduled/idle triggers for background agents
- Full export functionality
- Multi-course support

---

## The Thesis

We're shifting from an attention economy to an intent economy. AI systems will increasingly act on our behalf, make decisions for us, shape our experiences.

The question isn't whether AI will have context about you. It will.

The question is: **Who controls it?**

YouLab is our answer: You do.

- **Transparent**: See what the AI thinks it knows
- **Portable**: Take your context anywhere
- **Authoritative**: You decide what's true about you

This is what we think AI-human relationships should look like.

---

## Links

- [Honcho](https://docs.honcho.dev/) - Theory-of-mind for AI
- [Dolt](https://docs.dolthub.com/) - Version-controlled database
- [Letta](https://docs.letta.com/) - Self-editing memory paradigm

---

*YouLab: Your context, your control.*
