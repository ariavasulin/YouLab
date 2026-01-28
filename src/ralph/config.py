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

    # Agent workspace - where the agent operates (can be a shared codebase)
    agent_workspace: str | None = None  # If set, all users share this workspace

    # Docker sandbox
    sandbox_base_image: str = "nikolaik/python-nodejs:python3.12-nodejs22"
    sandbox_timeout: int = 300  # 5 minutes
    use_docker_sandbox: bool = False
    sandbox_port_base: int = 9000

    # Dolt database settings
    dolt_host: str = "localhost"
    dolt_port: int = 3307
    dolt_user: str = "root"
    dolt_password: str = "devpassword"  # noqa: S105 - dev default, overridden by env
    dolt_database: str = "youlab"

    @property
    def dolt_url(self) -> str:
        """SQLAlchemy async connection URL for Dolt."""
        return f"mysql+aiomysql://{self.dolt_user}:{self.dolt_password}@{self.dolt_host}:{self.dolt_port}/{self.dolt_database}"

    model_config = {"env_prefix": "RALPH_"}


@lru_cache
def get_settings() -> Settings:
    """Get settings singleton. Allows override in tests."""
    return Settings()


# For convenience, but prefer get_settings() for testability
settings = get_settings()
