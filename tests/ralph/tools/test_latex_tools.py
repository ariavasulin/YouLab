"""Tests for LaTeX templates and artifact compilation."""

from __future__ import annotations

from ralph.tools.latex_templates import (
    NOTES_TEMPLATE,
    PDF_VIEWER_TEMPLATE,
)


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
