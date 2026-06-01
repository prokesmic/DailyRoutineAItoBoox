"""Execute pipeline steps 9-14: build brief, save to Readwise, update seen.json."""
import json, time, sys, os
from datetime import datetime, timezone

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
HEADERS = {"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"}
BASE = "https://readwise.io/api/v3"
BRIEF_SLUG = "AI_Daily_2026-06-01_1511"
TIMESTAMP = "Monday, 1 June 2026 15:11"
CITATION_SOURCES = {"Ethan Mollick","Andrej Karpathy","Everyday AI","Latent Space","Zvi Mowshowitz","Pragmatic Engineer"}

import httpx

# ---------- PICKS ----------
picks = [
    {
        "source": "Interconnects",
        "title": "Open and closed models are on different exponentials",
        "url": "https://www.interconnects.ai/p/open-and-closed-models-are-on-different",
        "blurb": "Meta, Mistral, and DeepSeek compress costs while GPT-4/Claude extend capability leads — the diverging curves change enterprise multi-year AI bets.",
    },
    {
        "source": "Zvi Mowshowitz",
        "title": "Claude Opus 4.8: The System Card",
        "url": "https://thezvi.wordpress.com/2026/05/29/claude-opus-4-8-the-system-card",
        "blurb": "Zvi dissects Opus 4.8's system card: autonomy thresholds, hardcoded refusals, and what the model-spec evolution signals about frontier safety direction.",
    },
    {
        "source": "Simon Willison",
        "title": "How we contain Claude across products",
        "url": "https://simonwillison.net/2026/May/30/how-we-contain-claude/",
        "blurb": "Anthropic's containment architecture — trust hierarchies, operator permissions, user overrides — is essential governance reading for any enterprise deployment team.",
    },
    {
        "source": "Latent Space",
        "title": "[AINews] Founders and Forward Deployed Engineers",
        "url": "https://www.latent.space/p/ainews-founders-and-forward-deployed",
        "blurb": "The emerging 'Forward Deployed Engineer' role: part implementation, part change management, the enterprise AI translator function organizations are inventing on the fly.",
    },
    {
        "source": "Lenny's Newsletter",
        "title": "A rational conversation on where AI is actually going | Benedict Evans",
        "url": "https://www.lennysnewsletter.com/p/a-rational-conversation-on-where",
        "blurb": "Benedict Evans maps where productivity gains are real, where extrapolation is speculative, and what timelines executives should actually calibrate to.",
    },
    {
        "source": "HN (254 pts)",
        "title": "ChatGPT for Google Sheets exfiltrates workbooks",
        "url": "https://www.promptarmor.com/resources/gpt-for-google-sheets-data-exfiltration",
        "blurb": "Prompt injection via a Google Sheets AI plugin silently exfiltrates spreadsheet contents — concrete exploit, not theoretical, with direct enterprise data-governance implications.",
    },
    {
        "source": "TechCrunch AI",
        "title": "Does your CEO have AI psychosis? Aaron Levie thinks most of them do.",
        "url": "https://techcrunch.com/podcast/does-your-ceo-have-ai-psychosis-aaron-levie-thinks-most-of-them-do",
        "blurb": "Box CEO Aaron Levie names the pattern: executives over-indexing on AI disruption timelines, driving misdirected org changes and talent exits.",
    },
    {
        "source": "The Decoder",
        "title": "Terence Tao argues AI could bring division of labor to math for the first time in history",
        "url": "https://the-decoder.com/terence-tao-argues-ai-could-bring-division-of-labor-to-math-for-the-first-time-in-history",
        "blurb": "Fields Medal winner argues AI enables mathematical specialization at scale — a frame that applies directly to AI-for-science and pharma discovery pipelines.",
    },
    {
        "source": "The Decoder",
        "title": "AI search agents often confirm what they already know instead of actually researching the web",
        "url": "https://the-decoder.com/ai-search-agents-often-confirm-what-they-already-know-instead-of-actually-researching-the-web",
        "blurb": "Research documents AI search agents exhibiting confirmation bias — retrieving evidence for prior beliefs rather than independent search, a critical reliability failure mode.",
    },
    {
        "source": "TechCrunch AI",
        "title": "Cognition's Scott Wu says AI coding agents shouldn't replace humans",
        "url": "https://techcrunch.com/2026/05/29/cognitions-scott-wu-says-ai-coding-agents-shouldnt-replace-humans",
        "blurb": "Cognition CEO Scott Wu's calibration: agents as force-multipliers, not replacements — and why getting the framing wrong leads to poor adoption and brittle systems.",
    },
    {
        "source": "TechCrunch AI",
        "title": "After Nvidia's $20B not-acqui-hire, AI chip startup Groq reportedly raising $650M",
        "url": "https://techcrunch.com/2026/05/29/after-nvidias-20b-not-acqui-hire-ai-chip-startup-groq-reportedly-raising-650m",
        "blurb": "Nvidia's $20B arrangement with Groq restructures inference compute; the $650M raise signals Groq's bet on a differentiated position in the chip race.",
    },
    {
        "source": "The Decoder",
        "title": "Anthropic bans AI tools during job interviews to see how candidates actually think",
        "url": "https://the-decoder.com/anthropic-bans-ai-tools-during-job-interviews-to-see-how-candidates-actually-think",
        "blurb": "Anthropic's named policy banning AI in interviews signals a real tension: assessing genuine reasoning vs. tool fluency as hiring norms diverge across the industry.",
    },
]

EDITOR_NOTE = """<p>Two pieces this run are in direct conversation: Interconnects' structural analysis of open vs. closed model exponentials and Zvi's breakdown of the Opus 4.8 system card both ask what to expect from frontier AI — but from different angles. Interconnects argues the curves aren't parallel; that matters for any enterprise making multi-year infrastructure bets. Meanwhile, Anthropic's containment architecture write-up is required reading for anyone thinking through deployment governance — the pharma GxP framing writes itself.</p>
<p>Three items converge on workforce reality: Aaron Levie's "AI psychosis" diagnosis of executive behavior, Anthropic's decision to ban AI from their own hiring process, and the Latent Space piece on the Forward Deployed Engineer role emerging as the enterprise AI translator function. The ChatGPT-for-Sheets exfiltration finding is the week's sharpest enterprise-security wake-up call. Terence Tao on AI and the division of labor in mathematics earns its place as the long-read — with a direct line to pharma discovery acceleration.</p>"""

# Build HTML
def citation_note(pick):
    return " &middot; <em>citations to follow</em>" if pick["source"] in CITATION_SOURCES else ""

items_html = ""
for i, p in enumerate(picks, 1):
    items_html += f"""<h3>{i}. {p['title']}</h3>
<div class="meta">{p['source']}{citation_note(p)}</div>
<p class="blurb">{p['blurb']}</p>
<p><a href="{p['url']}">Read source →</a></p>
"""

BRIEF_HTML = f"""<html><head><meta charset="utf-8"><title>AI Daily — {TIMESTAMP}</title>
<style>body{{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}}
h1{{font-size:1.6em}} h3{{margin:1.5em 0 .2em;font-size:1.1em}}
.meta{{color:#666;font-size:.9em;font-style:italic}}
.blurb{{color:#333;margin:.3em 0 .5em}}
.editor{{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}}
a{{color:#000}}</style></head><body>
<h1>AI Daily — {TIMESTAMP} (Prague)</h1>
<div class="editor">{EDITOR_NOTE}</div><hr/>
{items_html}
</body></html>"""

# Step 10: Save brief locally
os.makedirs("briefs", exist_ok=True)
brief_path = f"briefs/{BRIEF_SLUG}.html"
with open(brief_path, "w", encoding="utf-8") as f:
    f.write(BRIEF_HTML)
print(f"Brief saved: {brief_path}", file=sys.stderr)

# Load seen.json
seen_urls = set()
seen_entries = []
if os.path.exists("seen.json"):
    try:
        seen_entries = json.load(open("seen.json"))
        seen_urls = {e["url"] for e in seen_entries}
    except:
        pass

def save_to_reader(payload, label="item"):
    try:
        r = httpx.post(f"{BASE}/save/", headers=HEADERS, json=payload, timeout=30)
        if r.status_code in (200, 201):
            return True
        else:
            print(f"WARN: {label} status {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"ERR: {label}: {e}", file=sys.stderr)
        return False

# Step 11: Save brief to Readwise
brief_url = f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/create-ai-daily-reader-gylCx/briefs/{BRIEF_SLUG}.html"
brief_payload = {
    "url": brief_url,
    "html": BRIEF_HTML,
    "title": f"AI Daily — {TIMESTAMP}",
    "author": "AI Daily routine",
    "tags": ["AI Daily", "Brief"],
    "location": "new",
    "category": "article",
    "should_clean_html": False,
    "saved_using": "AI Daily routine"
}
ok = save_to_reader(brief_payload, "brief")
if not ok:
    print("ERROR: Failed to save brief — stopping.", file=sys.stderr)
    sys.exit(1)
print("Brief saved to Readwise.", file=sys.stderr)

# Step 12: Save each pick
saved_picks = []
for p in picks:
    url = p["url"]
    payload = {
        "url": url,
        "title": p["title"],
        "summary": p["blurb"],
        "tags": ["AI Daily", p["source"]],
        "location": "new",
        "category": "article",
        "saved_using": "AI Daily routine"
    }
    ok = save_to_reader(payload, p["title"][:40])
    if ok:
        saved_picks.append(p)
    time.sleep(0.2)

print(f"Saved {len(saved_picks)}/{len(picks)} picks.", file=sys.stderr)

# Step 13: Extract citations from CITATION_SOURCE picks
# We'll do this via WebFetch in a separate step
# For now, mark which picks need citations
citation_picks = [p for p in saved_picks if p["source"] in CITATION_SOURCES]
print(f"Citation picks to process: {[p['source'] for p in citation_picks]}", file=sys.stderr)

# Step 14: Update seen.json
now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
cutoff_dt = datetime.now(timezone.utc).replace(tzinfo=None)
from datetime import timedelta
cutoff_str = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat().replace("+00:00","Z")

new_entries = []
for e in seen_entries:
    if e.get("shipped_at","") > cutoff_str:
        new_entries.append(e)

for p in saved_picks:
    url = p["url"]
    if url not in seen_urls:
        new_entries.append({"url": url, "shipped_at": now_iso})
        seen_urls.add(url)

new_entries.sort(key=lambda x: x.get("shipped_at",""), reverse=True)
with open("seen.json", "w") as f:
    json.dump(new_entries, f, indent=2)

print(f"seen.json updated: {len(new_entries)} entries.", file=sys.stderr)

# Output counts for main script
print(json.dumps({
    "picks": len(saved_picks),
    "citation_picks": [p["url"] for p in citation_picks],
    "citation_sources": [p["source"] for p in citation_picks]
}))
