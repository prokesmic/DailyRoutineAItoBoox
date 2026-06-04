"""
AI Daily pipeline — steps 9-16 (brief compose, Readwise save, citations, seen.json, commit).
Run after candidates.json is already present.
"""
import json, os, re, time, subprocess, sys
from datetime import datetime, timezone

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space", "Zvi Mowshowitz", "Pragmatic Engineer"}
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}

import httpx

PICKS = [
    {
        "title": "An Interview with Microsoft CEO Satya Nadella About Finding Core Competencies",
        "url": "https://stratechery.com/2026/an-interview-with-microsoft-ceo-satya-nadella-about-finding-core-competencies",
        "source": "Stratechery",
        "blurb": "Nadella defines Microsoft's AI identity after Build: Copilot vs Azure positioning, the OpenAI relationship, and where core competency lands in 2026.",
    },
    {
        "title": "Satya Nadella: No Priors x Latent Space Crossover Special at Microsoft Build",
        "url": "https://www.latent.space/p/satya-2026",
        "source": "Latent Space",
        "blurb": "First Latent Space appearance by a Fortune 50 CEO; Nadella on agents-as-products, the Microsoft AI PC thesis, and compounding moats.",
    },
    {
        "title": "The Google Capital Company",
        "url": "https://stratechery.com/2026/the-google-capital-company",
        "source": "Stratechery",
        "blurb": "Alphabet issues equity to Berkshire Hathaway; Stratechery frames it as capital-as-moat strategy — the new competitive logic of AI infrastructure financing.",
    },
    {
        "title": "Uber Caps Usage of AI Tools Like Claude Code to Manage Costs",
        "url": "https://simonwillison.net/2026/Jun/3/uber-caps-usage/",
        "source": "Simon Willison",
        "blurb": "Uber blew its entire 2026 AI tooling budget in four months and is now rationing Claude Code — a concrete OpEx data point every enterprise should benchmark.",
    },
    {
        "title": "Trump Signs Executive Order For AI Testing Prior To Frontier Model Releases",
        "url": "https://thezvi.wordpress.com/2026/06/03/trump-signs-executive-order-for-ai-testing-prior-to-frontier-model-releases",
        "source": "Zvi Mowshowitz",
        "blurb": "White House EO walked mandatory pre-release AI testing back to voluntary; Zvi explains what was conceded in negotiations and what enforcement now looks like.",
    },
    {
        "title": "Claude Opus 4.8: Capabilities and Reactions",
        "url": "https://thezvi.wordpress.com/2026/06/02/claude-opus-4-8-capabilities-and-reactions",
        "source": "Zvi Mowshowitz",
        "blurb": "Rigorous multi-axis evaluation of Opus 4.8: capability jumps, benchmark comparisons, and what the new model actually changes for practitioners beyond the marketing.",
    },
    {
        "title": "Ideas: slow down to speed up when working with AI agents",
        "url": "https://newsletter.pragmaticengineer.com/p/ideas-slow-down-to-speed-up-when",
        "source": "Pragmatic Engineer",
        "blurb": "Devs now generate 2x the code; review depth hasn't kept pace — concrete patterns for sustainable agent-assisted workflows before velocity becomes a quality liability.",
    },
    {
        "title": "GitHub's plan for Agents — Kyle Daigle, GitHub",
        "url": "https://www.latent.space/p/github",
        "source": "Latent Space",
        "blurb": "GitHub's VP of Engineering on how agents are replacing the PR review model, with adoption numbers and the architectural shift in software delivery at scale.",
    },
    {
        "title": "Import AI 459: AI oversight is difficult; scaling laws for protein folding models",
        "url": "https://importai.substack.com/p/import-ai-459-ai-oversight-is-difficult",
        "source": "Import AI",
        "blurb": "Scaling laws demonstrated for protein-folding foundation models — direct signal for pharma AI pipelines; plus a sober diagnosis of why AI oversight is harder than assumed.",
    },
    {
        "title": "Introducing new capabilities to GPT-Rosalind",
        "url": "https://openai.com/index/introducing-new-capabilities-to-gpt-rosalind",
        "source": "OpenAI",
        "blurb": "OpenAI's life-sciences LLM gains biological reasoning and medicinal chemistry expertise — first-party announcement directly relevant to pharma AI investment decisions.",
    },
    {
        "title": "The ways we contain Claude across products",
        "url": "https://www.anthropic.com/engineering/how-we-contain-claude",
        "source": "Anthropic",
        "blurb": "Anthropic's engineering team on operator/user/system-prompt containment architecture — essential reading for deploying Claude in regulated or GxP-sensitive contexts.",
    },
    {
        "title": "Ep 789: Tokenmaxxing is over — The New Era of Token Efficiency",
        "url": "https://read.youreverydayai.com/p/ep-789-tokenmaxxing-is-over-the-new-era-of-token-efficiency-and-how-your-company-should-adapt",
        "source": "Everyday AI",
        "blurb": "Strategic shift signal: model-scaling era gives way to token efficiency; implications for enterprise AI cost modeling and architecture as the subsidy period ends.",
    },
]

EDITORS_NOTE = """<p>The week's strongest thread is capital and positioning at the hyperscaler layer.
Alphabet's $85B equity deal — read through Stratechery's lens — isn't fundraising; it's locking in
capital as a structural moat before AI infrastructure gets priced as permanent utility. Satya Nadella
appeared on both Stratechery and Latent Space in the same week, which is itself a signal: Microsoft is
actively managing the narrative on its post-Build AI identity, especially its relationship with OpenAI
and the Copilot vs. Azure split.</p>
<p>Three pieces form a useful enterprise deployment cluster: Uber burned its full-year AI tooling budget
in four months and is now rationing Claude Code access; Pragmatic Engineer argues that 2x code
generation without 2x review is a quality debt accumulation story; and Anthropic's engineering blog
explains the containment scaffolding that makes regulated deployment tractable. Read these three together
before any internal AI tooling budget conversation.</p>
<p>On governance, Trump signed a meaningfully weakened AI EO — mandatory pre-release testing became
voluntary after industry lobbying; Zvi has the full analysis. On science, Import AI covers scaling laws
for protein-folding models, and OpenAI's GPT-Rosalind adds biological reasoning to a life-sciences LLM —
both direct reads for anyone steering AI investment in pharma or biotech.</p>"""

# ─── Prague timestamp ───────────────────────────────────────────────────────
import subprocess as sp
prague_ts = sp.check_output(
    ['bash','-c','TZ=Europe/Prague date +"%A, %-d %B %Y %H:%M"'], text=True
).strip()
slug_ts = sp.check_output(
    ['bash','-c','TZ=Europe/Prague date +%Y-%m-%d_%H%M'], text=True
).strip()
BRIEF_SLUG = f"AI_Daily_{slug_ts}"

# ─── Step 9: compose HTML ────────────────────────────────────────────────────
rows = []
for i, p in enumerate(PICKS, 1):
    citation_note = " · citations to follow" if p["source"] in CITATION_SOURCES else ""
    rows.append(f"""<h3>{i}. {p['title']}</h3>
<div class="meta">{p['source']}{citation_note}</div>
<p class="blurb">{p['blurb']}</p>
<p><a href="{p['url']}">Read source →</a></p>""")

BRIEF_HTML = f"""<html><head><meta charset="utf-8"><title>AI Daily — {prague_ts}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>AI Daily — {prague_ts} (Prague)</h1>
<div class="editor">{EDITORS_NOTE}</div><hr/>
{''.join(rows)}
</body></html>"""

# ─── Step 10: save brief locally ────────────────────────────────────────────
os.makedirs("briefs", exist_ok=True)
brief_path = f"briefs/{BRIEF_SLUG}.html"
with open(brief_path, "w") as f:
    f.write(BRIEF_HTML)
print(f"Brief saved: {brief_path}", file=sys.stderr)

# ─── Readwise helpers ────────────────────────────────────────────────────────
saved_urls = []   # (url, type)
failed_urls = []

def rw_save(client, payload, label=""):
    r = client.post("https://readwise.io/api/v3/save/", headers=HEADERS, json=payload, timeout=30)
    if r.status_code in (200, 201):
        saved_urls.append(payload["url"])
        return True
    else:
        print(f"SAVE FAIL [{r.status_code}] {label}: {r.text[:200]}", file=sys.stderr)
        failed_urls.append(payload["url"])
        return False

with httpx.Client(timeout=30) as c:
    # ─── Step 11: save brief to Readwise ─────────────────────────────────────
    brief_payload = {
        "url": f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/create-ai-daily-reader-gylCx/briefs/{BRIEF_SLUG}.html",
        "html": BRIEF_HTML,
        "title": f"AI Daily — {prague_ts}",
        "author": "AI Daily routine",
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "saved_using": "AI Daily routine",
    }
    ok = rw_save(c, brief_payload, "brief")
    if not ok:
        print("FATAL: could not save brief to Readwise.", file=sys.stderr)
        sys.exit(1)
    print("Brief posted to Readwise.", file=sys.stderr)

    # ─── Step 12: save each pick ──────────────────────────────────────────────
    pick_saved = []
    for p in PICKS:
        payload = {
            "url": p["url"],
            "title": p["title"],
            "summary": p["blurb"],
            "tags": ["AI Daily", p["source"]],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        }
        ok = rw_save(c, payload, p["title"][:50])
        if ok:
            pick_saved.append(p)
        time.sleep(0.2)

    print(f"Picks saved: {len(pick_saved)}/{len(PICKS)}", file=sys.stderr)

    # ─── Step 13: extract citations ───────────────────────────────────────────
    # Load seen URLs to avoid re-saving
    seen_set = set()
    if os.path.exists("seen.json"):
        try:
            seen_set = {row["url"] for row in json.load(open("seen.json"))}
        except Exception:
            pass
    # Add all pick URLs to seen_set
    for p in PICKS:
        seen_set.add(p["url"])

    citation_count = 0
    citation_urls = []

    for p in pick_saved:
        if p["source"] not in CITATION_SOURCES:
            continue
        print(f"Fetching citations from: {p['source']} — {p['title'][:60]}", file=sys.stderr)
        try:
            r = c.get(p["url"], timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; AIDaily/1.0)"})
            html_body = r.text
        except Exception as ex:
            print(f"  Fetch error: {ex}", file=sys.stderr)
            continue

        # Extract href URLs from the article body
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_body)
        # Filter to substantive external links
        skip_patterns = [
            r'twitter\.com', r'x\.com', r'threads\.net', r'mastodon\.',
            r'linkedin\.com/in/', r'facebook\.com', r'instagram\.com',
            r'youreverydayai\.com', r'latent\.space', r'thezvi\.wordpress',
            r'newsletter\.pragmaticengineer', r'oneusefulthing\.org',
            r'karpathy\.github', r'substack\.com/p/',  # same-site
            r'#', r'javascript:', r'mailto:',
            r'apple\.com/podcasts', r'spotify\.com', r'youtube\.com',
            r'open\.spotify', r'podcasts\.google', r'overcast\.fm',
            r'pocketcasts\.com', r'podcastaddict',
        ]
        # Same-site skip
        try:
            from urllib.parse import urlparse
            source_host = urlparse(p["url"]).netloc
        except Exception:
            source_host = ""

        candidates_cit = []
        seen_in_loop = set()
        for href in hrefs:
            href = href.strip()
            if not href.startswith("http"):
                continue
            # strip fragments and query-only changes
            href_clean = href.split("#")[0].split("?")[0].rstrip("/")
            if not href_clean or href_clean in seen_in_loop:
                continue
            seen_in_loop.add(href_clean)
            if href_clean in seen_set:
                continue
            try:
                href_host = urlparse(href_clean).netloc
            except Exception:
                continue
            if href_host == source_host:
                continue
            skip = False
            for pat in skip_patterns:
                if re.search(pat, href_clean, re.I):
                    skip = True
                    break
            if skip:
                continue
            # Prefer arXiv, GitHub, named research domains
            score = 0
            if "arxiv.org" in href_clean:
                score += 3
            elif "github.com" in href_clean and any(kw in href_clean.lower() for kw in ["research","paper","model","dataset","llm","ml","ai"]):
                score += 2
            elif any(d in href_clean for d in ["nature.com","science.org","biorxiv.org","openreview.net","proceedings.mlr.press","dl.acm.org","semanticscholar.org"]):
                score += 3
            elif any(d in href_clean for d in ["openai.com","anthropic.com","deepmind.google","huggingface.co/papers","mistral.ai"]):
                score += 2
            elif any(d in href_clean for d in ["techcrunch.com","theverge.com","wired.com","nytimes.com","ft.com","bloomberg.com","wsj.com"]):
                score += 1
            elif any(d in href_clean for d in ["substack.com","medium.com","newsletter","blog"]):
                score += 1
            else:
                score += 1
            candidates_cit.append((score, href_clean))

        # Sort by score, take top 3
        candidates_cit.sort(key=lambda x: -x[0])
        top_cit = candidates_cit[:3]

        for score, cit_url in top_cit:
            if cit_url in seen_set:
                continue
            # Build a title guess
            tail = cit_url.split("/")[-1] or cit_url.split("/")[-2]
            tail = re.sub(r'[-_]', ' ', tail)[:60]
            from urllib.parse import urlparse as up2
            host = up2(cit_url).netloc.replace("www.","")
            title_guess = f"{host} — {tail}" if tail else host

            cit_payload = {
                "url": cit_url,
                "title": title_guess,
                "summary": f"Cited in '{p['title'][:80]}' by {p['source']}",
                "tags": ["AI Daily", f"Cited from {p['source']}"],
                "location": "new",
                "category": "article",
                "saved_using": "AI Daily routine",
            }
            ok = rw_save(c, cit_payload, f"citation: {cit_url[:60]}")
            if ok:
                citation_count += 1
                citation_urls.append(cit_url)
                seen_set.add(cit_url)
            time.sleep(0.2)

print(f"Citations saved: {citation_count}", file=sys.stderr)

# ─── Step 14: update seen.json ───────────────────────────────────────────────
now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
cutoff_dt = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
from datetime import timedelta
keep_cutoff = cutoff_dt - timedelta(days=14)

existing = []
if os.path.exists("seen.json"):
    try:
        existing = json.load(open("seen.json"))
    except Exception:
        existing = []

# Drop old entries
def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

existing = [e for e in existing if parse_dt(e.get("shipped_at","")) >= keep_cutoff]

# Add new URLs
existing_urls = {e["url"] for e in existing}
for url in saved_urls:
    if url not in existing_urls:
        existing.append({"url": url, "shipped_at": now_iso})
        existing_urls.add(url)

# Sort descending
existing.sort(key=lambda e: e.get("shipped_at",""), reverse=True)

with open("seen.json","w") as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)
print(f"seen.json updated: {len(existing)} entries", file=sys.stderr)

# ─── Summary counts ──────────────────────────────────────────────────────────
n_picks = len(pick_saved)
n_cit = citation_count
print(f"RESULT:{n_picks}:{n_cit}")
