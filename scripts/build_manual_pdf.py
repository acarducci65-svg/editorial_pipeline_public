"""Build the printable manual with Playwright: uv run --extra dev --extra social python scripts/build_manual_pdf.py."""

from __future__ import annotations

import html
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "manuale_configurazione_e_uso.md"
OUTPUT = ROOT / "docs" / "manuale_configurazione_e_uso.pdf"


def inline(value: str) -> str:
    """Render the inline Markdown used by the manual, escaping source HTML."""
    parts = re.split(r"(`[^`]+`)", value)
    for i, part in enumerate(parts):
        if part.startswith("`") and part.endswith("`"):
            parts[i] = "<code>" + html.escape(part[1:-1]) + "</code>"
            continue
        part = html.escape(part)
        part = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', part)
        part = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", part)
        parts[i] = re.sub(r"(?<!\*)\*([^*]+)\*", r"<em>\1</em>", part)
    return "".join(parts)


def cells(line: str) -> list[str]:
    return [s.strip().replace(r"\|", "|") for s in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def markdown(source: str) -> str:
    """Convert the manual's headings, tables, lists, quotations and fenced code."""
    lines = source.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            anchor = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
            out.append(
                f'<h{level} id="{html.escape(anchor, quote=True)}">{inline(title)}</h{level}>'
            )
            i += 1
            continue
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and re.match(r"^\|[\s:|\-]+\|\s*$", lines[i + 1])
        ):
            rows = [cells(line)]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append(
                "<table><thead><tr>"
                + "".join("<th>" + inline(c) + "</th>" for c in rows[0])
                + "</tr></thead><tbody>"
            )
            for row in rows[1:]:
                out.append("<tr>" + "".join("<td>" + inline(c) + "</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
            continue
        if re.match(r"^\s*([-*] |\d+\. )", line):
            ordered = bool(re.match(r"^\s*\d+\. ", line))
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^\s*([-*] |\d+\. )", lines[i]):
                item = re.sub(r"^\s*([-*] |\d+\. )", "", lines[i])
                out.append("<li>" + inline(item) + "</li>")
                i += 1
            out.append(f"</{tag}>")
            continue
        if line.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(inline(lines[i].lstrip("> ")))
                i += 1
            out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
            continue
        if re.match(r"^\s*---+\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        paragraph = [line.strip()]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^(#{1,6} |```|\||>|\s*[-*] |\s*\d+\. |---+$)", lines[i])
        ):
            paragraph.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    return "\n".join(out)


CSS = """
@page { size: A4; }
* { box-sizing: border-box; }
body { font-family: Inter, 'Segoe UI', Helvetica, Arial, sans-serif; color: #202a36; font-size: 9pt; line-height: 1.5; }
.cover { height: 240mm; display: flex; flex-direction: column; justify-content: center; border-top: 9px solid #18344b; page-break-after: always; }
.badge { align-self: flex-start; background: #dcece9; color: #165b54; padding: 6px 12px; font-size: 9pt; font-weight: 700; letter-spacing: .12em; }
.cover h1 { font-size: 32pt; line-height: 1.1; color: #18344b; margin: 24px 0 10px; }
.cover p { color: #526a77; font-size: 14pt; max-width: 120mm; }
h1, h2, h3, h4 { color: #18344b; line-height: 1.22; break-after: avoid; }
h1 { font-size: 22pt; } h2 { font-size: 16pt; border-bottom: 1px solid #9ab8bb; padding-bottom: 5px; margin-top: 23px; } h3 { font-size: 12pt; margin-top: 18px; } h4 { font-size: 10pt; }
p, li { overflow-wrap: anywhere; } p { margin: 7px 0; } li { margin: 3px 0; } ul, ol { padding-left: 21px; }
a { color: #116b72; text-decoration: none; }
blockquote { margin: 12px 0; padding: 8px 14px; background: #edf5f3; border-left: 3px solid #368b82; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 8pt; break-inside: avoid; } thead { display: table-header-group; } tr { break-inside: avoid; } th, td { border: 1px solid #c5d1d5; padding: 5px 6px; vertical-align: top; overflow-wrap: anywhere; } th { background: #24465b; color: white; text-align: left; } tbody tr:nth-child(even) { background: #f0f5f5; }
pre { background: #1e2a36; color: #f3f6f8; border-radius: 4px; padding: 11px; white-space: pre-wrap; overflow-wrap: anywhere; font: 7.5pt/1.4 Consolas, monospace; break-inside: avoid; } code { font-family: Consolas, monospace; } :not(pre) > code { background: #eaf0f1; padding: 1px 3px; font-size: .93em; } hr { border: 0; border-top: 1px solid #d4dfe1; margin: 18px 0; }
"""


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    document = f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Editorial Pipeline — Manuale ufficiale</title><style>{CSS}</style></head><body><section class="cover"><span class="badge">EDITORIAL PIPELINE · OPEN SOURCE</span><h1>Manuale di<br>configurazione e uso</h1><p>Una guida pratica alla redazione aumentata e ai suoi controlli umani.</p><p>Versione 1.0.0 · Apache 2.0</p></section>{markdown(source)}</body></html>"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(document, wait_until="load")
            page.pdf(
                path=str(OUTPUT),
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"},
                display_header_footer=True,
                header_template="<span></span>",
                footer_template='<div style="width:100%;text-align:center;font:8px sans-serif;color:#687c86"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
            )
        finally:
            browser.close()
    print("Creato docs/manuale_configurazione_e_uso.pdf")


if __name__ == "__main__":
    main()
