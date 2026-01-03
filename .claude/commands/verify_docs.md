---
description: Verify /docs and CLAUDE.md accuracy against recent codebase changes
model: opus
---

# Verify Documentation Accuracy

You are tasked with verifying that `/docs` and `CLAUDE.md` accurately reflect the current codebase. This command uses `/research_codebase` to produce a discrepancy report.

## Step 1: Get Git Context

Run the docs-diff script to understand what changed:

```bash
./hack/docs-diff.sh
```

Parse the output to get:
- `docs_baseline`: Last commit that touched docs
- `code_commits_since`: Number of code commits since
- `files_changed`: List of changed source files

If output shows "Docs in sync", respond:
```
Documentation is in sync with the codebase. No code changes since the last documentation update.
```
And stop.

## Step 2: Map Changes to Documentation

Based on the changed files, identify which docs need verification:

| Changed Path Pattern | Docs to Verify |
|---------------------|----------------|
| `server/` | `docs/HTTP-Service.md`, `docs/API.md`, `docs/Schemas.md` |
| `memory/` | `docs/Memory-System.md` |
| `agents/` | `docs/Agent-System.md`, `docs/Strategy-Agent.md` |
| `pipelines/` | `docs/Pipeline.md` |
| `config/` | `docs/Configuration.md`, `docs/Settings.md` |
| Any `.py` | `CLAUDE.md` (structure, key files) |

## Step 3: Research Each Doc Area

For each relevant doc, invoke research_codebase thinking (via Task agents) to compare:

**Research prompt template**:
```
Compare docs/{doc_file}.md against the current implementation.

Focus on these changed files: {list of changed files}

Document:
1. Claims in the doc that match current code (with file:line refs)
2. Claims that no longer match (discrepancies)
3. New features in code not mentioned in docs

Do NOT suggest fixes. Only document what IS vs what the doc SAYS.
```

Run these in parallel for efficiency.

## Step 4: Generate Verification Report

Write to `thoughts/shared/research/YYYY-MM-DD-docs-verification.md`:

```markdown
---
date: {ISO timestamp}
researcher: claude
git_commit: {current HEAD}
docs_baseline: {last docs commit}
code_commits_since: {count}
status: complete
---

# Documentation Verification Report

**Baseline**: {docs_baseline} ({date})
**Analyzed**: {code_commits_since} commits, {files_changed} files

## Summary

| Doc File | Status | Discrepancies |
|----------|--------|---------------|
| HTTP-Service.md | {Accurate/Needs Update} | {count} |
| ... | ... | ... |

## Discrepancies Found

### docs/HTTP-Service.md

#### Inaccurate Claims
- Line X: Doc says "{quote}" but code at `file:line` does Y

#### Missing Coverage
- Feature at `file:line` not documented

### CLAUDE.md
...

## Files Changed Since Docs Update
{list with brief descriptions}
```

## Step 5: Present and Sync

1. Run `humanlayer thoughts sync`
2. Present summary:
```
Verification complete. Report saved to:
thoughts/shared/research/YYYY-MM-DD-docs-verification.md

Summary:
- X docs verified accurate
- Y docs need updates (Z total discrepancies)

Review the report, then tell me which docs to update.
```

## Important Notes

- This is READ-ONLY - no modifications to docs
- Use parallel agents for efficiency
- Include file:line references for all claims
- Focus on accuracy, not style
