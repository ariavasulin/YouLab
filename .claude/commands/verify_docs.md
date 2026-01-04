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

## Step 2: Research discrepancies between documentation and codebase 

Invoke the research_codebase slash command to compare the entirety of the documentation available at /docs and the CLAUDE.MD to the changed files in identified in step 1. Do not edit the codebase.
