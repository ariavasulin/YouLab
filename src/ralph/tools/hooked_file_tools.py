"""FileTools wrapper with post-write hooks for automatic LaTeX compilation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from agno.tools.file import FileTools

from ralph.artifacts import compile_and_push

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class HookedFileTools(FileTools):
    """
    FileTools with automatic LaTeX compilation on .tex file writes.

    Extends Agno's FileTools and overrides write operations. When a .tex file
    is written, automatically compiles it to PDF and pushes the viewer to
    the OpenWebUI artifact panel.
    """

    def __init__(
        self,
        base_dir: Path,
        user_id: str,
        chat_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._user_id = user_id
        self._chat_id = chat_id
        super().__init__(base_dir=base_dir, **kwargs)

    def save_file(
        self,
        contents: str,
        file_name: str,
        overwrite: bool = True,
        encoding: str = "utf-8",
    ) -> str:
        """Save file and trigger LaTeX compilation if .tex."""
        result = super().save_file(contents, file_name, overwrite=overwrite, encoding=encoding)
        if file_name.endswith(".tex") and not result.startswith("Error"):
            self._trigger_compile(file_name)
        return result

    def replace_file_chunk(
        self,
        file_name: str,
        start_line: int,
        end_line: int,
        chunk: str,
        encoding: str = "utf-8",
    ) -> str:
        """Replace file chunk and trigger LaTeX compilation if .tex."""
        result = super().replace_file_chunk(file_name, start_line, end_line, chunk, encoding=encoding)
        if file_name.endswith(".tex") and not result.startswith("Error"):
            self._trigger_compile(file_name)
        return result

    def _trigger_compile(self, file_name: str) -> None:
        """Trigger async compile_and_push from sync tool context."""
        from pathlib import Path

        tex_path = self.base_dir / file_name if not Path(file_name).is_absolute() else Path(file_name)

        if not tex_path.exists():
            logger.warning("tex_file_not_found_for_compile: path=%s", tex_path)
            return

        logger.info("auto_compile_triggered: path=%s user_id=%s", tex_path, self._user_id)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._compile_async(tex_path))  # noqa: RUF006
        except RuntimeError:
            logger.warning("no_event_loop_for_compile: path=%s", tex_path)

    async def _compile_async(self, tex_path: Path) -> None:
        """Async compilation wrapper with error handling."""
        try:
            result = await compile_and_push(tex_path, self._user_id, self._chat_id)
            logger.info("auto_compile_result: path=%s result=%s", tex_path, result)
        except Exception:
            logger.exception("auto_compile_failed: path=%s", tex_path)
