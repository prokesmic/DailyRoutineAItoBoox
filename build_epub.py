#!/usr/bin/env python3
"""build_epub.py selected.json

Builds out/AI_Daily_YYYY-MM-DD_HHMM.epub from selected.json using stdlib only.
Prints the output path on stdout.
"""

import json
import os
import sys
import zipfile
from datetime import datetime, timezone

CSS = """
body {
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 1em;
  line-height: 1.65;
  max-width: 680px;
  margin: 0 auto;
  padding: 1.2em 1.5em;
  color: #1a1a1a;
}
h1 { font-size: 1.75em; color: #0f3460; margin-bottom: 0.3em; }
h2 { font-size: 1.2em; color: #16213e; margin-top: 2em; }
.masthead { border-bottom: 2px solid #0f3460; padding-bottom: 0.5em; margin-bottom: 1.5em; }
.date { font-size: 0.85em; color: #555; margin-top: 0.2em; }
.editor-note {
  background: #f4f6fb;
  border-left: 4px solid #0f3460;
  padding: 1em 1.2em;
  margin-bottom: 2em;
  font-size: 0.97em;
}
.article-source { font-size: 0.82em; color: #555; margin-bottom: 0.4em; }
.article-url   { font-size: 0.78em; color: #0066cc; word-break: break-all; }
.blurb { font-style: italic; margin-top: 0.6em; color: #333; }
hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
"""

MIMETYPE = "application/epub+zip"

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def _page(title: str, body_html: str) -> str:
    return (
        '<?xml version=\'1.0\' encoding=\'utf-8\'?>'
        '<!DOCTYPE html>'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        f'<head><title>{_esc(title)}</title>'
        '<link href="../Styles/main.css" rel="stylesheet" type="text/css"/>'
        '</head>'
        f'<body>{body_html}</body></html>'
    )


def build(selected_path: str) -> str:
    with open(selected_path) as f:
        data = json.load(f)

    editor_note: str = data.get("editor_note", "")
    picks: list = data.get("picks", [])

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")
    ts_str = now.strftime("%Y-%m-%d_%H%M")
    uid = f"ai-daily-{ts_str}"
    filename = f"AI_Daily_{ts_str}.epub"

    os.makedirs("out", exist_ok=True)
    output_path = os.path.join("out", filename)

    # Build in-memory file list: [(epub_path, content_str)]
    files: list[tuple[str, str]] = []

    # ── Note page ─────────────────────────────────────────────────────────
    note_paras = "".join(
        f"<p>{_esc(p.strip())}</p>"
        for p in editor_note.split("\n\n") if p.strip()
    )
    note_body = (
        f'<div class="masthead"><h1>AI Daily</h1>'
        f'<div class="date">{_esc(date_str)}</div></div>'
        f'<div class="editor-note">{note_paras}</div>'
    )
    files.append(("OEBPS/Text/note.xhtml", _page("Editor's Note", note_body)))

    # ── Article pages ─────────────────────────────────────────────────────
    for i, pick in enumerate(picks, 1):
        title  = pick.get("title", f"Article {i}")
        source = pick.get("source", "")
        url    = pick.get("url", "")
        blurb  = pick.get("blurb", "")
        art_body = (
            f"<h1>{_esc(title)}</h1>"
            f'<p class="article-source">{_esc(source)}</p>'
            f'<p class="article-url"><a href="{_esc(url)}">{_esc(url)}</a></p>'
            "<hr/>"
            f'<p class="blurb">{_esc(blurb)}</p>'
        )
        files.append((f"OEBPS/Text/art{i:02d}.xhtml", _page(title, art_body)))

    # ── OPF manifest ──────────────────────────────────────────────────────
    manifest_items = [
        '<item id="css" href="Styles/main.css" media-type="text/css"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="note" href="Text/note.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine_items = ['<itemref idref="note"/>']
    ncx_nav_points = [
        '<navPoint id="note" playOrder="1">'
        '<navLabel><text>Editor\'s Note</text></navLabel>'
        '<content src="Text/note.xhtml"/>'
        '</navPoint>'
    ]

    for i, pick in enumerate(picks, 1):
        iid = f"art{i:02d}"
        href = f"Text/art{i:02d}.xhtml"
        title = _esc(pick.get("title", f"Article {i}"))
        manifest_items.append(
            f'<item id="{iid}" href="{href}" media-type="application/xhtml+xml"/>'
        )
        spine_items.append(f'<itemref idref="{iid}"/>')
        ncx_nav_points.append(
            f'<navPoint id="{iid}" playOrder="{i + 1}">'
            f'<navLabel><text>{title}</text></navLabel>'
            f'<content src="{href}"/>'
            f'</navPoint>'
        )

    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
        f'unique-identifier="uid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="uid">{uid}</dc:identifier>'
        f'<dc:title>AI Daily — {_esc(date_str)}</dc:title>'
        '<dc:language>en</dc:language>'
        '<dc:creator>AI Reader Pipeline</dc:creator>'
        '</metadata>'
        '<manifest>'
        + "".join(manifest_items)
        + '</manifest>'
        '<spine toc="ncx">'
        + "".join(spine_items)
        + '</spine>'
        '</package>'
    )

    ncx = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
        '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f'<head><meta name="dtb:uid" content="{uid}"/></head>'
        f'<docTitle><text>AI Daily — {_esc(date_str)}</text></docTitle>'
        '<navMap>'
        + "".join(ncx_nav_points)
        + '</navMap></ncx>'
    )

    # ── Write epub (ZIP) ──────────────────────────────────────────────────
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            MIMETYPE,
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        zf.writestr("OEBPS/Styles/main.css", CSS)
        for epub_path, content in files:
            zf.writestr(epub_path, content)

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: build_epub.py selected.json", file=sys.stderr)
        sys.exit(1)
    path = build(sys.argv[1])
    print(path)


if __name__ == "__main__":
    main()
