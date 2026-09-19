#!/usr/bin/env python3
"""Local AI Daily Reader pipeline. Runs on the Mac mini via launchd.
Replaces the claude.ai/code/routines version with a self-contained script
that calls the Anthropic API directly for curation + citation extraction.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def _load_env():
    """Read .env file alongside this script (KEY=value lines). Skips comments."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env()

import httpx  # noqa: E402
import yaml  # noqa: E402
from anthropic import Anthropic  # noqa: E402

PRAGUE = ZoneInfo("Europe/Prague")
CITATION_SOURCES = {
    "Ethan Mollick",
    "Andrej Karpathy",
    "Everyday AI",
    "Latent Space",
    "Zvi Mowshowitz",
    "Pragmatic Engineer",
}

READWISE_TOKEN = os.environ.get("READWISE_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("AIDAILY_MODEL", "claude-sonnet-4-6")

if not READWISE_TOKEN or not ANTHROPIC_API_KEY:
    print("ERROR: READWISE_TOKEN and ANTHROPIC_API_KEY must be set (see .env)", file=sys.stderr)
    sys.exit(1)

client = Anthropic(api_key=ANTHROPIC_API_KEY)
READWISE_HEADERS = {"Authorization": f"Token {READWISE_TOKEN}"}
SAVE_URL = "https://readwise.io/api/v3/save/"
LIST_URL = "https://readwise.io/api/v3/list/"
DELETE_URL = "https://readwise.io/api/v3/delete/"
FETCH_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}


def log(msg):
    ts = datetime.now(PRAGUE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _strip_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def cleanup_expired():
    """Delete Reader items tagged 'AI Daily' older than 14 days. Idempotent."""
    log("Cleanup: listing Reader docs")
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    docs = []
    cursor = None
    with httpx.Client(timeout=30, headers=READWISE_HEADERS) as c:
        while True:
            params = {"pageCursor": cursor} if cursor else {}
            r = c.get(LIST_URL, params=params)
            if r.status_code != 200:
                log(f"  list error {r.status_code}: {r.text[:200]}")
                return 0
            data = r.json()
            docs.extend(data.get("results", []))
            cursor = data.get("nextPageCursor")
            if not cursor:
                break
            time.sleep(0.3)

    to_delete = []
    for d in docs:
        tags = d.get("tags") or {}
        if isinstance(tags, dict):
            names = list(tags.keys())
        elif isinstance(tags, list):
            names = [t.get("name") if isinstance(t, dict) else t for t in tags]
        else:
            names = []
        if not any(str(t).lower() == "ai daily" for t in names):
            continue
        created_str = d.get("created_at") or d.get("updated_at")
        if not created_str:
            continue
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created < cutoff:
            to_delete.append(d["id"])

    log(f"  {len(to_delete)} expired items to delete")
    deleted = 0
    with httpx.Client(timeout=30, headers=READWISE_HEADERS) as c:
        for doc_id in to_delete:
            r = c.delete(f"{DELETE_URL}{doc_id}/")
            if r.status_code in (200, 204):
                deleted += 1
            else:
                log(f"  delete {doc_id} -> {r.status_code}")
            time.sleep(0.35)
    log(f"  deleted {deleted}")
    return deleted


def fetch_candidates():
    log("Fetch: running fetch.py")
    result = subprocess.run(
        [sys.executable, str(ROOT / "fetch.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        log(f"  fetch.py failed: {result.stderr[:500]}")
        sys.exit(1)
    candidates = json.loads(result.stdout)
    log(f"  {len(candidates)} candidates")
    return candidates


CURATION_SYSTEM = """You are curating an AI daily reader for a senior pharma IT exec leading the AI strategic pillar in Prague. He listens to Latent Space, The AI Daily Brief, Everyday AI, and reads Ethan Mollick, Andrej Karpathy, Zvi Mowshowitz, Pragmatic Engineer, Stratechery.

Score each candidate 0-10 on novelty (0.25), depth/rigor (0.25), relevance to profile (0.30), signal-vs-hype (0.20). Apply the candidate's `weight` as a multiplier (clamp 0.8-1.2).

Cite-worthiness signals (score higher when these apply):
- Money attached (funding, hyperscaler deal, capex/opex, restructured contract)
- Frontier-lab primary source (OpenAI/Anthropic/DeepMind/Mistral/Meta/Microsoft/NVIDIA first-party)
- Concrete enterprise/government deployment (named org, named scope, adoption metrics)
- Strategic-shift framing (not release notes)
- Builder write-up with numbers (token economics, latency, cost, eval scores, adoption %)
- Reproducible method with weights/code/dataset, or benchmark exposing real failure mode
- Regulator/executive/workforce action with name and date
- AI-for-science with pharma-adjacent angle (HIGH priority)
- Author from Mollick/Karpathy/Zvi/Pragmatic Engineer/Latent Space/Everyday AI (+0.5 implicit bonus)
- Executive/management thinking (named CEO/CTO/founder writing or interviewed on AI strategy, org design)
- Viral-thread coverage (second-hand reporting on consequential X threads, research-team announcements, open-source releases)

Down-rank: consumer reviews, vendor PR with no new claim, generic 'AI is changing X' pieces, beginner explainers, crypto crossover.

Pick up to 12 candidates with weighted score >= 5.0. If fewer than 5 qualify, take all that do. At higher volumes aim for spread across clusters: frontier model moves, enterprise deployment, capital flows/compute, agentic systems, governance/workforce, AI-for-science, builder methodology, executive/management.

For each pick write a single sentence (max 25 words) explaining why it matters.

Write a 120-200 word editor's note connecting the picks. Direct, peer-to-peer, no throat-clearing. Lead with the strongest strategic thread.

Return ONLY valid JSON in this exact shape, no preamble or markdown:
{
  "editor_note": "...",
  "picks": [
    {"url": "...", "title": "...", "source": "...", "blurb": "..."}
  ]
}"""


def score_and_pick(candidates):
    log("Curation: calling Claude API")
    profile = (ROOT / "profile.md").read_text()
    user = (
        "## Reader profile\n"
        + profile
        + "\n\n## Candidates\n"
        + json.dumps(candidates, ensure_ascii=False, indent=2)
        + "\n\nReturn the curated selection as JSON per the schema in the system prompt."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=CURATION_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = _strip_fences(response.content[0].text)
    selected = json.loads(text)
    log(f"  picked {len(selected['picks'])} articles")
    return selected


def build_brief_html(selected):
    now = datetime.now(PRAGUE)
    title = f"AI Daily — {now.strftime('%a, %-d %B %Y %H:%M')} (Prague)"
    paras = "".join(
        f"<p>{esc(p.strip())}</p>"
        for p in selected["editor_note"].split("\n\n")
        if p.strip()
    )
    picks_html = ""
    for i, p in enumerate(selected["picks"], 1):
        suffix = " · citations to follow" if p["source"] in CITATION_SOURCES else ""
        picks_html += (
            f'<h3>{i}. {esc(p["title"])}</h3>'
            f'<div class="meta">{esc(p["source"])}{suffix}</div>'
            f'<p class="blurb">{esc(p["blurb"])}</p>'
            f'<p><a href="{esc(p["url"])}">Read source →</a></p>'
        )
    return (
        '<html><head><meta charset="utf-8"><title>' + esc(title) + '</title>'
        '<style>body{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}'
        'h1{font-size:1.6em} h3{margin:1.5em 0 .2em;font-size:1.1em}'
        '.meta{color:#666;font-size:.9em;font-style:italic}'
        '.blurb{color:#333;margin:.3em 0 .5em}'
        '.editor{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}'
        'a{color:#000}</style></head><body>'
        f'<h1>{esc(title)}</h1>'
        f'<div class="editor">{paras}</div><hr/>'
        f'{picks_html}'
        '</body></html>'
    )


def reader_save(payload):
    with httpx.Client(timeout=30, headers=READWISE_HEADERS) as c:
        r = c.post(SAVE_URL, json=payload)
        try:
            return r.status_code, r.json()
        except json.JSONDecodeError:
            return r.status_code, {}


def save_brief(brief_html, slug):
    log("Save brief")
    title = f"AI Daily — {datetime.now(PRAGUE).strftime('%a, %-d %B %Y %H:%M')}"
    payload = {
        "url": f"https://aidaily.local/briefs/{slug}.html",
        "html": brief_html,
        "title": title,
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "saved_using": "AI Daily routine",
    }
    code, body = reader_save(payload)
    if code not in (200, 201):
        log(f"  brief save FAILED: HTTP {code} {body}")
        sys.exit(1)
    log("  brief saved")


def save_picks(picks):
    log("Save picks")
    saved = []
    for p in picks:
        payload = {
            "url": p["url"],
            "title": p["title"],
            "summary": p["blurb"],
            "tags": ["AI Daily", p["source"]],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        }
        code, _ = reader_save(payload)
        if code in (200, 201):
            saved.append(p["url"])
        else:
            log(f"  failed {p['url']}: HTTP {code}")
        time.sleep(0.2)
    log(f"  saved {len(saved)}/{len(picks)}")
    return saved


CITATION_PROMPT_TEMPLATE = """From the article body below, identify the 2-4 most substantive externally-cited items: arXiv links, GitHub repos with research/academic orientation, named research papers, exec memos, or blog posts the author references substantively.

SKIP: social-media links (twitter/x.com, linkedin profiles, threads, mastodon), the source site's own related-content/navigation links, footnote ornaments, image embeds, podcast platform links, sponsor/affiliate links.

Article title: {title}
Article source: {source}

Article body:
{body}

Return ONLY JSON, no preamble or markdown:
{{"citations": [{{"url": "...", "title": "short descriptive title"}}]}}"""


def extract_citations(picks, seen):
    log("Citations: mining picks from citation-source feeds")
    saved_urls = []
    targets = [p for p in picks if p["source"] in CITATION_SOURCES]
    log(f"  {len(targets)} citation-source picks")
    for pick in targets:
        try:
            with httpx.Client(timeout=20, follow_redirects=True, headers=FETCH_UA) as c:
                body = c.get(pick["url"]).text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            log(f"  fetch failed {pick['url']}: {type(e).__name__}")
            continue
        prompt = CITATION_PROMPT_TEMPLATE.format(
            title=pick["title"], source=pick["source"], body=body[:30000]
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = _strip_fences(response.content[0].text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log(f"  parse failed for {pick['title'][:50]}: {e}")
            continue
        for cite in data.get("citations", []):
            url = (cite.get("url") or "").strip()
            if not url or url in seen:
                continue
            payload = {
                "url": url,
                "title": cite.get("title") or url[:80],
                "summary": f"Cited in '{pick['title']}' by {pick['source']}",
                "tags": ["AI Daily", f"Cited from {pick['source']}"],
                "location": "new",
                "category": "article",
                "saved_using": "AI Daily routine",
            }
            code, _ = reader_save(payload)
            if code in (200, 201):
                saved_urls.append(url)
                seen.add(url)
            time.sleep(0.2)
    log(f"  saved {len(saved_urls)} citations")
    return saved_urls


def update_seen(new_urls):
    log("Update seen.json")
    path = ROOT / "seen.json"
    try:
        existing = json.loads(path.read_text()) if path.exists() else []
    except json.JSONDecodeError:
        existing = []
    now_iso = datetime.now(timezone.utc).isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    rows = list(existing) + [{"url": u, "shipped_at": now_iso} for u in new_urls]
    by_url = {}
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["shipped_at"].replace("Z", "+00:00"))
        except (ValueError, KeyError, AttributeError):
            continue
        if ts < cutoff:
            continue
        prev = by_url.get(row["url"])
        if not prev or ts > datetime.fromisoformat(prev["shipped_at"].replace("Z", "+00:00")):
            by_url[row["url"]] = row
    seen_sorted = sorted(by_url.values(), key=lambda r: r["shipped_at"], reverse=True)
    path.write_text(json.dumps(seen_sorted, indent=2))
    log(f"  {len(seen_sorted)} entries in ledger")


def main():
    log(f"=== AI Daily Reader @ {datetime.now(PRAGUE).strftime('%Y-%m-%d %H:%M %Z')} ===")
    cleanup_expired()
    candidates = fetch_candidates()
    if len(candidates) == 0:
        log("No new candidates. Done.")
        return
    selected = score_and_pick(candidates)
    if len(selected["picks"]) < 3:
        log(f"Only {len(selected['picks'])} picks qualified; not shipping.")
        return

    slug = f"AI_Daily_{datetime.now(PRAGUE).strftime('%Y-%m-%d_%H%M')}"
    brief_html = build_brief_html(selected)
    (ROOT / "briefs").mkdir(exist_ok=True)
    (ROOT / "briefs" / f"{slug}.html").write_text(brief_html)

    save_brief(brief_html, slug)
    saved_pick_urls = save_picks(selected["picks"])

    try:
        seen = {row["url"] for row in json.loads((ROOT / "seen.json").read_text())}
    except (FileNotFoundError, json.JSONDecodeError):
        seen = set()
    seen.update(saved_pick_urls)

    saved_pick_objs = [p for p in selected["picks"] if p["url"] in saved_pick_urls]
    citation_urls = extract_citations(saved_pick_objs, seen)

    update_seen(saved_pick_urls + citation_urls)
    log(f"=== Done. {len(saved_pick_urls)} articles + {len(citation_urls)} citations + 1 brief. ===")


if __name__ == "__main__":
    main()
