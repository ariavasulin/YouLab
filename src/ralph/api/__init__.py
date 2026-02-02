"""Ralph API routers."""

from ralph.api.blocks import router as blocks_router
from ralph.api.notes_adapter import router as notes_router

__all__ = ["blocks_router", "notes_router"]
