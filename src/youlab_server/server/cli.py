"""CLI entry point for the HTTP service."""

import uvicorn

from youlab_server.config.settings import ServiceSettings


def main() -> None:
    """Run the HTTP service."""
    settings = ServiceSettings()
    uvicorn.run(
        "youlab_server.server.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
