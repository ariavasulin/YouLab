# Makefile for YouLab
# All commands use uv for dependency management

.PHONY: help setup lint lint-fix typecheck test check verify clean

help:
	@echo "YouLab Development Commands"
	@echo ""
	@echo "  setup      Install dependencies and configure dev environment"
	@echo "  lint       Run ruff linter (check mode)"
	@echo "  lint-fix   Run ruff with auto-fix"
	@echo "  typecheck  Run mypy type checker"
	@echo "  test       Run pytest"
	@echo "  check      Run lint + typecheck (no tests)"
	@echo "  verify     Run lint + typecheck + tests (full verification)"
	@echo "  clean      Remove cache directories"

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
	uv run mypy src/

test:
	uv run pytest

check: lint typecheck

verify: check test
	@echo ""
	@echo "All checks passed!"

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
