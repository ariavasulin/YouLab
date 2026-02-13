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

    def test_viewer_template_has_viewer(self) -> None:
        """Test that PDF viewer has the main viewer element."""
        assert 'id="viewer"' in PDF_VIEWER_TEMPLATE

    def test_viewer_template_has_pdf_rendering(self) -> None:
        """Test that PDF viewer includes PDF.js rendering logic."""
        assert "pdfjsLib" in PDF_VIEWER_TEMPLATE
        assert "renderAllPages" in PDF_VIEWER_TEMPLATE
