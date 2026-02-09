"""LaTeX compilation tools for producing PDF notes."""

from __future__ import annotations

import base64
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from agno.run import RunContext  # noqa: TC002
from agno.tools import Toolkit

logger = logging.getLogger(__name__)

# Professional LaTeX template for notes
# Note: %% is used for literal % in Python string formatting
NOTES_TEMPLATE = r"""
\documentclass[11pt,a4paper]{article}

%% Typography and fonts
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{microtype}

%% Math support
\usepackage{amsmath,amssymb,amsthm}

%% Better lists
\usepackage{enumitem}

%% Code listings
\usepackage{listings}
\lstset{
    basicstyle=\ttfamily\small,
    breaklines=true,
    frame=single,
    numbers=left,
    numberstyle=\tiny\color{gray}
}

%% Colors
\usepackage{xcolor}
\definecolor{sectioncolor}{RGB}{0,51,102}

%% Hyperlinks
\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    linkcolor=sectioncolor,
    urlcolor=blue
}

%% Page geometry
\usepackage[margin=1in]{geometry}

%% Headers/footers
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\rhead{\thepage}
\lhead{\leftmark}
\renewcommand{\headrulewidth}{0.4pt}

%% Section styling
\usepackage{titlesec}
\titleformat{\section}
    {\normalfont\Large\bfseries\color{sectioncolor}}
    {\thesection}{1em}{}
\titleformat{\subsection}
    {\normalfont\large\bfseries\color{sectioncolor}}
    {\thesubsection}{1em}{}

%% Theorem environments
\theoremstyle{definition}
\newtheorem{definition}{Definition}[section]
\newtheorem{example}{Example}[section]
\theoremstyle{plain}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{corollary}[theorem]{Corollary}
\theoremstyle{remark}
\newtheorem{remark}{Remark}[section]
\newtheorem{note}{Note}[section]

%% Title
\title{%(title)s}
\author{AI Tutor Notes}
\date{\today}

\begin{document}

\maketitle
\tableofcontents
\newpage

%(content)s

\end{document}
"""

# HTML template with embedded PDF.js viewer
# Uses legacy UMD build for broader iframe compatibility (no ES modules)
PDF_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>%(title)s</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #525659;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .toolbar {
            background: #323639;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            gap: 16px;
            color: white;
            flex-shrink: 0;
        }
        .toolbar button {
            background: #474a4d;
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .toolbar button:hover { background: #5a5d60; }
        .toolbar button:disabled { opacity: 0.5; cursor: not-allowed; }
        .page-info {
            font-size: 14px;
            min-width: 100px;
            text-align: center;
        }
        .zoom-controls { display: flex; align-items: center; gap: 8px; }
        .spacer { flex: 1; }
        .viewer {
            flex: 1;
            overflow: auto;
            display: flex;
            justify-content: center;
            padding: 20px;
        }
        #pdf-canvas {
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            background: white;
        }
        .download-btn {
            background: #0066cc !important;
        }
        .download-btn:hover { background: #0052a3 !important; }
        .error {
            color: #ff6b6b;
            padding: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="toolbar">
        <button id="prev" disabled>&larr; Prev</button>
        <span class="page-info"><span id="page-num">1</span> / <span id="page-count">-</span></span>
        <button id="next" disabled>Next &rarr;</button>
        <div class="zoom-controls">
            <button id="zoom-out">-</button>
            <span id="zoom-level">150%%</span>
            <button id="zoom-in">+</button>
        </div>
        <div class="spacer"></div>
        <button id="download" class="download-btn">Download PDF</button>
    </div>
    <div class="viewer">
        <canvas id="pdf-canvas"></canvas>
    </div>
    <script>
        // PDF data embedded as base64
        var pdfBase64 = '%(pdf_base64)s';

        // Decode base64 to binary
        var pdfData = atob(pdfBase64);
        var pdfBytes = new Uint8Array(pdfData.length);
        for (var i = 0; i < pdfData.length; i++) {
            pdfBytes[i] = pdfData.charCodeAt(i);
        }

        // Set worker source
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

        var pdfDoc = null;
        var pageNum = 1;
        var scale = 1.5;
        var canvas = document.getElementById('pdf-canvas');
        var ctx = canvas.getContext('2d');

        function renderPage(num) {
            pdfDoc.getPage(num).then(function(page) {
                var viewport = page.getViewport({ scale: scale });
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                page.render({ canvasContext: ctx, viewport: viewport }).promise.then(function() {
                    document.getElementById('page-num').textContent = num;
                    document.getElementById('prev').disabled = num <= 1;
                    document.getElementById('next').disabled = num >= pdfDoc.numPages;
                });
            });
        }

        function updateZoom() {
            document.getElementById('zoom-level').textContent = Math.round(scale * 100) + '%%';
            renderPage(pageNum);
        }

        // Load PDF
        pdfjsLib.getDocument({ data: pdfBytes }).promise.then(function(pdf) {
            pdfDoc = pdf;
            document.getElementById('page-count').textContent = pdf.numPages;
            renderPage(pageNum);
        }).catch(function(err) {
            document.querySelector('.viewer').innerHTML = '<div class="error">Error loading PDF: ' + err.message + '</div>';
        });

        // Navigation
        document.getElementById('prev').addEventListener('click', function() {
            if (pageNum > 1) { pageNum--; renderPage(pageNum); }
        });
        document.getElementById('next').addEventListener('click', function() {
            if (pageNum < pdfDoc.numPages) { pageNum++; renderPage(pageNum); }
        });

        // Zoom
        document.getElementById('zoom-in').addEventListener('click', function() {
            scale = Math.min(scale + 0.25, 3);
            updateZoom();
        });
        document.getElementById('zoom-out').addEventListener('click', function() {
            scale = Math.max(scale - 0.25, 0.5);
            updateZoom();
        });

        // Download
        document.getElementById('download').addEventListener('click', function() {
            var blob = new Blob([pdfBytes], { type: 'application/pdf' });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = '%(filename)s';
            a.click();
            URL.revokeObjectURL(url);
        });
    </script>
</body>
</html>"""


class LaTeXTools(Toolkit):
    """
    Tools for creating professional PDF notes from structured content.

    This toolkit allows the agent to produce textbook-quality PDF documents
    that appear in the OpenWebUI artifacts pane. Users never see LaTeX -
    they just get beautiful PDF notes.
    """

    def __init__(self, workspace: Path, **kwargs: Any) -> None:
        """
        Initialize LaTeX tools.

        Args:
            workspace: Path to user's workspace directory for temp files.
            **kwargs: Additional arguments passed to Toolkit base class.

        """
        self.workspace = workspace
        tools = [self.render_notes]
        super().__init__(name="latex_tools", tools=tools, **kwargs)

    def render_notes(
        self,
        run_context: RunContext,
        title: str,
        content: str,
    ) -> str:
        r"""
        Create professional PDF notes and display in the artifacts pane.

        Use this tool when the student asks for notes, summaries, or study
        materials on a topic. The content should be written in a LaTeX-friendly
        format with sections and mathematical notation where appropriate.

        Args:
            run_context: Agno run context (auto-injected).
            title: The title for the notes document.
            content: The notes content in LaTeX format. Use:
                - \section{Name} and \subsection{Name} for organization
                - $...$ for inline math (e.g., $x^2 + y^2 = r^2$)
                - $$...$$ or \[...\] for display math
                - \begin{itemize}/\begin{enumerate} for lists
                - \begin{definition}, \begin{theorem}, \begin{example} for formal statements
                - \textbf{} for bold, \textit{} for italic
                - \begin{lstlisting} for code blocks

        Returns:
            An HTML artifact containing the PDF viewer, or an error message
            if compilation fails.

        """
        logger.info("Rendering notes: %s", title)

        # Create temp directory for compilation
        with tempfile.TemporaryDirectory(prefix="latex_", dir=self.workspace) as tmpdir:
            tmppath = Path(tmpdir)
            tex_file = tmppath / "notes.tex"
            pdf_file = tmppath / "notes.pdf"

            # Generate LaTeX document
            latex_source = NOTES_TEMPLATE % {
                "title": self._escape_latex(title),
                "content": content,
            }
            tex_file.write_text(latex_source)

            # Compile with Tectonic (tectonic path is intentional, not user input)
            try:
                tectonic_cmd = ["tectonic", "-X", "compile", str(tex_file)]
                result = subprocess.run(tectonic_cmd,  # noqa: S603
                    cwd=tmppath,
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minute timeout
                    check=False,
                )

                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or "Unknown compilation error"
                    logger.warning("LaTeX compilation failed: %s", error_msg)
                    # Extract the most relevant error lines
                    error_lines = [
                        line
                        for line in error_msg.split("\n")
                        if "error" in line.lower() or "Error" in line
                    ][:5]
                    friendly_error = "\n".join(error_lines) if error_lines else error_msg[:500]
                    return f"I encountered an error creating the PDF notes:\n\n```\n{friendly_error}\n```\n\nLet me try a simpler format."

                if not pdf_file.exists():
                    return "PDF compilation succeeded but output file not found. This is unexpected."

            except FileNotFoundError:
                logger.error("Tectonic not found in PATH")
                return "The LaTeX compiler (Tectonic) is not installed. Please install it with: `cargo install tectonic` or via your package manager."
            except subprocess.TimeoutExpired:
                return "PDF compilation timed out. The document may be too complex."
            except Exception as e:
                logger.exception("Unexpected error during LaTeX compilation")
                return f"Unexpected error creating PDF: {e}"

            # Read and encode PDF
            pdf_bytes = pdf_file.read_bytes()
            pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

            # Generate safe filename
            safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
            safe_title = safe_title.strip()[:50] or "notes"
            filename = f"{safe_title}.pdf"

            # Generate HTML viewer
            html = PDF_VIEWER_TEMPLATE % {
                "title": title,
                "pdf_base64": pdf_base64,
                "filename": filename,
            }

            logger.info(
                "PDF generated: %d bytes, %d pages estimated", len(pdf_bytes), len(pdf_bytes) // 5000 + 1
            )

            # Return as HTML code block for artifact rendering
            # IMPORTANT: The HTML code block below must be included VERBATIM in your response
            # for the PDF to appear in the artifacts panel. Do not summarize or omit it.
            return f"""I've created your notes on **{title}**. The PDF viewer below will appear in the artifacts panel:

```html
{html}
```

You can navigate pages, zoom, and download the PDF using the controls above."""

    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters in plain text."""
        # Only escape in title, not in content (which should be LaTeX)
        replacements = [
            ("\\", r"\textbackslash{}"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("~", r"\textasciitilde{}"),
            ("^", r"\textasciicircum{}"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text
