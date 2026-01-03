#!/bin/bash
# Documentation sync analysis - agent-friendly output
# Usage: ./hack/docs-diff.sh [--verbose]
#
# Default: Compact output for agents (swallow success details)
# --verbose: Full output for human review

set -euo pipefail

VERBOSE="${1:-}"

# Find last docs commit
LAST_DOCS_COMMIT=$(git log -1 --format="%H" -- docs/ CLAUDE.md 2>/dev/null || echo "")

if [ -z "$LAST_DOCS_COMMIT" ]; then
    echo "error: No documentation commits found"
    exit 1
fi

LAST_DOCS_SHORT=$(git log -1 --format="%h" "$LAST_DOCS_COMMIT")
LAST_DOCS_MSG=$(git log -1 --format="%s" "$LAST_DOCS_COMMIT")
LAST_DOCS_DATE=$(git log -1 --format="%ar" "$LAST_DOCS_COMMIT")

# Count changes since docs update
CODE_COMMITS=$(git rev-list --count "$LAST_DOCS_COMMIT"..HEAD -- 'src/' 'tests/' '*.py' 'pyproject.toml' 'Makefile' 2>/dev/null || echo "0")
CHANGED_FILES=$(git diff --name-only "$LAST_DOCS_COMMIT"..HEAD -- 'src/' 'tests/' 2>/dev/null | wc -l | tr -d ' ')

# Agent-friendly compact output
if [ "$VERBOSE" != "--verbose" ]; then
    if [ "$CODE_COMMITS" = "0" ]; then
        echo "✓ Docs in sync (no code changes since $LAST_DOCS_SHORT)"
        exit 0
    fi

    echo "docs_baseline: $LAST_DOCS_SHORT"
    echo "docs_date: $LAST_DOCS_DATE"
    echo "code_commits_since: $CODE_COMMITS"
    echo "files_changed: $CHANGED_FILES"
    echo ""
    echo "changed_files:"
    git diff --name-only "$LAST_DOCS_COMMIT"..HEAD -- 'src/' 'tests/' 2>/dev/null || true
    exit 0
fi

# Verbose output for humans
echo "=== Documentation Sync Analysis ==="
echo ""
echo "Last docs update: $LAST_DOCS_SHORT $LAST_DOCS_MSG ($LAST_DOCS_DATE)"
echo ""

if [ "$CODE_COMMITS" = "0" ]; then
    echo "✓ No code changes since last documentation update"
    exit 0
fi

echo "=== Code Changes Since Docs Update ($CODE_COMMITS commits) ==="
git log --oneline "$LAST_DOCS_COMMIT"..HEAD -- 'src/' 'tests/' '*.py' 'pyproject.toml' 'Makefile' 2>/dev/null || echo "None"
echo ""
echo "=== Changed Files ($CHANGED_FILES files) ==="
git diff --name-only "$LAST_DOCS_COMMIT"..HEAD -- 'src/' 'tests/' 2>/dev/null || echo "None"
