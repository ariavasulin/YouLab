#!/bin/bash
# Wrapper for launching Claude Desktop research
# Usage: ./hack/claude-research.sh "Your research query"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$1" ]; then
    echo "Usage: claude-research.sh \"Your research query\""
    exit 1
fi

osascript "$SCRIPT_DIR/launch-claude-research.applescript" "$1"
