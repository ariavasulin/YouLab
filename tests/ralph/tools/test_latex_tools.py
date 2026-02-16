"""Tests for LaTeX templates and artifact compilation."""

from __future__ import annotations

from ralph.tools.latex_templates import PDF_VIEWER_TEMPLATE


class TestTemplates:
    """Tests for LaTeX and HTML templates."""

    def test_viewer_template_has_viewer(self) -> None:
        """Test that PDF viewer has the main viewer element."""
        assert 'id="viewer"' in PDF_VIEWER_TEMPLATE

    def test_viewer_template_has_pdf_rendering(self) -> None:
        """Test that PDF viewer includes PDF.js rendering logic."""
        assert "pdfjsLib" in PDF_VIEWER_TEMPLATE
        assert "renderAllPages" in PDF_VIEWER_TEMPLATE
