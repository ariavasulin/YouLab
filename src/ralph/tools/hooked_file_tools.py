"""FileTools wrapper with post-write hooks for automatic LaTeX compilation."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

import structlog
from agno.tools.file import FileTools

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger()


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
        logger.info("save_file_called", file_name=file_name, is_tex=file_name.endswith(".tex"))
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
            logger.warning("tex_file_not_found_for_compile", path=str(tex_path))
            return

        logger.info("auto_compile_triggered", path=str(tex_path), user_id=self._user_id)

        # Run compile_and_push in a background thread with its own event loop.
        # Agno tool methods run synchronously, so there's typically no running
        # event loop we can schedule onto.
        thread = threading.Thread(
            target=self._compile_in_thread,
            args=(tex_path,),
            daemon=True,
        )
        thread.start()

    def _compile_in_thread(self, tex_path: Path) -> None:
        """Run async compilation in a new event loop on a background thread."""
        from ralph.artifacts import compile_and_push

        try:
            result = asyncio.run(compile_and_push(tex_path, self._user_id, self._chat_id))
            logger.info("auto_compile_result", path=str(tex_path), result=result)
        except Exception:
            logger.exception("auto_compile_failed", path=str(tex_path))
