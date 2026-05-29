#!/usr/bin/env python3
"""Execute the AI Daily pipeline: score, brief, post to Readwise, update seen.json."""
import json, os, sys, time, re
from datetime import datetime, timezone, timedelta
import requests

READWISE_TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
BRANCH = "claude/intelligent-tesla-6Y4rZ"
REPO = "prokesmic/DailyRoutineAItoBoox"
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space",
                    "Zvi Mowshowitz", "Pragmatic Engineer"}

HEADERS = {"Authorization": f"Token {READWISE_TOKEN}", "Content-Type": "application/json"}

def rw_save(payload: dict) -> bool:
    r = requests.post("https://readwise.io/api/v3/save/", headers=HEADERS, json=payload, timeout=20)
    if r.status_code not in (200, 201):
        print(f"  WARN save failed {r.status_code}: {payload.get('url','')[:80]}", file=sys.stderr)
        return False
    return True

# ── picks (index into candidates.json, pre-scored) ──────────────────────────
PICKS_IDX = [40, 0, 57, 2, 3, 4, 1, 39, 56, 60, 68, 75]

BLURBS = {
    40: "Foundation model scaling is coming to proteins; Alex Rives' ESM work at BioHub is the biopharma AI development to track.",
    0:  "The largest AI capital raise in history ($965B Series H), paired with Opus 4.8 dynamic workflow tooling—Latent Space covers the full picture.",
    57: "Mollick argues we must actively choose which tasks stay human before defaults are set for us—essential framing for pharma AI governance.",
    2:  "Zvi's weekly roundup frames the conspicuous absence of a US executive order as a strategic signal compliance teams should log.",
    3:  "Engineering teams cutting AI tooling spend after unconstrained adoption—a real counter-trend with direct budget implications for IT leaders.",
    4:  "OpenAI and Rosalind Foundation deploy AI for biodefense threat detection—named production deployment with national-security scope.",
    1:  "How Cognition's team thinks about async long-horizon agents in production: the deepest available technical conversation on agentic architecture.",
    39: "Cognition raises $1B at $26B valuation; confirms agent-layer infrastructure is being priced as essential capital by top-tier funds.",
    56: "IBM Research's first benchmark for enterprise agentic IT tasks shows frontier models below 50%—a concrete data point for IT execs.",
    60: "Pragmatic Engineer's 2026 SE job market survey quantifies how AI is reshaping engineering hiring, compensation, and team structure.",
    68: "Clearest published framework for redesigning org structure around agentic AI systems rather than discrete model deployments.",
    75: "Large-scale unified deep learning for peptide mass spectrum interpretation—directly relevant to biopharma proteomics and drug discovery.",
}

EDITOR_NOTE = """\
<p>The week's central thread runs through Anthropic: a $965B Series H (the largest AI raise in history), Opus 4.8 with dynamic workflow tooling, and a locked SpaceX data-center lease—all in the same window. Paired with Cognition's $1B raise at $26B, capital markets are pricing agent infrastructure as critical infrastructure. The Latent Space piece on async agents at Cognition deepens that argument technically.</p>
<p>Two pieces demand pharma AI committee attention. Alex Rives at BioHub makes the case that the "bitter lesson" (scale wins) is coming to protein science—ESM's trajectory is the strategic signal for biopharma AI planning. The Nature Machine Intelligence peptide mass-spec model confirms it quietly: deep learning is commoditising proteomics interpretation at scale.</p>
<p>Three pieces form an enterprise reality check. Pragmatic Engineer surfaces a genuine counter-trend—engineering teams cutting AI tooling spend after unconstrained adoption. The ITBench-AA benchmark puts frontier models below 50% on agentic enterprise IT tasks. MIT Tech Review's org-design piece is the best available guide for structuring teams around agents, not models. Ethan Mollick's "Choosing to Stay Human" and Zvi's governance roundup frame the gap: no US executive order, no federal guidance on what to keep human. Your organisation needs to decide that without a rulebook.</p>"""

def build_html(picks, now_prague):
    ts = now_prague.strftime("%A, %-d %B %Y %H:%M")
    lines = [
        "<!DOCTYPE html>",
        '<html><head><meta charset="utf-8">',
        f"<title>AI Daily — {ts}</title>",
        "<style>body{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}",
        "h1{font-size:1.6em} h3{margin:1.5em 0 .2em;font-size:1.1em}",
        ".meta{color:#666;font-size:.9em;font-style:italic}",
        ".blurb{color:#333;margin:.3em 0 .5em}",
        ".editor{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}",
        "a{color:#000}</style></head><body>",
        f"<h1>AI Daily — {ts} (Prague)</h1>",
        f'<div class="editor">{EDITOR_NOTE}</div><hr/>',
    ]
    for i, pick in enumerate(picks, 1):
        source_note = " · citations to follow" if pick["source"] in CITATION_SOURCES else ""
        lines += [
            f"<h3>{i}. {pick['title']}</h3>",
            f'<div class="meta">{pick["source"]}{source_note}</div>',
            f'<p class="blurb">{pick["blurb"]}</p>',
            f'<p><a href="{pick["url"]}">Read source →</a></p>',
        ]
    lines.append("</body></html>")
    return "\n".join(lines)


def extract_citations_from_html(html_text: str, seen_urls: set) -> list:
    """Pull substantive external links from fetched HTML."""
    SKIP = re.compile(
        r"(twitter\.com|x\.com|threads\.net|mastodon|linkedin\.com/in|"
        r"instagram\.com|facebook\.com|tiktok\.com|youtube\.com/watch|"
        r"podcasts\.apple\.com|open\.spotify\.com|substack\.com/subscribe|"
        r"substack\.com/app|ghost\.io|feedburner|patreon\.com|"
        r"amzn\.|amazon\.|shop\.|store\.|utm_|#|javascript:)",
        re.I,
    )
    ACADEMIC = re.compile(
        r"(arxiv\.org|github\.com/[^/]+/[^/]+|nature\.com/articles|"
        r"science\.org/doi|biorxiv\.org|medrxiv\.org|openreview\.net|"
        r"papers\.ssrn\.com|semanticscholar\.org|dl\.acm\.org|"
        r"proceedings\.mlr\.press|huggingface\.co/(papers|datasets|models)|"
        r"research\.(google|microsoft|meta|anthropic)\.com|"
        r"deepmind\.google|openai\.com/research|"
        r"distill\.pub|lilianweng\.github\.io)",
        re.I,
    )
    links = re.findall(r'href=["\']?(https?://[^\s"\'<>]+)', html_text)
    seen_local = set()
    results = []
    for url in links:
        url = url.rstrip(".,;)'\"")
        if url in seen_urls or url in seen_local:
            continue
        if SKIP.search(url):
            continue
        if ACADEMIC.search(url):
            seen_local.add(url)
            results.append(url)
        if len(results) >= 4:
            break
    return results


def main():
    candidates = json.load(open("candidates.json"))
    seen_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
    seen_data = json.load(open(seen_path)) if os.path.exists(seen_path) else []
    seen_urls = {item["url"] for item in seen_data}

    # Prague time (CEST = UTC+2)
    prague_tz = timezone(timedelta(hours=2))
    now_utc = datetime.now(timezone.utc)
    now_prague = now_utc.astimezone(prague_tz)
    slug = "AI_Daily_" + now_prague.strftime("%Y-%m-%d_%H%M")

    picks = []
    for idx in PICKS_IDX:
        c = candidates[idx]
        c["blurb"] = BLURBS[idx]
        picks.append(c)

    # Build HTML brief
    html = build_html(picks, now_prague)
    os.makedirs("briefs", exist_ok=True)
    brief_path = f"briefs/{slug}.html"
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Brief saved: {brief_path}", file=sys.stderr)

    ts_display = now_prague.strftime("%A, %-d %B %Y %H:%M")
    brief_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/briefs/{slug}.html"

    # POST brief
    print("Posting brief …", file=sys.stderr)
    ok = rw_save({
        "url": brief_url,
        "html": html,
        "title": f"AI Daily — {ts_display}",
        "author": "AI Daily",
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "saved_using": "AI Daily routine",
    })
    if not ok:
        print("ERROR: brief POST failed, aborting.", file=sys.stderr)
        sys.exit(1)
    saved_urls = [brief_url]
    print("  Brief posted.", file=sys.stderr)
    time.sleep(0.2)

    # POST picks
    n_picks = 0
    for pick in picks:
        ok = rw_save({
            "url": pick["url"],
            "title": pick["title"],
            "summary": pick["blurb"],
            "tags": ["AI Daily", pick["source"]],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        })
        if ok:
            n_picks += 1
            saved_urls.append(pick["url"])
        time.sleep(0.2)
    print(f"  Picks posted: {n_picks}", file=sys.stderr)

    # Extract + POST citations (only for CITATION_SOURCES picks)
    n_citations = 0
    citation_picks = [p for p in picks if p["source"] in CITATION_SOURCES]
    print(f"Fetching citations from {len(citation_picks)} citation-source articles …", file=sys.stderr)

    current_seen = set(seen_urls) | set(saved_urls)

    for pick in citation_picks:
        print(f"  Citing: {pick['source']} — {pick['title'][:60]}", file=sys.stderr)
        try:
            r = requests.get(pick["url"], timeout=15,
                             headers={"User-Agent": "AIDaily/1.0 (citations)"})
            body = r.text
        except Exception as e:
            print(f"    Fetch error: {e}", file=sys.stderr)
            continue

        cited = extract_citations_from_html(body, current_seen)
        print(f"    Found {len(cited)} candidate citations", file=sys.stderr)
        for cit_url in cited:
            # derive title from URL
            tail = cit_url.rstrip("/").split("/")[-1][:80]
            title = tail.replace("-", " ").replace("_", " ").title()
            if not title:
                from urllib.parse import urlparse
                title = urlparse(cit_url).netloc + "/" + tail
            ok = rw_save({
                "url": cit_url,
                "title": title,
                "summary": f"Cited in '{pick['title'][:60]}' by {pick['source']}",
                "tags": ["AI Daily", f"Cited from {pick['source']}"],
                "location": "new",
                "category": "article",
                "saved_using": "AI Daily routine",
            })
            if ok:
                n_citations += 1
                saved_urls.append(cit_url)
                current_seen.add(cit_url)
            time.sleep(0.2)

    # Update seen.json
    now_iso = now_utc.isoformat()
    cutoff = now_utc - timedelta(days=14)
    # keep existing entries not older than 14 days
    fresh = [e for e in seen_data
             if datetime.fromisoformat(e.get("shipped_at", "2000-01-01T00:00:00+00:00")
                                       .replace("Z", "+00:00")) > cutoff]
    for url in saved_urls:
        fresh.append({"url": url, "shipped_at": now_iso})
    fresh.sort(key=lambda x: x["shipped_at"], reverse=True)
    with open(seen_path, "w") as f:
        json.dump(fresh, f, indent=2)
    print(f"seen.json updated: {len(fresh)} entries", file=sys.stderr)

    print(f"RESULT:{n_picks} articles,{n_citations} citations")

if __name__ == "__main__":
    main()
