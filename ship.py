#!/usr/bin/env python3
"""Post AI Daily brief and picks to Readwise Reader."""
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
SAVE_URL = "https://readwise.io/api/v3/save/"
SEEN_FILE = Path("seen.json")
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI",
                    "Latent Space", "Zvi Mowshowitz", "Pragmatic Engineer"}

BRIEF_SLUG = "AI_Daily_2026-06-25_1511"
BRIEF_TITLE = "AI Daily — Thursday, 25 June 2026 15:11"
BRIEF_TIMESTAMP = "Thursday, 25 June 2026 15:11"

PICKS = [
    {
        "url": "https://www.statnews.com/2026/06/25/radiology-generative-ai-cognita-aidoc-fda-breakthrough-designation/?utm_campaign=rss",
        "title": "FDA gives generative AI in radiology two breakthrough designation nods",
        "source": "STAT News",
        "blurb": "FDA grants breakthrough status to Cognita and Aidoc for generative AI in radiology — first regulatory go-signal for clinical generative AI at scale.",
    },
    {
        "url": "https://www.statnews.com/2026/06/24/biotech-news-bio-2026-glimpse-behind-lilly-and-chai-partnership/?utm_campaign=rss",
        "title": "At BIO, a glimpse behind Lilly and Chai's partnership",
        "source": "STAT News",
        "blurb": "Inside Eli Lilly's partnership with Chai Discovery: how big pharma integrates an AI-native protein-structure platform into drug discovery pipelines.",
    },
    {
        "url": "https://www.statnews.com/2026/06/24/artificial-intelligence-model-cause-of-sudden-cardiac-death/?utm_campaign=rss",
        "title": "AI wades into a vexing medical mystery: What causes sudden cardiac death?",
        "source": "STAT News",
        "blurb": "New AI model targets sudden cardiac death, one of medicine's oldest unsolved mysteries, with implications for clinical risk stratification.",
    },
    {
        "url": "https://www.latent.space/p/ainews-claude-tag-multiplayer-proactive",
        "title": "[AINews] Claude Tag: Multiplayer, Proactive, Persistent Agents in Slack",
        "source": "Latent Space",
        "blurb": "Anthropic's Claude Tag brings persistent, proactive multi-agent team members to Slack — Latent Space covers the enterprise-agent architecture shift.",
    },
    {
        "url": "https://thezvi.substack.com/p/ai-174-youre-it",
        "title": "AI #174: You're It",
        "source": "Zvi Mowshowitz",
        "blurb": "Zvi's weekly signal-to-noise digest covers the Fable model situation and the week's most consequential frontier AI developments.",
    },
    {
        "url": "https://www.statnews.com/2026/06/24/dispatch-from-bio-biotech-big-summer-bash-ai-prognosis/?utm_campaign=rss",
        "title": "A dispatch on AI from BIOtech's big summer bash",
        "source": "STAT News",
        "blurb": "STAT's floor report from BIO 2026: which AI themes dominated and what pharma leaders are actually committing to deploy in production.",
    },
    {
        "url": "https://www.technologyreview.com/2026/06/24/1139621/stripe-anthropic-and-openai-are-backing-an-effort-to-stop-respiratory-infections/",
        "title": "Stripe, Anthropic, and OpenAI are backing an effort to stop respiratory infections",
        "source": "MIT Technology Review",
        "blurb": "Leading AI labs and Stripe back a biomedical mission to eliminate respiratory infections — a signal of frontier labs entering organised medical R&D.",
    },
    {
        "url": "https://www.latent.space/p/databricks",
        "title": "Why the Frontier Ecosystem must be Open — Matei Zaharia and Reynold Xin, Databricks",
        "source": "Latent Space",
        "blurb": "Databricks co-founders argue the open frontier must win — grounded in deployment data and a playbook for how enterprise AI infrastructure should evolve.",
    },
    {
        "url": "https://arstechnica.com/ai/2026/06/oracles-21000-layoffs-help-drive-its-debt-fueled-ai-investments/",
        "title": "Oracle's 21,000 layoffs help drive its debt-fueled AI investments",
        "source": "Ars Technica AI",
        "blurb": "Oracle cut 21,000 workers in a year as AI restructuring funds compute buildout — the sharpest enterprise case of the OpEx-to-CapEx workforce shift.",
    },
    {
        "url": "https://techcrunch.com/2026/06/24/openai-unveils-its-first-custom-chip-built-by-broadcom/",
        "title": "OpenAI unveils its first custom chip, built by Broadcom",
        "source": "TechCrunch AI",
        "blurb": "OpenAI debuts Jalapeño, its first custom inference chip with Broadcom, reshaping the compute-dependency calculus for frontier AI providers.",
    },
    {
        "url": "https://techcrunch.com/2026/06/24/companies-are-scrambling-to-stop-employees-from-maxing-out-ai-budgets-with-small-tasks/",
        "title": "Companies scrambling to stop employees from maxing out AI budgets with small tasks",
        "source": "TechCrunch AI",
        "blurb": "Token rationing has arrived: enterprises throttle AI spend after employees exhaust budgets on low-value tasks — early signal of AI governance at scale.",
    },
    {
        "url": "https://newsletter.pragmaticengineer.com/p/slow-down-to-speed-up",
        "title": "Slow down to speed up: so much has changed in 6 months' time",
        "source": "Pragmatic Engineer",
        "blurb": "Six months of AI tool maturation reviewed: what engineering practice actually changed, and why deliberate adoption beats reactive sprinting.",
    },
]

EDITOR_NOTE = """<p>The dominant thread this week is pharma AI moving from pilot to pipeline. BIO 2026 produced concrete signals: STAT's floor dispatch shows pharma leaders no longer debating whether to use AI but how fast to re-wire their discovery workflows. Eli Lilly's Absci investment and the Lilly–Chai partnership at BIO mark two distinct strategies — one buying AI-native drug design capability, the other co-developing it with a foundation-model partner. Meanwhile, the FDA has granted generative AI its first breakthrough designations in radiology (Cognita and Aidoc), which is the clearest regulatory go-signal for clinical AI yet.</p>
<p>Three pieces land on the compute-and-capital side: OpenAI shipping its first custom inference chip (Jalapeño via Broadcom), Oracle restructuring 21,000 jobs to fund AI buildout, and Databricks making the case that the open-frontier model wins. Together they frame the infrastructure bet as decided — the question is who controls the stack.</p>
<p>On the enterprise governance floor: Anthropic's Claude Tag introduces persistent multi-agent team members in Slack, while TechCrunch documents the first wave of AI budget governance — companies discovering they need token rationing after employees maxed out AI spending on trivial tasks. Pragmatic Engineer rounds it out with six months of honest reflection on what actually changed in engineering practice.</p>"""

BRIEF_HTML = f"""<html><head><meta charset="utf-8"><title>{BRIEF_TITLE}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>{BRIEF_TITLE} (Prague)</h1>
<div class="editor">{EDITOR_NOTE}</div><hr/>
""" + "".join(
    f"""<h3>{i+1}. {p['title']}</h3>
<div class="meta">{p['source']}{"&nbsp;·&nbsp;<em>citations to follow</em>" if p['source'] in CITATION_SOURCES else ""}</div>
<p class="blurb">{p['blurb']}</p>
<p><a href="{p['url']}">Read source →</a></p>
""" for i, p in enumerate(PICKS)
) + "</body></html>"


def rw_post(body: dict) -> int:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        SAVE_URL,
        data=data,
        headers={
            "Authorization": f"Token {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read()[:200]}", file=sys.stderr)
        return e.code


def load_seen():
    if not SEEN_FILE.exists():
        return []
    try:
        return json.loads(SEEN_FILE.read_text())
    except Exception:
        return []


def save_seen(entries):
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - 14 * 86400
    existing = load_seen()
    seen_urls = {e["url"] for e in existing}
    for e in entries:
        if e["url"] not in seen_urls:
            existing.append(e)
    # Drop older than 14 days
    kept = []
    for e in existing:
        try:
            ts = datetime.fromisoformat(e["shipped_at"].replace("Z", "+00:00")).timestamp()
            if ts >= cutoff:
                kept.append(e)
        except Exception:
            kept.append(e)
    kept.sort(key=lambda x: x.get("shipped_at", ""), reverse=True)
    SEEN_FILE.write_text(json.dumps(kept, indent=2))


def main():
    shipped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_seen = []
    saved_picks = 0
    saved_citations = 0

    # Step 10: Save brief locally
    briefs_dir = Path("briefs")
    briefs_dir.mkdir(exist_ok=True)
    brief_path = briefs_dir / f"{BRIEF_SLUG}.html"
    brief_path.write_text(BRIEF_HTML, encoding="utf-8")
    print(f"Brief saved locally: {brief_path}", file=sys.stderr)

    # Step 11: Save brief to Readwise
    print("Posting brief to Readwise...", file=sys.stderr)
    status = rw_post({
        "url": f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/intelligent-tesla-33mxdn/briefs/{BRIEF_SLUG}.html",
        "html": BRIEF_HTML,
        "title": BRIEF_TITLE,
        "author": "AI Daily",
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "saved_using": "AI Daily routine",
    })
    if status not in (200, 201):
        print(f"ERROR: Brief post returned {status}", file=sys.stderr)
        sys.exit(1)
    print(f"  Brief posted: {status}", file=sys.stderr)

    # Step 12: Save each picked article
    print("Posting picks...", file=sys.stderr)
    pick_saved_urls = []
    for pick in PICKS:
        status = rw_post({
            "url": pick["url"],
            "title": pick["title"],
            "summary": pick["blurb"],
            "tags": ["AI Daily", pick["source"]],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        })
        if status in (200, 201):
            saved_picks += 1
            pick_saved_urls.append(pick["url"])
            new_seen.append({"url": pick["url"], "shipped_at": shipped_at})
            print(f"  ✓ {pick['source']}: {pick['title'][:60]}", file=sys.stderr)
        else:
            print(f"  ✗ {status}: {pick['title'][:60]}", file=sys.stderr)
        time.sleep(0.2)

    # Step 13: Citations from CITATION_SOURCES picks
    print("Extracting citations...", file=sys.stderr)
    seen_urls_set = {e["url"] for e in load_seen()} | {e["url"] for e in new_seen}

    citation_picks = [p for p in PICKS
                      if p["source"] in CITATION_SOURCES and p["url"] in pick_saved_urls]

    # We'll write cited URLs to a file for the next script step (WebFetch happens outside)
    # For now write the picks that need citation extraction
    Path("citation_picks.json").write_text(json.dumps(citation_picks, indent=2))
    Path("seen_urls.json").write_text(json.dumps(list(seen_urls_set)))

    # Step 14: Update seen.json
    save_seen(new_seen)
    print(f"Seen.json updated with {len(new_seen)} entries", file=sys.stderr)

    print(f"RESULT:{saved_picks}:{saved_citations}")


if __name__ == "__main__":
    main()
