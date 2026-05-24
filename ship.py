"""Execute steps 9-14 of the AI Reader pipeline: compose brief, save to Readwise, update seen.json."""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone
import zoneinfo

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
READWISE_BASE = "https://readwise.io/api/v3"
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}
CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space",
                    "Zvi Mowshowitz", "Pragmatic Engineer"}

prague = zoneinfo.ZoneInfo("Europe/Prague")
now_prague = datetime.now(prague)
SLUG = "AI_Daily_" + now_prague.strftime("%Y-%m-%d_%H%M")
DISPLAY_TS = now_prague.strftime("%A, %-d %B %Y %H:%M")
BRANCH = "claude/create-ai-daily-reader-gylCx"

# --- Picks definition ---
candidates = json.load(open("candidates.json"))

PICKS = [
    {
        "idx": 35, "title": "2026.21: The Data Center Veto",
        "url": "https://stratechery.com/2026/the-data-center-veto",
        "source": "Stratechery",
        "blurb": "Ben Thompson decodes this week's data center political economy and agent-era economics — why compute is becoming a sovereign bargaining chip.",
    },
    {
        "idx": 3, "title": "AI #169: New Knowledge",
        "url": "https://thezvi.wordpress.com/2026/05/21/ai-169-new-knowledge",
        "source": "Zvi Mowshowitz",
        "blurb": "Zvi's weekly synthesis covers GPT-next's historic Erdős proof, cross-lab capability assessment, and AI's emerging knowledge-creation loop.",
    },
    {
        "idx": 37, "title": "Did Google's AI agents really build an operating system for $916?",
        "url": "https://www.normaltech.ai/p/did-googles-ai-agents-really-build",
        "source": "AI Snake Oil",
        "blurb": "Independent evaluation shows Google's headline claim doesn't survive scrutiny — essential reading before trusting vendor AI productivity benchmarks.",
    },
    {
        "idx": 16, "title": "OpenAI GPT-next disproves 80-year-old Erdős planar unit distance problem",
        "url": "https://www.latent.space/p/ainews-openai-gpt-next-disproves",
        "source": "Latent Space",
        "blurb": "GPT-next produced a verified mathematical proof that eluded humans for 80 years — a concrete milestone for AI as research collaborator.",
    },
    {
        "idx": 2, "title": "Gemini 3.5 Flash Looks Good For How Fast It Is",
        "url": "https://thezvi.wordpress.com/2026/05/22/gemini-3-5-flash-looks-good-for-how-fast-it-is",
        "source": "Zvi Mowshowitz",
        "blurb": "Detailed capability analysis of Google's fastest production model; useful for evaluating latency-cost tradeoffs in enterprise AI deployments.",
    },
    {
        "idx": 15, "title": "Giving Agents Computers — Ivan Burazin, Daytona",
        "url": "https://www.latent.space/p/daytona",
        "source": "Latent Space",
        "blurb": "CEO interview: 74% MoM growth and 850K daily agent runs show real enterprise adoption of secure bare-metal sandboxes for agentic workflows.",
    },
    {
        "idx": 12, "title": "Specialization Beats Scale: A Strategic Variable Most AI Procurement Decisions Overlook",
        "url": "https://huggingface.co/blog/Dharma-AI/specialization-beats-scale",
        "source": "Hugging Face",
        "blurb": "Framework arguing specialized smaller models outperform frontier giants for domain tasks — actionable for enterprise AI procurement decisions.",
    },
    {
        "idx": 13, "title": "All Model Labs are now Agent Labs",
        "url": "https://www.latent.space/p/ainews-all-model-labs-are-now-agent",
        "source": "Latent Space",
        "blurb": "Every major model lab has repositioned as an agent platform — the product paradigm has shifted from text completion to autonomous action.",
    },
    {
        "idx": 55, "title": "Google I/O showed how the path for AI-driven science is shifting",
        "url": "https://www.technologyreview.com/2026/05/22/1137813/google-i-o-showed-how-the-path-for-ai-science-is-shifting",
        "source": "MIT Tech Review AI",
        "blurb": "Hassabis signals DeepMind's pivot toward AI-accelerated discovery; maps how life-science foundation models are entering production research pipelines.",
    },
    {
        "idx": 7, "title": "AdventHealth advances whole-person care with OpenAI",
        "url": "https://openai.com/index/adventhealth",
        "source": "OpenAI",
        "blurb": "Named healthcare deployment using ChatGPT for Healthcare to reduce administrative burden and streamline clinical workflows — pharma-adjacent proof point.",
    },
    {
        "idx": 4, "title": "The Pulse: Antigravity 2.0 takes 'IDE' out of its new IDE",
        "url": "https://newsletter.pragmaticengineer.com/p/the-pulse-antigravity-20-takes-ide",
        "source": "Pragmatic Engineer",
        "blurb": "Pragmatic Engineer dissects Google's AI coding tool redesign and developer backlash — signals where the agentic development toolchain is heading.",
    },
    {
        "idx": 33, "title": "OpenAI burned through $1.22 per dollar earned (Q1 2026)",
        "url": "https://the-decoder.com/openai-burned-through-1-22-per-dollar-earned-even-after-stripping-out-stock-based-compensation",
        "source": "The Decoder",
        "blurb": "Hard Q1 financials: $5.7B revenue but losses still outpace income — the unit economics of frontier AI development remain deeply negative.",
    },
]

EDITOR_NOTE = """<p>The strongest thread this run: the AI-as-researcher story gained hard evidence. GPT-next produced a verified proof of the 80-year-old Erdős planar unit distance conjecture (items 4 and 2), and MIT Tech Review maps how DeepMind is repositioning explicitly for AI-accelerated science (9). For a pharma IT executive watching foundation models in biology, this is a capability signal worth tracking into your 2027 R&D horizon.</p>
<p>Two structural shifts run through the rest of the brief. First, every major model lab has repositioned as an agent platform (8, 6) — the question is no longer whether your workflows run on agents but when and at what infrastructure cost. Stratechery's data center veto piece (1) and OpenAI's Q1 financials (12) together map the capital and geopolitical architecture that will determine what enterprise AI actually costs over the next 18 months.</p>
<p>For your procurement desk: the AI Snake Oil evaluation of Google's $916 OS claim (3) and the Hugging Face specialization-vs-scale framework (7) are worth handing to your architecture team before the next vendor briefing. The Pragmatic Engineer's IDE piece (11) is the builder-side complement — the agentic development toolchain is still in violent flux.</p>"""


def api_post(payload, retries=4):
    url = f"{READWISE_BASE}/save/"
    data = json.dumps(payload).encode()
    delays = [3, 6, 12, 24]
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = delays[attempt]
                print(f"  429 rate limit, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
            else:
                body = ""
                try:
                    body = e.read().decode()[:200]
                except Exception:
                    pass
                return e.code, {"error": str(e), "body": body}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delays[attempt])
            else:
                return 0, {"error": str(e)}
    return 0, {"error": "max retries"}


# Step 9: Compose brief HTML
def build_html():
    citation_note = lambda s: " · citations to follow" if s in CITATION_SOURCES else ""
    items_html = ""
    for i, p in enumerate(PICKS, 1):
        cs = citation_note(p["source"])
        items_html += f"""
<h3>{i}. {p['title']}</h3>
<div class="meta">{p['source']}{cs}</div>
<p class="blurb">{p['blurb']}</p>
<p><a href="{p['url']}">Read source →</a></p>"""

    return f"""<html><head><meta charset="utf-8"><title>AI Daily — {DISPLAY_TS}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>AI Daily — {DISPLAY_TS} (Prague)</h1>
<div class="editor">{EDITOR_NOTE}</div><hr/>
{items_html}
</body></html>"""


html = build_html()

# Step 10: Save locally
os.makedirs("briefs", exist_ok=True)
brief_path = f"briefs/{SLUG}.html"
with open(brief_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Saved brief to {brief_path}", file=sys.stderr)

# Step 11: Save brief to Readwise
print("Posting brief...", file=sys.stderr)
status, resp = api_post({
    "url": f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/{BRANCH}/briefs/{SLUG}.html",
    "html": html,
    "title": f"AI Daily — {DISPLAY_TS}",
    "author": "AI Daily Pipeline",
    "tags": ["AI Daily", "Brief"],
    "location": "new",
    "category": "article",
    "should_clean_html": False,
    "saved_using": "AI Daily routine",
})
if status not in (200, 201):
    print(f"ERROR posting brief: {status} {resp}", file=sys.stderr)
    sys.exit(1)
print(f"Brief posted OK (HTTP {status})", file=sys.stderr)
time.sleep(0.5)

# Track saved URLs for seen.json
now_utc = datetime.now(timezone.utc)
saved_urls = []

# Step 12: Save each pick
picks_saved = 0
picks_failed = 0
for p in PICKS:
    status, resp = api_post({
        "url": p["url"],
        "title": p["title"],
        "summary": p["blurb"],
        "tags": ["AI Daily", p["source"]],
        "location": "new",
        "category": "article",
        "saved_using": "AI Daily routine",
    })
    if status in (200, 201):
        picks_saved += 1
        saved_urls.append(p["url"])
        print(f"  OK [{p['source']}] {p['title'][:60]}", file=sys.stderr)
    else:
        picks_failed += 1
        print(f"  FAIL {status} [{p['source']}] {p['title'][:60]}: {resp}", file=sys.stderr)
    time.sleep(0.2)

print(f"Picks: {picks_saved} saved, {picks_failed} failed", file=sys.stderr)

# Step 13: Citations — fetch and extract from CITATION_SOURCES picks
# Load seen URLs to skip
try:
    existing_seen = {row["url"] for row in json.load(open("seen.json"))}
except Exception:
    existing_seen = set()
already_seen = existing_seen | set(saved_urls)

citation_picks = [p for p in PICKS if p["source"] in CITATION_SOURCES]
citations_saved = 0

# We'll do citation extraction via a separate script invocation to use WebFetch-like logic
# Write citation targets to a temp file for the agent to process
with open("citation_picks.json", "w") as f:
    json.dump(citation_picks, f, indent=2)

with open("already_seen.json", "w") as f:
    json.dump(list(already_seen), f)

# Step 14: Update seen.json
try:
    existing = json.load(open("seen.json"))
except Exception:
    existing = []

cutoff_dt = datetime.now(timezone.utc).replace(tzinfo=timezone.utc)
from datetime import timedelta
keep_cutoff = cutoff_dt - timedelta(days=14)

# Filter old entries
kept = []
for row in existing:
    try:
        shipped = datetime.fromisoformat(row.get("shipped_at","").replace("Z","+00:00"))
        if shipped >= keep_cutoff:
            kept.append(row)
    except Exception:
        kept.append(row)

shipped_at = now_utc.isoformat()
for url in saved_urls:
    kept.append({"url": url, "shipped_at": shipped_at})

# Sort descending
kept.sort(key=lambda x: x.get("shipped_at",""), reverse=True)

with open("seen.json", "w", encoding="utf-8") as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)

print(f"seen.json updated: {len(kept)} entries", file=sys.stderr)
print(f"PICKS_SAVED={picks_saved}")
print(f"PICKS_FAILED={picks_failed}")
print(f"BRIEF_SLUG={SLUG}")
