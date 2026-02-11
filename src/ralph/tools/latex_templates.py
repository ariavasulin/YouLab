"""LaTeX and PDF viewer templates for note generation."""

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
