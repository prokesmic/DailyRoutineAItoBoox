"""Execute AI Daily pipeline steps 8-15."""
import json, time, sys, os, re
from datetime import datetime, timezone, timedelta
import httpx

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space", "Zvi Mowshowitz", "Pragmatic Engineer"}

# ── Picks (scored and ranked) ──────────────────────────────────────────────────
PICKS = [
    {
        "url": "https://stratechery.com/2026/power-shifts",
        "title": "2026.23: Power Shifts",
        "source": "Stratechery",
        "blurb": "Strategic analysis of how compute economics and AI investment flows are reshaping power across frontier labs, hyperscalers, and enterprise buyers.",
    },
    {
        "url": "https://www.oneusefulthing.org/p/co-existence-and-the-end-of-co-intelligence",
        "title": "Co-Existence and the End of Co-Intelligence",
        "source": "Ethan Mollick",
        "blurb": "Mollick argues the AI partnership framing is giving way to something more disruptive—required reading for any exec leading AI strategy.",
    },
    {
        "url": "https://thezvi.wordpress.com/2026/06/05/openai-offers-a-new-policy-blueprint",
        "title": "OpenAI Offers A New Policy Blueprint",
        "source": "Zvi Mowshowitz",
        "blurb": "OpenAI's federal governance framework for frontier AI includes recursive self-improvement warnings—high signal on where the policy fight is heading.",
    },
    {
        "url": "https://simonwillison.net/2026/Jun/4/ai-enthusiasts-ai-skeptics/",
        "title": "AI enthusiasts are in a race against time, AI skeptics are in a race against entropy",
        "source": "Simon Willison",
        "blurb": "Sharpest ideological split framing of the year: enthusiasts race before incumbents adapt; skeptics bet institutions absorb disruption first.",
    },
    {
        "url": "https://thezvi.wordpress.com/2026/06/04/ai-171-false-flag",
        "title": "AI #171: False Flag",
        "source": "Zvi Mowshowitz",
        "blurb": "Zvi's comprehensive week-in-review covering Claude Opus 4.8 launch, model welfare debate, and enterprise capability assessment.",
    },
    {
        "url": "https://www.latent.space/p/bad-envs",
        "title": "How to Stop Shipping Low-Quality RL Environments (with Examples)",
        "source": "Latent Space",
        "blurb": "Practitioners share concrete patterns and failure modes in building RL training environments—critical for anyone building production agentic systems.",
    },
    {
        "url": "https://www.latent.space/p/andon",
        "title": "Reality: The Final Eval — Lukas Petersson and Axel Backlund of Andon Labs",
        "source": "Latent Space",
        "blurb": "Andon Labs argues real-world deployment is the only meaningful eval—dissects how benchmarks fail to predict production outcomes.",
    },
    {
        "url": "https://www.technologyreview.com/2026/06/05/1138437/the-meta-hack-shows-theres-more-to-ai-security-than-mythos",
        "title": "The Meta hack shows there's more to AI security than Mythos",
        "source": "MIT Tech Review AI",
        "blurb": "Meta's AI chatbot exploited to hack thousands of Instagram accounts—concrete case for why enterprise AI security requires new frameworks beyond traditional controls.",
    },
    {
        "url": "https://huggingface.co/blog/nvidia/nemotron-3-5-content-safety",
        "title": "Nemotron 3.5 Content Safety: Customizable Multimodal Safety for Global Enterprise",
        "source": "Hugging Face",
        "blurb": "NVIDIA's multimodal safety model for global enterprise: customizable for regional compliance regimes, directly relevant to GxP and regulated industries.",
    },
    {
        "url": "https://arxiv.org/abs/2601.14470",
        "title": "Tokenomics: Quantifying Where Tokens Are Used in Agentic Software Engineering",
        "source": "HN (120 pts)",
        "blurb": "First quantitative breakdown of token distribution in agentic coding pipelines—essential numbers for managing AI-assisted development costs at scale.",
    },
    {
        "url": "https://techcrunch.com/2026/06/05/the-token-bill-comes-due-inside-the-industry-scramble-to-manage-ais-runaway-costs",
        "title": "The token bill comes due: Inside the industry scramble to manage AI's runaway costs",
        "source": "TechCrunch AI",
        "blurb": "Industry-wide reckoning with AI's runaway inference costs; maps how enterprises are restructuring usage to manage the OpEx surprise.",
    },
    {
        "url": "https://read.youreverydayai.com/p/ep-787-claude-opus-4-8-new-copilot-studio-agents-chatgpt-agent-updates-and-7-other-ai-features-you-c-0d4d",
        "title": "Ep 792: Autonomous Copilot Agents, New Codex Tools, GitHub CoPilot App and 7 More AI Updates",
        "source": "Everyday AI",
        "blurb": "Microsoft's autonomous Copilot agents, new Codex tools, and GitHub app updates: practical enterprise AI deployment signals from Build week.",
    },
]

EDITOR_NOTE = """<p>The strongest thread this weekend: a strategic power shift is underway in how AI compute and capital are being allocated. Stratechery maps how the subsidized growth era is giving way to ruthless compute economics — the $920M/month Google-SpaceX deal being Exhibit A — while TechCrunch's piece on runaway inference costs shows enterprise buyers are already feeling the OpEx squeeze. Ethan Mollick signals something deeper in the workforce conversation: the "co-intelligence" framing is giving way to something more disruptive, not more collaborative.</p>
<p>Three pieces on governance and the policy frontier: OpenAI's federal framework floats recursive self-improvement as a real risk, Zvi's AI #171 anchors the Claude Opus 4.8 moment, and Simon Willison offers the sharpest framing of the ideological split — enthusiasts racing before incumbents adapt, skeptics betting on institutional absorption.</p>
<p>For builders: Latent Space delivers two strong practical pieces on RL environments and real-world evals. The arXiv tokenomics paper quantifies token burn in agentic pipelines — numbers your infrastructure team will want. The Meta/Instagram hack via AI chatbot is this week's enterprise security wake-up call, and NVIDIA's Nemotron safety model is worth a look for anyone in regulated environments.</p>"""

# ── Timestamp ─────────────────────────────────────────────────────────────────
import subprocess
prg_time = subprocess.check_output(["bash","-c","TZ=Europe/Prague date +'%A, %-d %B %Y %H:%M'"]).decode().strip()
slug = subprocess.check_output(["bash","-c","TZ=Europe/Prague date +AI_Daily_%Y-%m-%d_%H%M"]).decode().strip()
title = f"AI Daily — {prg_time} (Prague)"

# ── Build HTML ────────────────────────────────────────────────────────────────
picks_html = ""
for i, p in enumerate(PICKS, 1):
    cit_note = " · citations to follow" if p["source"] in CITATION_SOURCES else ""
    picks_html += f"""<h3>{i}. {p['title']}</h3>
<div class="meta">{p['source']}{cit_note}</div>
<p class="blurb">{p['blurb']}</p>
<p><a href="{p['url']}">Read source →</a></p>
"""

html = f"""<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>{title}</h1>
<div class="editor">{EDITOR_NOTE}</div><hr/>
{picks_html}
</body></html>"""

os.makedirs("briefs", exist_ok=True)
brief_path = f"briefs/{slug}.html"
with open(brief_path, "w") as f:
    f.write(html)
print(f"Brief saved: {brief_path}", file=sys.stderr)

# ── Readwise save helper ──────────────────────────────────────────────────────
def rw_save(payload, label=""):
    try:
        r = httpx.post("https://readwise.io/api/v3/save/", headers=HEADERS, json=payload, timeout=30)
        if r.status_code in (200, 201):
            return True
        print(f"Save failed [{label}]: {r.status_code} {r.text[:200]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Save error [{label}]: {e}", file=sys.stderr)
        return False

# ── Step 11: Save brief ───────────────────────────────────────────────────────
brief_url = f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/create-ai-daily-reader-gylCx/briefs/{slug}.html"
ok = rw_save({
    "url": brief_url,
    "html": html,
    "title": title,
    "author": "AI Daily routine",
    "tags": ["AI Daily", "Brief"],
    "location": "new",
    "category": "article",
    "should_clean_html": False,
    "saved_using": "AI Daily routine",
}, "brief")
if not ok:
    print("FATAL: brief save failed", file=sys.stderr)
    sys.exit(1)
print("Brief posted to Readwise", file=sys.stderr)

# ── Step 12: Save picks ────────────────────────────────────────────────────────
saved_picks = []
failed_picks = []
for p in PICKS:
    ok = rw_save({
        "url": p["url"],
        "title": p["title"],
        "summary": p["blurb"],
        "tags": ["AI Daily", p["source"]],
        "location": "new",
        "category": "article",
        "saved_using": "AI Daily routine",
    }, p["title"][:40])
    if ok:
        saved_picks.append(p)
    else:
        failed_picks.append(p)
    time.sleep(0.2)

print(f"Picks saved: {len(saved_picks)}/{len(PICKS)}", file=sys.stderr)

# ── Step 13: Extract citations from citation-source picks ──────────────────────
seen_data = []
if os.path.exists("seen.json"):
    try:
        seen_data = json.load(open("seen.json"))
    except:
        pass
seen_urls = {row["url"] for row in seen_data}
# also add pick URLs to seen
for p in PICKS:
    seen_urls.add(p["url"])

citation_results = []  # (pick_title, pick_source, cited_url, ok)

def extract_citations(pick):
    """Fetch article and extract substantive cited URLs."""
    from urllib.parse import urlparse
    SKIP_DOMAINS = {
        "twitter.com","x.com","t.co","threads.net","mastodon.social","linkedin.com",
        "facebook.com","instagram.com","youtube.com","open.spotify.com",
        "podcasts.apple.com","overcast.fm","pocketcasts.com",
    }
    try:
        r = httpx.get(pick["url"], headers={"User-Agent":"Mozilla/5.0"}, timeout=25, follow_redirects=True)
        body = r.text
    except Exception as e:
        print(f"Fetch error for citations [{pick['title'][:40]}]: {e}", file=sys.stderr)
        return []

    # extract all href links
    raw_links = re.findall(r'href=["\']([^"\'#\s]+)["\']', body)
    candidates = []
    for link in raw_links:
        if not link.startswith("http"):
            continue
        parsed = urlparse(link)
        domain = parsed.netloc.lstrip("www.")
        if domain in SKIP_DOMAINS:
            continue
        # skip same-site links
        pick_domain = urlparse(pick["url"]).netloc.lstrip("www.")
        if domain == pick_domain:
            continue
        # skip nav/image/media
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in (".png",".jpg",".jpeg",".gif",".svg",".ico",".mp3",".mp4",".pdf")):
            continue
        # prefer research/substantive
        url_clean = link.split("?")[0].rstrip("/")
        if url_clean and url_clean not in seen_urls:
            candidates.append(url_clean)

    # de-dup preserving order, prefer arxiv/github/blog over news
    seen_c = set()
    deduped = []
    for u in candidates:
        if u not in seen_c:
            seen_c.add(u)
            deduped.append(u)

    # Score: arxiv > github > academic/research domains > others
    def score_url(u):
        if "arxiv.org" in u: return 3
        if "github.com" in u and "/research" not in u: return 2
        if any(d in u for d in ["research","paper","blog","huggingface","openai.com","anthropic.com","deepmind","nature.com","science.org"]): return 2
        return 1

    deduped.sort(key=score_url, reverse=True)
    return deduped[:4]  # top 4

citation_sources_in_picks = [p for p in saved_picks if p["source"] in CITATION_SOURCES]
total_citations = 0

for pick in citation_sources_in_picks:
    cited_urls = extract_citations(pick)
    for cu in cited_urls:
        if cu in seen_urls:
            continue
        parsed_path = cu.rsplit("/", 1)[-1][:60] or cu
        ok = rw_save({
            "url": cu,
            "title": parsed_path,
            "summary": f"Cited in '{pick['title'][:60]}' by {pick['source']}",
            "tags": ["AI Daily", f"Cited from {pick['source']}"],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        }, f"citation:{cu[:40]}")
        if ok:
            seen_urls.add(cu)
            citation_results.append(cu)
            total_citations += 1
        time.sleep(0.2)

print(f"Citations saved: {total_citations}", file=sys.stderr)

# ── Step 14: Update seen.json ─────────────────────────────────────────────────
now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
cutoff_14 = datetime.now(timezone.utc) - timedelta(days=14)

new_entries = [{"url": p["url"], "shipped_at": now_iso} for p in saved_picks]
new_entries += [{"url": cu, "shipped_at": now_iso} for cu in citation_results]
# also brief
new_entries.append({"url": brief_url, "shipped_at": now_iso})

existing = []
for row in seen_data:
    try:
        ts = datetime.fromisoformat(row["shipped_at"].replace("Z", "+00:00"))
        if ts > cutoff_14:
            existing.append(row)
    except:
        existing.append(row)

merged = new_entries + existing
merged.sort(key=lambda r: r["shipped_at"], reverse=True)

with open("seen.json", "w") as f:
    json.dump(merged, f, indent=2)
print(f"seen.json updated with {len(new_entries)} new entries", file=sys.stderr)

# ── Summary output ─────────────────────────────────────────────────────────────
print(json.dumps({
    "picks": len(saved_picks),
    "citations": total_citations,
    "slug": slug,
    "brief_path": brief_path,
}))
