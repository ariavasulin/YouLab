#!/bin/bash
# Agent-optimized test runner
# Implements HumanLayer's "swallow success, show failure" pattern
#
# Usage:
#   ./hack/test-agent.sh           # Run all tests
#   ./hack/test-agent.sh tests/    # Run specific path
#   VERBOSE=1 ./hack/test-agent.sh # Show full output

set -e

# Source the run_silent helpers
source "$(dirname "$0")/run_silent.sh"

# Agent-optimized pytest flags:
#   -x           Fail fast (stop on first failure)
#   --tb=short   Short traceback format
#   -q           Quiet mode (minimal output)
#   --no-header  No pytest header
#   --no-cov     Disable coverage (reduce noise)
PYTEST_AGENT_FLAGS="-x --tb=short -q --no-header --no-cov"

# Allow passing additional args (e.g., specific test path)
EXTRA_ARGS="${*:-}"

run_silent_with_test_count "Tests" "uv run pytest $PYTEST_AGENT_FLAGS $EXTRA_ARGS" "pytest"
