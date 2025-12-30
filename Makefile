# Makefile for YouLab
# All commands use uv for dependency management

.PHONY: help setup lint lint-fix typecheck test test-agent check check-agent verify verify-agent coverage coverage-html clean

help:
	@echo "YouLab Development Commands"
	@echo ""
	@echo "  setup        Install dependencies and configure dev environment"
	@echo "  lint         Run ruff linter (check mode)"
	@echo "  lint-fix     Run ruff with auto-fix"
	@echo "  typecheck    Run basedpyright type checker"
	@echo "  test         Run pytest (with coverage)"
	@echo "  test-agent   Run tests with agent-optimized output"
	@echo "  check        Run lint + typecheck (no tests)"
	@echo "  check-agent  Run lint + typecheck (agent-optimized output)"
	@echo "  verify       Run lint + typecheck + tests (full verification)"
	@echo "  verify-agent Run full verification (agent-optimized output)"
	@echo "  coverage     Run tests with coverage report"
	@echo "  coverage-html Generate HTML coverage report"
	@echo "  clean        Remove cache directories"

setup:
	uv sync --all-extras
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install
	@echo ""
	@echo "Setup complete! Run 'make verify' to check everything works."

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:
	uv run basedpyright src/

test:
	uv run pytest

test-agent:
	@./hack/test-agent.sh

check: lint typecheck

check-agent:
	@./hack/check-agent.sh

verify: check test
	@echo ""
	@echo "All checks passed!"

verify-agent:
	@./hack/verify-agent.sh

coverage:
	uv run pytest --cov=src/letta_starter --cov-report=term-missing

coverage-html:
	uv run pytest --cov=src/letta_starter --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
