"""User management endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
import tomli_w
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from youlab_server.curriculum import curriculum
from youlab_server.storage.git import GitUserStorageManager

log = structlog.get_logger()
router = APIRouter(prefix="/users", tags=["users"])

# Dependency injection
_storage_manager: GitUserStorageManager | None = None


class CurrentUser(BaseModel):
    """Represents the authenticated user from request context."""

    id: str
    email: str | None = None
    name: str | None = None


async def get_current_user(request: Request) -> CurrentUser:
    """
    Extract current user from request headers.

    The frontend passes user info via X-User-Id header (set by OpenWebUI).
    Falls back to Bearer token extraction if needed.
    """
    # Try X-User-Id header first (simple approach for YouLab)
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return CurrentUser(
            id=user_id,
            email=request.headers.get("X-User-Email"),
            name=request.headers.get("X-User-Name"),
        )

    # Try Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # For now, use the token as user_id (OpenWebUI tokens encode user info)
        # In production, this should validate the JWT and extract user_id
        token = auth_header.replace("Bearer ", "")
        # Simple fallback: use token prefix as user_id (for development)
        # Real implementation would decode JWT
        uuid_length = 36  # Standard UUID format: 8-4-4-4-12
        return CurrentUser(id=token[:uuid_length] if len(token) >= uuid_length else token)

    raise HTTPException(status_code=401, detail="User authentication required")


def get_storage_manager() -> GitUserStorageManager:
    """Get the storage manager instance."""
    if _storage_manager is None:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    return _storage_manager


def set_storage_manager(manager: GitUserStorageManager) -> None:
    """Set the storage manager (called on startup)."""
    global _storage_manager
    _storage_manager = manager


class UserInitRequest(BaseModel):
    """Request body for user initialization."""

    user_id: str
    name: str | None = None
    email: str | None = None
    course_id: str = "college-essay"  # Default course


class UserInitResponse(BaseModel):
    """Response for user initialization."""

    user_id: str
    created: bool
    blocks_initialized: list[str]
    message: str


# Type alias for dependency injection
StorageDep = Annotated[GitUserStorageManager, Depends(get_storage_manager)]


@router.post("/init", response_model=UserInitResponse)
async def init_user(
    request: UserInitRequest,
    storage: StorageDep,
) -> UserInitResponse:
    """
    Initialize user storage and default memory blocks.

    This endpoint is called by OpenWebUI webhook on user signup.
    It is idempotent - calling multiple times is safe.
    """
    user_storage = storage.get(request.user_id)

    # Check if already initialized
    if user_storage.exists:
        log.info("user_already_initialized", user_id=request.user_id)
        return UserInitResponse(
            user_id=request.user_id,
            created=False,
            blocks_initialized=[],
            message="User already initialized",
        )

    # Initialize storage
    user_storage.init()

    # Get course configuration for default blocks
    course = curriculum.get(request.course_id)
    if course is None:
        # Fallback to default course
        course = curriculum.get("default")

    blocks_created: list[str] = []

    if course:
        # Create default blocks from course schema
        block_registry = curriculum.get_block_registry(request.course_id)

        for block_name, block_schema in course.blocks.items():
            model_class = block_registry.get(block_name) if block_registry else None
            if model_class is None:
                continue

            # Create instance with defaults
            overrides: dict[str, Any] = {}
            if block_schema.label == "human" and request.name:
                # Try to inject user name if block has a name-like field
                for field_name in ["name", "profile"]:
                    if field_name in model_class.model_fields:
                        overrides[field_name] = request.name
                        break

            try:
                instance = model_class(**overrides)
                # Serialize to TOML format
                toml_content = _block_to_toml(instance)
                user_storage.write_block(
                    label=block_name,
                    content=toml_content,
                    message=f"Initialize {block_name} block",
                    author="system",
                )
                blocks_created.append(block_name)
            except Exception as e:
                log.warning(
                    "block_init_failed",
                    user_id=request.user_id,
                    block=block_name,
                    error=str(e),
                )

    log.info(
        "user_initialized",
        user_id=request.user_id,
        blocks=blocks_created,
    )

    return UserInitResponse(
        user_id=request.user_id,
        created=True,
        blocks_initialized=blocks_created,
        message=f"Initialized {len(blocks_created)} memory blocks",
    )


def _block_to_toml(instance: Any) -> str:
    """Convert a block instance to TOML string."""
    # Get field values from instance
    data = {}
    for field_name in instance.model_fields:
        value = getattr(instance, field_name)
        if value is not None and value not in ("", []):
            data[field_name] = value

    return tomli_w.dumps(data)


@router.get("/{user_id}/exists")
async def user_exists(
    user_id: str,
    storage: StorageDep,
) -> dict[str, bool]:
    """Check if user storage exists."""
    return {"exists": storage.user_exists(user_id)}
