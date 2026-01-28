# Universal Claude Guidelines

## Task Approach (Inline TODOs)

**Let the codebase carry the truth.** Instead of external task lists or reports, embed TODO stubs directly in the code where work is needed.

```python
# TODO(feature): validate input before processing
# TODO(auth): add rate limiting to login endpoint
```

**Why this works:**
- The codebase is the source of truth - no stale external docs
- Missing work lives exactly where it belongs
- `grep -r "TODO" src/` shows all remaining work
- When done, the TODO disappears naturally
- Aligns with small-scope, clear-intent work

**When implementing:** Insert scoped TODOs for anything deferred, incomplete, or intentionally skipped. Be explicit, not vague.

## Documentation (Progressive Disclosure)

Don't memorize - look things up. Use `./hack/` scripts when available.

**Principles:**
- Prefer pointers to copies - reference files, don't duplicate content
- Tell Claude *when* to read something, not everything upfront
- If `docs/` exists, it's the authoritative source of truth

**Precedence:** `docs/` > `thoughts/shared/` > code comments

## Thoughts Directory

The `thoughts/` directory is managed via `humanlayer thoughts` (not committed to repos).

```
thoughts/
  {username}/           # Personal notes
  shared/               # Team notes
    research/           # Research documents
    plans/              # Implementation plans
  global/               # Cross-repo notes
  searchable/           # Auto-generated (NEVER write here)
```

**Important**: Never write to `thoughts/searchable/` — it gets wiped on every sync. Write to `thoughts/shared/` instead.

## Hack Scripts

Most repos have a `hack/` directory with helper scripts. Check what's available:

```bash
ls hack/                    # See available scripts
./hack/claude-docs.sh       # Query docs (if available)
```

## Worktrees & Implementation Sessions

Use git worktrees for isolated implementation work:

```bash
# Create worktree (runs setup, copies .claude/, inits thoughts)
./hack/create_worktree.sh <branch-name> [base-branch]

# Launch implementation session
humanlayer launch --model opus -w .trees/<branch-name> \
  "/implement_plan at thoughts/shared/plans/<plan>.md ..."

# Cleanup when done
./hack/cleanup_worktree.sh <branch-name>
```

Use CodeLayer to monitor running sessions.

**Common slash commands:**
- `/implement_plan` - Execute a plan from thoughts/shared/plans/
- `/create_plan` - Research and create a new implementation plan
- `/commit` - Create a git commit with user approval

## Linear

Assignee: **ARI** (Ariav Asulin)
