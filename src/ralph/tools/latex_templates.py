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
# No toolbar — full-bleed continuous scroll, fit-to-width
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
        html, body { height: 100%%; overflow: hidden; }
        body { background: white; }
        #viewer {
            width: 100%%;
            height: 100%%;
            overflow-y: auto;
            overflow-x: hidden;
        }
        .page-canvas {
            display: block;
            width: 100%%;
        }
        .error {
            color: #ff6b6b;
            padding: 20px;
            text-align: center;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
    </style>
</head>
<body>
    <div id="viewer"></div>
    <script>
        var pdfBase64 = '%(pdf_base64)s';
        var pdfData = atob(pdfBase64);
        var pdfBytes = new Uint8Array(pdfData.length);
        for (var i = 0; i < pdfData.length; i++) {
            pdfBytes[i] = pdfData.charCodeAt(i);
        }

        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

        var pdfDoc = null;
        var rendering = false;
        var resizeTimer = null;
        var viewer = document.getElementById('viewer');

        function renderAllPages() {
            if (!pdfDoc || rendering) return;
            rendering = true;
            var scrollRatio = viewer.scrollHeight > 0 ? viewer.scrollTop / viewer.scrollHeight : 0;
            viewer.innerHTML = '';

            pdfDoc.getPage(1).then(function(firstPage) {
                var unscaledViewport = firstPage.getViewport({ scale: 1 });
                var scale = viewer.clientWidth / unscaledViewport.width;
                var dpr = window.devicePixelRatio || 1;

                var chain = Promise.resolve();
                for (var i = 1; i <= pdfDoc.numPages; i++) {
                    (function(pageNum) {
                        chain = chain.then(function() {
                            return pdfDoc.getPage(pageNum).then(function(page) {
                                var viewport = page.getViewport({ scale: scale * dpr });
                                var canvas = document.createElement('canvas');
                                canvas.className = 'page-canvas';
                                canvas.width = viewport.width;
                                canvas.height = viewport.height;
                                viewer.appendChild(canvas);
                                return page.render({
                                    canvasContext: canvas.getContext('2d'),
                                    viewport: viewport
                                }).promise;
                            });
                        });
                    })(i);
                }

                chain.then(function() {
                    rendering = false;
                    viewer.scrollTop = scrollRatio * viewer.scrollHeight;
                });
            });
        }

        pdfjsLib.getDocument({ data: pdfBytes }).promise.then(function(pdf) {
            pdfDoc = pdf;
            renderAllPages();
        }).catch(function(err) {
            viewer.innerHTML = '<div class="error">Error loading PDF: ' + err.message + '</div>';
        });

        new ResizeObserver(function() {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(renderAllPages, 150);
        }).observe(viewer);
    </script>
</body>
</html>"""
