"""Exporting the notebook's saved content without executing any cells."""

from pathlib import Path

import nbformat
from nbconvert import HTMLExporter


root = Path(__file__).resolve().parents[3]
notebook_path = root / "Compulsory Assignments/notebooks/CA3.ipynb"
notebook = nbformat.read(notebook_path, as_version=4)
# Omitting empty input boxes from the export copy while keeping the notebook unchanged.
notebook.cells = [cell for cell in notebook.cells
                  if cell.cell_type != "code" or cell.source.strip() or cell.get("outputs")]
exporter = HTMLExporter(template_name="lab")
exporter.exclude_input_prompt = True
exporter.exclude_output_prompt = True
html, _ = exporter.from_notebook_node(notebook, resources={"metadata": {"name": "IND320 - CA3 - Elias Vinsrygg"}})

# Keeping code readable across pages and scaling saved figures/tables to A4.
style = """
<style>
@page { size: A4; margin: 16mm 14mm 18mm; }
html, body { background: white !important; color: #222 !important; }
body { margin: 0 !important; font-size: 10.5pt !important; }
main, .jp-Notebook { padding: 0 !important; margin: 0 !important; max-width: none !important; }
.jp-Cell { padding: 0 !important; margin: 0 0 9pt !important; }
.jp-Cell, .jp-Cell-inputWrapper, .jp-InputArea, .highlight { break-inside: auto !important; }
.jp-InputPrompt, .jp-OutputPrompt { display: none !important; }
.jp-InputArea, .jp-OutputArea-output { overflow: visible !important; max-height: none !important; }
.jp-RenderedHTMLCommon { font-size: 10.5pt !important; line-height: 1.45 !important; }
h1 { font-size: 21pt !important; } h2 { font-size: 16pt !important; } h3 { font-size: 12pt !important; }
h1, h2, h3 { break-after: avoid !important; }
p, li { orphans: 3; widows: 3; }
pre { white-space: pre-wrap !important; overflow-wrap: anywhere !important;
      font-size: 9.7pt !important; line-height: 1.35 !important; }
pre code, pre span { font-size: inherit !important; }
.jp-OutputArea-child { break-inside: avoid !important; }
img { max-width: 100% !important; height: auto !important; max-height: 220mm; object-fit: contain; }
table { max-width: 100% !important; font-size: 7.5pt !important; }
th, td { white-space: normal !important; overflow-wrap: anywhere; padding: 3px 4px !important; }
a { overflow-wrap: anywhere; }
</style>
"""
html = html.replace("</head>", style + "</head>")
(Path(__file__).parent / "CA3.html").write_text(html, encoding="utf-8")
print("Exported saved notebook content to HTML; no cells executed.")
