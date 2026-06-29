#!/usr/bin/env python3
"""AI Daily pipeline: build brief, save to Readwise, update seen.json."""

import json, os, time, datetime, urllib.request, urllib.parse, urllib.error, sys, html

READWISE_TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space", "Zvi Mowshowitz", "Pragmatic Engineer"}
HEADERS = {"Authorization": f"Token {READWISE_TOKEN}", "Content-Type": "application/json"}

BRIEF_SLUG = "AI_Daily_2026-06-29_1510"
PRAGUE_TIME = "Monday, 29 June 2026 15:10"
BRANCH = "claude/intelligent-tesla-2tqpm8"

PICKS = [
    {
        "url": "https://www.latent.space/p/ainews-openai-gpt-56-sol-terra-luna",
        "title": "[AINews] OpenAI GPT-5.6 Sol / Terra / Luna — restricted to trusted partners",
        "source": "Latent Space",
        "blurb": "Three-tier restricted frontier model with White House vetting signals a new quasi-regulatory access paradigm for enterprise AI buyers.",
        "cluster": "frontier model moves",
    },
    {
        "url": "https://thezvi.wordpress.com/2026/06/26/white-house-will-ad-hoc-decide-who-can-individually-access-gpt-5-6",
        "title": "White House Will Ad Hoc Decide Who Can Individually Access GPT-5.6",
        "source": "Zvi Mowshowitz",
        "blurb": "Opaque per-company government vetting of frontier model access could upend every enterprise AI roadmap built on commercial availability.",
        "cluster": "governance/workforce",
    },
    {
        "url": "https://thezvi.wordpress.com/2026/06/28/gpt-5-6-the-system-card",
        "title": "GPT-5.6: The System Card",
        "source": "Zvi Mowshowitz",
        "blurb": "Zvi dissects the GPT-5.6 system card, surfacing what the capability narrative leaves unsaid about alignment and deployment constraints.",
        "cluster": "frontier model moves",
    },
    {
        "url": "https://openai.com/index/mapping-ai-jobs-transition-eu",
        "title": "Mapping Europe's AI Workforce Opportunity",
        "source": "OpenAI",
        "blurb": "OpenAI primary report mapping EU job-transition risk by occupation — direct input for P&O AI strategy and workforce fluency programs.",
        "cluster": "governance/workforce",
    },
    {
        "url": "https://importai.substack.com/p/import-ai-463-self-improving-robots",
        "title": "Import AI 463: Self-improving robots; a 10k Chinese GPU cluster; and an elegiac essay for the human era",
        "source": "Import AI",
        "blurb": "Jack Clark surfaces self-improving robot research and a 10k-GPU Chinese cluster — acceleration signals outside Western hyperscaler orbit.",
        "cluster": "capital flows/compute",
    },
    {
        "url": "https://www.lennysnewsletter.com/p/no-figma-no-jira-no-docs-how-gusto",
        "title": "No Figma. No Jira. No docs. How Gusto built a new product line with Claude Code | Eddie Kim (CTO)",
        "source": "Lenny's Newsletter",
        "blurb": "Concrete enterprise case study: Gusto shipped a product line dropping traditional tooling entirely, using Claude Code as the operating layer.",
        "cluster": "builder methodology",
    },
    {
        "url": "https://www.interconnects.ai/p/artifacts-22-zyphra-cohere-and-poolside",
        "title": "Latest open artifacts (#22): Zyphra, Cohere, and Poolside are expanding the breadth of the ecosystem",
        "source": "Interconnects",
        "blurb": "Three new open-weight releases advance on-premise and regulated-environment deployment options — relevant for GxP-constrained pharma AI.",
        "cluster": "frontier model moves",
    },
    {
        "url": "https://marginalrevolution.com/marginalrevolution/2026/06/will-future-biomedical-advances-be-low-marginal-cost.html",
        "title": "Will future biomedical advances be low marginal cost?",
        "source": "Marginal Revolution",
        "blurb": "Cowen argues AI compresses biomedical R&D toward marginal cost of software — a structural thesis that re-prices pharma capex assumptions.",
        "cluster": "AI-for-science",
    },
    {
        "url": "https://marginalrevolution.com/marginalrevolution/2026/06/my-arc-talk-on-ai-and-jobs.html",
        "title": "My ARC talk on AI and jobs",
        "source": "Marginal Revolution",
        "blurb": "Cowen's empirical view on AI and labor displacement — measured, evidence-grounded, cuts through both panic and complacency.",
        "cluster": "governance/workforce",
    },
    {
        "url": "https://www.bloomberg.com/news/articles/2026-06-28/austria-lobbies-eu-to-host-anthropic-after-us-access-curbs",
        "title": "Austria Lobbies EU to Host Anthropic After US Access Curbs",
        "source": "Bloomberg",
        "blurb": "EU governments competing to attract frontier labs post-export-controls — direct geopolitical context for Prague-based AI strategic programs.",
        "cluster": "governance/workforce",
    },
    {
        "url": "https://www.lennysnewsletter.com/p/openai-codex-lead-on-the-new-shape",
        "title": "OpenAI Codex lead on the new shape of product work | Andrew Ambrosino",
        "source": "Lenny's Newsletter",
        "blurb": "Codex product lead on how agentic coding reshapes PM/engineer team topology — org implications beyond individual productivity.",
        "cluster": "agentic systems",
    },
    {
        "url": "https://semgrep.dev/blog/2026/we-have-mythos-at-home-glm-52-beats-claude-in-our-cyber-benchmarks",
        "title": "GLM 5.2 beats Claude in our benchmarks",
        "source": "Semgrep Blog",
        "blurb": "Semgrep's cyber-security benchmark finds GLM 5.2 outperforming Claude — AI capability competition is now genuinely multilateral and open-weight.",
        "cluster": "frontier model moves",
    },
]

EDITOR_NOTE = """<p>The dominant story this week is GPT-5.6 and its extraordinary politics: a restricted release gated by White House approval, three capability tiers (Sol/Terra/Luna), and an ad-hoc per-company vetting process that no enterprise AI strategy anticipated. Zvi and Latent Space both dissect this — read them as a pair. The shift from commercial to quasi-regulatory model access is consequential for EU-based organizations that already navigate data-sovereignty rules and GxP compliance; what was a procurement decision is now a geopolitical one.</p>

<p>Two pieces run parallel on the workforce question: OpenAI's EU labor-transition report maps displacement risk by occupation while Cowen's ARC talk provides the macroeconomic frame. His biomedical low-marginal-cost thesis is the more provocative read for pharma: if AI compresses R&D cost curves the way he argues, capex assumptions need revision now. Austria's lobbying to host Anthropic underscores that EU governments are no longer passive observers of this reconfiguration.</p>

<p>Builder signal is strong: Gusto's Claude Code case study is the clearest enterprise deployment blueprint this week. Interconnects rounds out the open-model field with Zyphra, Cohere, and Poolside advancing regulated-environment options. Semgrep's GLM 5.2 benchmark is the sharpest reminder that capability competition is now multilateral and open-weight.</p>"""


def rw_post(body: dict, retries=3):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "https://readwise.io/api/v3/save/",
        data=data,
        headers=HEADERS,
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            return e.code, {}
        except Exception as e:
            print(f"  rw_post error: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(2)
            continue
    return 0, {}


def load_seen():
    try:
        with open("seen.json") as f:
            return json.load(f)
    except Exception:
        return []


def save_seen(entries):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)
    fresh = []
    for e in entries:
        try:
            dt = datetime.datetime.fromisoformat(e["shipped_at"].replace("Z", "+00:00"))
            if dt > cutoff:
                fresh.append(e)
        except Exception:
            pass
    fresh.sort(key=lambda e: e["shipped_at"], reverse=True)
    with open("seen.json", "w") as f:
        json.dump(fresh, f, indent=2)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_brief_html(picks, editor_note, prague_time):
    items_html = ""
    for i, p in enumerate(picks, 1):
        cit_note = " · citations to follow" if p["source"] in CITATION_SOURCES else ""
        items_html += f"""<h3>{i}. {html.escape(p['title'])}</h3>
<div class="meta">{html.escape(p['source'])}{cit_note}</div>
<p class="blurb">{html.escape(p['blurb'])}</p>
<p><a href="{p['url']}">Read source →</a></p>
"""
    return f"""<html><head><meta charset="utf-8"><title>AI Daily — {prague_time}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>AI Daily — {prague_time}</h1>
<div class="editor">{editor_note}</div><hr/>
{items_html}</body></html>"""


def main():
    seen = load_seen()
    new_entries = []
    saved_picks = 0
    saved_citations = 0

    # Build and save brief locally
    brief_html = build_brief_html(PICKS, EDITOR_NOTE, PRAGUE_TIME)
    os.makedirs("briefs", exist_ok=True)
    brief_path = f"briefs/{BRIEF_SLUG}.html"
    with open(brief_path, "w") as f:
        f.write(brief_html)
    print(f"Brief written: {brief_path}", file=sys.stderr)

    # Save brief to Readwise
    brief_url = f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/{BRANCH}/briefs/{BRIEF_SLUG}.html"
    status, resp = rw_post({
        "url": brief_url,
        "html": brief_html,
        "title": f"AI Daily — {PRAGUE_TIME}",
        "author": "AI Daily routine",
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "saved_using": "AI Daily routine",
    })
    if status not in (200, 201):
        print(f"ERROR saving brief to Readwise: HTTP {status}", file=sys.stderr)
        sys.exit(1)
    print(f"Brief → Readwise HTTP {status}", file=sys.stderr)
    new_entries.append({"url": brief_url, "shipped_at": now_iso()})

    # Save picks
    for pick in PICKS:
        time.sleep(0.2)
        status, resp = rw_post({
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
            new_entries.append({"url": pick["url"], "shipped_at": now_iso()})
            print(f"  ✓ [{status}] {pick['title'][:70]}", file=sys.stderr)
        else:
            print(f"  ✗ [{status}] {pick['title'][:70]}", file=sys.stderr)

    # Update seen.json (without citations yet — those come after WebFetch)
    seen.extend(new_entries)
    save_seen(seen)

    # Print results for citation step
    print(json.dumps({
        "picks": saved_picks,
        "new_entries": new_entries,
        "citation_eligible": [p for p in PICKS if p["source"] in CITATION_SOURCES],
    }))


if __name__ == "__main__":
    main()
