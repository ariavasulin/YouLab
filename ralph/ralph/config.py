"""Configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Ralph configuration."""

    # OpenRouter for model flexibility
    openrouter_api_key: str = ""  # Default empty for testing
    openrouter_model: str = "anthropic/claude-sonnet-4-20250514"

    # Honcho
    honcho_workspace_id: str = "ralph"
    honcho_environment: str = "demo"  # demo, local, production
    honcho_api_key: str | None = None

    # Workspace paths
    user_data_dir: str = "/data/ralph/users"
    conversations_dir: str = "/data/ralph/conversations"

    # Docker sandbox
    sandbox_base_image: str = "nikolaik/python-nodejs:python3.12-nodejs22"
    sandbox_timeout: int = 300  # 5 minutes
    use_docker_sandbox: bool = False
    sandbox_port_base: int = 9000

    model_config = {"env_prefix": "RALPH_"}


@lru_cache
def get_settings() -> Settings:
    """Get settings singleton. Allows override in tests."""
    return Settings()


# For convenience, but prefer get_settings() for testability
settings = get_settings()
