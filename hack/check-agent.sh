#!/bin/bash
# Agent-optimized lint + typecheck runner
# Implements HumanLayer's "swallow success, show failure" pattern
#
# Usage:
#   ./hack/check-agent.sh           # Run lint + typecheck
#   VERBOSE=1 ./hack/check-agent.sh # Show full output

set -e

# Source the run_silent helpers
source "$(dirname "$0")/run_silent.sh"

# Run lint (ruff check + format)
run_silent "Ruff check" "uv run ruff check src/ tests/"
run_silent "Ruff format" "uv run ruff format --check src/ tests/"

# Run typecheck
run_silent "Typecheck" "uv run basedpyright src/"
