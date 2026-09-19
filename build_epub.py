"""Read selected.json, extract bodies, build EPUB into out/."""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import httpx, trafilatura
from ebooklib import epub

CSS = """body{font-family:Georgia,serif;line-height:1.55}
h1{font-size:1.6em;margin:0 0 .3em} h2{font-size:1.25em;margin:1.2em 0 .4em}
.meta{color:#555;font-size:.85em;font-style:italic;font-family:Arial,sans-serif}
.blurb{color:#444;font-style:italic;margin:.4em 0 1em}
.editor-note{border-left:3px solid #888;padding:.2em 0 .2em 1em;margin:1.2em 0}
blockquote{border-left:3px solid #aaa;padding-left:1em;color:#333}
hr{border:none;border-top:1px solid #ccc;margin:1.5em 0} a{color:#000}"""

HEADERS = {"User-Agent": "Mozilla/5.0 AI-Daily-Reader"}

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def sanitize(h):
    h = re.sub(r"<script[^>]*>.*?</script>", "", h, flags=re.S|re.I)
    h = re.sub(r"<style[^>]*>.*?</style>", "", h, flags=re.S|re.I)
    return re.sub(r"\s(on\w+|style)=\"[^\"]*\"", "", h, flags=re.I)

def extract(url, fallback):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS) as c:
            raw = c.get(url).text
        body = trafilatura.extract(raw, output_format="html", include_links=True,
                                    include_tables=True, with_metadata=False)
        if not body or len(body) < 300:
            from readability import Document
            body = Document(raw).summary()
        return sanitize(body) if body and len(body) >= 300 else None
    except Exception as e:
        print(f"extract failed {url}: {e}", file=sys.stderr); return None

selected = json.load(open(sys.argv[1]))
today = datetime.now(timezone.utc)
title = f"AI Daily — {today:%a %-d %b %Y %H:%MZ}"
book = epub.EpubBook()
book.set_identifier(f"aidaily-{today:%Y%m%d-%H%M}"); book.set_title(title); book.set_language("en")
css = epub.EpubItem(uid="s", file_name="s.css", media_type="text/css", content=CSS)
book.add_item(css)

cover = epub.EpubHtml(title="Cover", file_name="cover.xhtml", lang="en")
cover.content = (f"<html><head><link rel='stylesheet' href='s.css'/></head><body>"
                 f"<div style='text-align:center'><h1 style='font-size:2.4em;font-weight:300'>AI Daily</h1>"
                 f"<div style='font-size:1.3em;color:#555'>{today:%A, %-d %B %Y}</div>"
                 f"<div style='color:#888;margin-top:3em'>{len(selected['picks'])} articles · curated by Claude</div>"
                 f"</div></body></html>")
cover.add_item(css); book.add_item(cover)

note = epub.EpubHtml(title="Editor's note", file_name="editor.xhtml", lang="en")
paras = "".join(f"<p>{esc(p.strip())}</p>" for p in selected["editor_note"].split("\n\n") if p.strip())
note.content = f"<html><head><link rel='stylesheet' href='s.css'/></head><body><h1>Editor's note</h1><div class='editor-note'>{paras}</div></body></html>"
note.add_item(css); book.add_item(note)

chapters = [note]
for i, p in enumerate(selected["picks"], 1):
    body = extract(p["url"], p["title"])
    if not body: continue
    chap = epub.EpubHtml(title=p["title"], file_name=f"a{i:02d}.xhtml", lang="en")
    wc = len(re.sub(r"<[^>]+>", " ", body).split())
    chap.content = (f"<html><head><link rel='stylesheet' href='s.css'/></head><body>"
                    f"<h1>{i}. {esc(p['title'])}</h1>"
                    f"<div class='meta'>{esc(p['source'])} · {max(1, round(wc/220))} min · "
                    f"<a href='{p['url']}'>source</a></div>"
                    f"<div class='blurb'>{esc(p['blurb'])}</div><hr/>{body}</body></html>")
    chap.add_item(css); book.add_item(chap); chapters.append(chap)

book.toc = tuple(chapters)
book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
book.spine = ["nav", cover] + chapters

out_dir = Path("out"); out_dir.mkdir(exist_ok=True)
out_path = out_dir / f"AI_Daily_{today:%Y-%m-%d_%H%M}.epub"
epub.write_epub(str(out_path), book)
print(str(out_path))
