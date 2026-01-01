#!/bin/bash
# Wrapper for launching Claude Desktop research via Option+Option quick add
# Usage: ./hack/claude-research.sh "Your research query"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$1" ]; then
    echo "Usage: claude-research.sh \"Your research query\""
    exit 1
fi

# Copy prompt to clipboard (no permissions needed)
echo -n "$1" | pbcopy

# Launch the compiled app (has its own accessibility permissions)
open "$SCRIPT_DIR/ClaudeResearch.app"
