#!/bin/bash
# Agent-optimized full verification runner
# Implements HumanLayer's "swallow success, show failure" pattern
#
# Usage:
#   ./hack/verify-agent.sh           # Run lint + typecheck + tests
#   VERBOSE=1 ./hack/verify-agent.sh # Show full output

set -e

# Source the run_silent helpers
source "$(dirname "$0")/run_silent.sh"

# Run lint (ruff check + format)
run_silent "Ruff check" "uv run ruff check src/ tests/"
run_silent "Ruff format" "uv run ruff format --check src/ tests/"

# Run typecheck
run_silent "Typecheck" "uv run basedpyright src/"

# Run tests (agent-optimized flags)
PYTEST_AGENT_FLAGS="-x --tb=short -q --no-header --no-cov"
run_silent_with_test_count "Tests" "uv run pytest $PYTEST_AGENT_FLAGS" "pytest"
