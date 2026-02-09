"""Tests for LaTeXTools."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from ralph.tools.latex_tools import (
    NOTES_TEMPLATE,
    PDF_VIEWER_TEMPLATE,
    LaTeXTools,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_run_context() -> MagicMock:
    """Create a mock RunContext."""
    ctx = MagicMock()
    ctx.user_id = "test-user-123"
    return ctx


@pytest.fixture
def tools(tmp_path: Path) -> LaTeXTools:
    """Create LaTeXTools instance with temp workspace."""
    return LaTeXTools(workspace=tmp_path)


class TestLaTeXToolsInit:
    """Tests for LaTeXTools initialization."""

    def test_init_sets_workspace(self, tmp_path: Path) -> None:
        """Should set workspace path."""
        tools = LaTeXTools(workspace=tmp_path)
        assert tools.workspace == tmp_path

    def test_init_registers_render_notes(self, tmp_path: Path) -> None:
        """Should register render_notes tool."""
        tools = LaTeXTools(workspace=tmp_path)
        assert tools.name == "latex_tools"
        assert len(tools.functions) == 1
        assert "render_notes" in tools.functions


class TestEscapeLatex:
    """Tests for LaTeX escaping."""

    def test_escape_percent(self, tools: LaTeXTools) -> None:
        """Should escape percent sign."""
        assert tools._escape_latex("100%") == r"100\%"

    def test_escape_dollar(self, tools: LaTeXTools) -> None:
        """Should escape dollar sign."""
        assert tools._escape_latex("$50") == r"\$50"

    def test_escape_underscore(self, tools: LaTeXTools) -> None:
        """Should escape underscore."""
        assert tools._escape_latex("a_b") == r"a\_b"

    def test_escape_ampersand(self, tools: LaTeXTools) -> None:
        """Should escape ampersand."""
        assert tools._escape_latex("A & B") == r"A \& B"

    def test_escape_hash(self, tools: LaTeXTools) -> None:
        """Should escape hash."""
        assert tools._escape_latex("#1") == r"\#1"

    def test_escape_braces(self, tools: LaTeXTools) -> None:
        """Should escape curly braces."""
        assert tools._escape_latex("{test}") == r"\{test\}"


class TestTemplates:
    """Tests for LaTeX and HTML templates."""

    def test_template_has_required_packages(self) -> None:
        """Test that the LaTeX template includes necessary packages."""
        assert r"\usepackage{amsmath" in NOTES_TEMPLATE
        assert r"\usepackage{hyperref}" in NOTES_TEMPLATE
        assert r"\newtheorem{definition}" in NOTES_TEMPLATE

    def test_template_has_theorem_environments(self) -> None:
        """Test that the LaTeX template includes theorem environments."""
        assert r"\newtheorem{theorem}" in NOTES_TEMPLATE
        assert r"\newtheorem{lemma}" in NOTES_TEMPLATE
        assert r"\newtheorem{example}" in NOTES_TEMPLATE

    def test_viewer_template_has_navigation(self) -> None:
        """Test that PDF viewer has navigation controls."""
        assert 'id="prev"' in PDF_VIEWER_TEMPLATE
        assert 'id="next"' in PDF_VIEWER_TEMPLATE
        assert 'id="page-num"' in PDF_VIEWER_TEMPLATE
        assert 'id="page-count"' in PDF_VIEWER_TEMPLATE

    def test_viewer_template_has_zoom(self) -> None:
        """Test that PDF viewer has zoom controls."""
        assert 'id="zoom-in"' in PDF_VIEWER_TEMPLATE
        assert 'id="zoom-out"' in PDF_VIEWER_TEMPLATE
        assert 'id="zoom-level"' in PDF_VIEWER_TEMPLATE

    def test_viewer_template_has_download(self) -> None:
        """Test that PDF viewer has download button."""
        assert 'id="download"' in PDF_VIEWER_TEMPLATE
        assert "download-btn" in PDF_VIEWER_TEMPLATE


class TestRenderNotes:
    """Tests for render_notes tool."""

    def test_render_notes_tectonic_not_found(
        self, tools: LaTeXTools, mock_run_context: MagicMock
    ) -> None:
        """Should return error when Tectonic is not installed."""
        with patch("ralph.tools.latex_tools.subprocess.run", side_effect=FileNotFoundError):
            result = tools.render_notes(mock_run_context, "Test", "content")
            assert "not installed" in result.lower()

    def test_render_notes_timeout(
        self, tools: LaTeXTools, mock_run_context: MagicMock
    ) -> None:
        """Should return error on compilation timeout."""
        import subprocess

        with patch(
            "ralph.tools.latex_tools.subprocess.run",
            side_effect=subprocess.TimeoutExpired("tectonic", 120),
        ):
            result = tools.render_notes(mock_run_context, "Test", "content")
            assert "timed out" in result.lower()

    def test_render_notes_compilation_error(
        self, tools: LaTeXTools, mock_run_context: MagicMock
    ) -> None:
        """Should return friendly error on compilation failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "! Undefined control sequence.\nl.42 \\badcommand"
        mock_result.stdout = ""

        with patch("ralph.tools.latex_tools.subprocess.run", return_value=mock_result):
            result = tools.render_notes(mock_run_context, "Test", r"\badcommand")
            assert "error" in result.lower()
            assert "simpler format" in result.lower()

    def test_render_notes_success_returns_html(
        self, tools: LaTeXTools, mock_run_context: MagicMock, tmp_path: Path
    ) -> None:
        """Should return HTML artifact on successful compilation."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""

        # We need to mock the PDF file creation inside the temp directory
        # Since the actual temp dir is created inside the workspace, we'll
        # check the output format instead of the actual PDF creation
        with (
            patch("ralph.tools.latex_tools.subprocess.run", return_value=mock_result),
            patch("ralph.tools.latex_tools.tempfile.TemporaryDirectory") as mock_tmpdir,
        ):
            # Set up mock temp directory
            mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
            # Create a fake PDF file
            (tmp_path / "notes.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

            result = tools.render_notes(
                mock_run_context,
                "Test Title",
                r"\section{Introduction}\nTest content",
            )

            assert "```html" in result
            assert "Test Title" in result
            assert "</html>" in result

    def test_render_notes_safe_filename(
        self, tools: LaTeXTools, mock_run_context: MagicMock, tmp_path: Path
    ) -> None:
        """Should generate safe filename from title."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""

        with (
            patch("ralph.tools.latex_tools.subprocess.run", return_value=mock_result),
            patch("ralph.tools.latex_tools.tempfile.TemporaryDirectory") as mock_tmpdir,
        ):
            mock_tmpdir.return_value.__enter__.return_value = str(tmp_path)
            (tmp_path / "notes.pdf").write_bytes(b"%PDF-1.4 fake")

            result = tools.render_notes(
                mock_run_context,
                "Test: Special/Characters!",
                "content",
            )

            # The filename should have special chars replaced with underscore
            assert "Test_ Special_Characters_" in result or "Test__Special_Characters_" in result
