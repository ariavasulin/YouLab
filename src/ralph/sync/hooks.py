"""Post-hooks for FileTools to trigger lazy sync."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from ralph.sync.service import get_knowledge_service, get_sync_client
from ralph.sync.workspace_sync import sync_file_to_kb

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from pathlib import Path
    from typing import Any

    from agno.tools.function import FunctionCall
    from agno.tools.toolkit import Toolkit

log = structlog.get_logger()

# Track background tasks to prevent GC
_background_tasks: set[asyncio.Task[None]] = set()


_main_loop: asyncio.AbstractEventLoop | None = None


def capture_event_loop() -> None:
    """Capture the main event loop. Call from async context during setup."""
    global _main_loop
    _main_loop = asyncio.get_running_loop()


def _fire_and_forget(coro: Coroutine[Any, Any, None]) -> None:
    """Schedule a coroutine as a background task on the main event loop."""
    # Try current thread's loop first, fall back to captured main loop.
    # Agno may run sync tool functions via asyncio.to_thread(), so
    # the post_hook can fire in a thread pool thread with no event loop.
    loop: asyncio.AbstractEventLoop | None = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = _main_loop

    if loop is None:
        log.warning("sync_hook_no_event_loop")
        return

    def _schedule() -> None:
        task = loop.create_task(coro)  # type: ignore[union-attr]
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    if loop.is_running():
        # If called from a different thread, use threadsafe scheduling
        try:
            asyncio.get_running_loop()
            # Same thread — schedule directly
            _schedule()
        except RuntimeError:
            # Different thread — use call_soon_threadsafe
            loop.call_soon_threadsafe(_schedule)
    else:
        log.warning("sync_hook_loop_not_running")
        return


def _make_sync_hook(workspace: Path, user_id: str):  # noqa: ANN202
    """Create a post_hook closure for file mutation tools."""

    def _on_file_mutated(fc: FunctionCall) -> None:
        log.info("sync_post_hook_called", tool=fc.function.name, error=fc.error, args=fc.arguments)

        # Skip if the tool call failed
        if fc.error:
            return

        # Extract file_name from arguments
        args = fc.arguments or {}
        file_name = args.get("file_name")
        if not file_name:
            log.info("sync_hook_no_file_name", args=args)
            return

        # Resolve full path
        file_path = (workspace / file_name).resolve()

        # Safety: ensure it's within workspace
        try:
            file_path.relative_to(workspace.resolve())
        except ValueError:
            log.warning("sync_hook_path_escape", file_name=file_name)
            return

        # Check sync is configured
        client = get_sync_client()
        knowledge = get_knowledge_service()
        if not client or not knowledge:
            return

        log.info("sync_hook_fired", tool=fc.function.name, file=file_name, user_id=user_id)
        _fire_and_forget(sync_file_to_kb(file_path, user_id, client, knowledge))

    return _on_file_mutated


def attach_sync_hooks(file_tools: Toolkit, workspace: Path, user_id: str) -> None:
    """
    Attach post_hooks to FileTools' mutating functions.

    Mutating functions: save_file, replace_file_chunk, delete_file.
    Modifies file_tools in place.
    """
    hook = _make_sync_hook(workspace, user_id)

    attached = []
    for func_name in ("save_file", "replace_file_chunk", "delete_file"):
        func = file_tools.functions.get(func_name)
        if func is not None:
            func.post_hook = hook
            attached.append(func_name)

    log.info("sync_hooks_attached", functions=attached, user_id=user_id, workspace=str(workspace))
