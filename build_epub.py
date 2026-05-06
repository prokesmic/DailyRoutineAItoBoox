#!/usr/bin/env python3
"""
build_epub.py — build an ePub digest from selected.json.
Usage: python build_epub.py selected.json
Output: prints path to out/AI_Daily_YYYY-MM-DD_HHMM.epub
"""
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from ebooklib import epub

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIDaily/1.0; +https://github.com/prokesmic/DailyRoutineAItoBoox)"}
FETCH_TIMEOUT = 12


def fetch_article_body(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove nav, footer, script, style noise
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        for el in ["article", "main", '[role="main"]']:
            found = soup.select_one(el)
            if found:
                return str(found)[:30000]
        body = soup.find("body")
        return str(body)[:15000] if body else ""
    except Exception as e:
        return f"<p><em>Could not fetch content: {e}</em></p>"


def sanitize(html_str):
    """Keep only safe inline/block tags for epub; always returns non-empty xhtml."""
    if not html_str or not html_str.strip():
        return "<p><em>Content not available — read online via the link above.</em></p>"
    allowed = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
               "a", "strong", "em", "b", "i", "blockquote", "pre", "code",
               "img", "figure", "figcaption", "hr", "br", "table", "tr", "td", "th"}
    soup = BeautifulSoup(html_str, "lxml")
    for tag in soup.find_all(True):
        if tag.name not in allowed:
            tag.unwrap()
    result = str(soup).strip()
    if not result:
        return "<p><em>Content not available — read online via the link above.</em></p>"
    return result


def build_epub(selected_path: str) -> str:
    data = json.loads(Path(selected_path).read_text())
    editor_note = data.get("editor_note", "")
    picks = data.get("picks", [])

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%d_%H%M")
    book_title = f"AI Daily {now.strftime('%Y-%m-%d')}"

    book = epub.EpubBook()
    book.set_identifier(f"ai-daily-{ts}")
    book.set_title(book_title)
    book.set_language("en")
    book.add_author("AI Daily Reader")

    css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=b"""
body { font-family: Georgia, serif; margin: 2em; font-size: 1em; line-height: 1.6; }
h1 { font-size: 1.6em; margin-bottom: 0.3em; }
h2 { font-size: 1.3em; }
.meta { color: #555; font-size: 0.85em; margin-bottom: 1em; }
.blurb { font-style: italic; border-left: 3px solid #ccc; padding-left: 1em; margin-bottom: 1.2em; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
a { color: #1a6faf; }
""",
    )
    book.add_item(css)

    chapters = []

    # --- Editor's note ---
    note_ch = epub.EpubHtml(title="Editor's Note", file_name="note.xhtml", lang="en")
    note_ch.add_item(css)
    note_ch.content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Editor's Note</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h1>Editor's Note</h1>
<p class="meta">{now.strftime('%A, %d %B %Y')}</p>
<p>{editor_note}</p>
</body></html>"""
    book.add_item(note_ch)
    chapters.append(note_ch)

    # --- Article chapters ---
    for i, pick in enumerate(picks, 1):
        url = pick.get("url", "")
        pick_title = pick.get("title", f"Article {i}")
        source = pick.get("source", "")
        blurb = pick.get("blurb", "")

        print(f"  [{i}/{len(picks)}] Fetching: {url}", file=sys.stderr)
        body_html = fetch_article_body(url)
        safe_body = sanitize(body_html)

        ch = epub.EpubHtml(title=pick_title, file_name=f"article_{i:02d}.xhtml", lang="en")
        ch.add_item(css)
        safe_title = pick_title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        ch.content = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<!DOCTYPE html>"
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            f"<head><title>{safe_title}</title>"
            '<link rel="stylesheet" href="style.css"/></head>'
            "<body>"
            f"<h1>{safe_title}</h1>"
            f'<p class="meta"><strong>{source}</strong> · <a href="{url}">{url}</a></p>'
            f'<p class="blurb">{blurb}</p>'
            "<hr/>"
            f"{safe_body}"
            "</body></html>"
        )
        book.add_item(ch)
        chapters.append(ch)

    # TOC & spine
    book.toc = tuple(
        epub.Link(ch.file_name, ch.title, ch.file_name.replace(".xhtml", ""))
        for ch in chapters
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"AI_Daily_{ts}.epub"
    epub.write_epub(str(out_path), book, {"epub3_pages": False})
    print(str(out_path))
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_epub.py selected.json", file=sys.stderr)
        sys.exit(1)
    build_epub(sys.argv[1])
