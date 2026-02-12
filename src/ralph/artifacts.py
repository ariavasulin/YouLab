"""Artifact compilation and push to OpenWebUI."""

from __future__ import annotations

import base64
import subprocess
from typing import TYPE_CHECKING

import httpx
import structlog

from ralph.config import get_settings
from ralph.tools.latex_templates import PDF_VIEWER_TEMPLATE

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger()


async def compile_and_push(
    tex_path: Path,
    user_id: str,
    chat_id: str | None = None,
) -> str:
    """
    Compile a .tex file to PDF and push the viewer to OpenWebUI's artifact panel.

    Args:
        tex_path: Absolute path to the .tex file in the user's workspace.
        user_id: OpenWebUI user ID for socket targeting.
        chat_id: Optional chat ID for scoping the artifact.

    Returns:
        Short status string suitable for tool output.

    """
    if not tex_path.exists():
        return f"Error: {tex_path.name} not found."

    if tex_path.suffix != ".tex":
        return f"Error: {tex_path.name} is not a .tex file."

    # Compile LaTeX → PDF
    pdf_bytes = _compile_latex(tex_path)
    if isinstance(pdf_bytes, str):
        # Push error to artifact panel so user sees it
        error_html = (
            '<html><body style="font-family: sans-serif; padding: 20px;">'
            '<h2 style="color: #dc3545;">Compilation Error</h2>'
            '<pre style="background: #f8f9fa; padding: 16px; border-radius: 8px;'
            f' overflow-x: auto;">{pdf_bytes}</pre>'
            "</body></html>"
        )
        await _push_artifact(user_id, error_html, chat_id=chat_id, title="Compilation Error")
        return pdf_bytes

    # Build HTML viewer
    title = tex_path.stem.replace("_", " ").replace("-", " ").title()
    html = _build_viewer(pdf_bytes, title)

    # Push to OpenWebUI
    await _push_artifact(user_id, html, chat_id=chat_id, title=title)

    page_estimate = len(pdf_bytes) // 5000 + 1
    return f"PDF compiled ({page_estimate} pages). Displayed in artifact panel."


def _compile_latex(tex_path: Path) -> bytes | str:
    """Compile .tex → PDF bytes. Returns error string on failure."""
    work_dir = tex_path.parent

    try:
        result = subprocess.run(  # noqa: S603
            ["tectonic", "-X", "compile", str(tex_path)],  # noqa: S607
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown compilation error"
            error_lines = [line for line in error_msg.split("\n") if "error" in line.lower()][:5]
            friendly = "\n".join(error_lines) if error_lines else error_msg[:500]
            return f"LaTeX compilation failed:\n```\n{friendly}\n```"

        pdf_path = tex_path.with_suffix(".pdf")
        if not pdf_path.exists():
            return "Compilation succeeded but PDF not found."

        return pdf_path.read_bytes()

    except FileNotFoundError:
        return "Tectonic compiler not installed."
    except subprocess.TimeoutExpired:
        return "Compilation timed out (>120s)."


def _build_viewer(pdf_bytes: bytes, title: str) -> str:
    """Build self-contained HTML PDF viewer."""
    pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    filename = f"{safe_title.strip()[:50] or 'notes'}.pdf"

    return PDF_VIEWER_TEMPLATE % {
        "title": title,
        "pdf_base64": pdf_base64,
        "filename": filename,
    }


async def _push_artifact(
    user_id: str,
    html: str,
    chat_id: str | None = None,
    title: str | None = None,
) -> None:
    """Push HTML content to OpenWebUI's artifact panel."""
    settings = get_settings()

    if not settings.openwebui_url or not settings.openwebui_api_key:
        logger.warning(
            "artifact_push_skipped", reason="RALPH_OPENWEBUI_URL or RALPH_OPENWEBUI_API_KEY not set"
        )
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.openwebui_url}/api/artifact/push",
            json={
                "user_id": user_id,
                "chat_id": chat_id,
                "content": html,
                "title": title,
            },
            headers={"Authorization": f"Bearer {settings.openwebui_api_key}"},
        )
        if not resp.is_success:
            logger.error("artifact_push_failed", status=resp.status_code, body=resp.text[:200])
        else:
            logger.info("artifact_pushed", user_id=user_id, title=title)
