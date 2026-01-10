"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    All settings can be overridden via environment variables.
    Example: LETTA_BASE_URL=http://localhost:8283
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Letta connection
    letta_base_url: str = Field(
        default="http://localhost:8283",
        description="URL of the Letta server",
    )
    letta_api_key: str | None = Field(
        default=None,
        description="API key for Letta server (if required)",
    )

    # LLM Configuration
    llm_provider: str = Field(
        default="openai",
        description="LLM provider: openai, anthropic, local",
    )
    llm_model: str = Field(
        default="gpt-4",
        description="Default LLM model to use",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )

    # Observability
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    log_json: bool = Field(
        default=True,
        description="Output logs as JSON (True for production)",
    )
    service_name: str = Field(
        default="letta-starter",
        description="Service name for logs and traces",
    )

    # Langfuse (optional LLM tracing)
    langfuse_enabled: bool = Field(
        default=False,
        description="Enable Langfuse LLM tracing",
    )
    langfuse_public_key: str | None = Field(
        default=None,
        description="Langfuse public key",
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        description="Langfuse secret key",
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse host URL",
    )

    # Memory settings
    core_memory_max_chars: int = Field(
        default=1500,
        description="Maximum characters per core memory block",
    )
    archival_rotation_threshold: float = Field(
        default=0.8,
        description="Rotate to archival when core memory exceeds this % of max",
    )

    # Agent defaults
    default_agent_name: str = Field(
        default="default",
        description="Default agent name",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


class ServiceSettings(BaseSettings):
    """Settings for the HTTP service."""

    model_config = SettingsConfigDict(
        env_prefix="YOULAB_SERVICE_",
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(
        default="127.0.0.1",
        description="Host to bind the service to",
    )
    port: int = Field(
        default=8100,
        description="Port to bind the service to",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for authentication",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Letta connection
    letta_base_url: str = Field(
        default="http://localhost:8283",
        description="URL of the Letta server",
    )

    langfuse_public_key: str | None = Field(
        default=None,
        description="Langfuse public key",
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        description="Langfuse secret key",
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse host URL",
    )
    langfuse_enabled: bool = Field(
        default=True,
        description="Enable Langfuse tracing",
    )

    # Honcho configuration
    honcho_enabled: bool = Field(
        default=True,
        description="Enable Honcho message persistence",
    )
    honcho_workspace_id: str = Field(
        default="youlab",
        description="Honcho workspace identifier",
    )
    honcho_api_key: str | None = Field(
        default=None,
        description="Honcho API key (required for production)",
    )
    honcho_environment: str = Field(
        default="demo",
        description="Honcho environment: demo, local, or production",
    )

    # File sync configuration (OpenWebUI → Letta)
    file_sync_enabled: bool = Field(
        default=False,
        description="Enable file sync from OpenWebUI to Letta",
    )
    openwebui_url: str = Field(
        default="http://localhost:3000",
        description="OpenWebUI base URL",
    )
    openwebui_api_key: str | None = Field(
        default=None,
        description="OpenWebUI API key for sync",
    )
    file_sync_interval: int = Field(
        default=30,
        description="Seconds between sync cycles",
    )
    file_sync_embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="Embedding model for Letta folders (must match agent)",
    )
    data_dir: str = Field(
        default=".data",
        description="Directory for persistent data (sync mappings, etc.)",
    )
