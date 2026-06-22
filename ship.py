#!/usr/bin/env python3
"""
ship.py - Post brief + picks to Readwise Reader, extract citations, update seen.json.
"""
import json, time, sys, os, re
from datetime import datetime, timezone
import urllib.request
import urllib.parse

READWISE_TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
SEEN_FILE = "seen.json"
BRANCH = "claude/intelligent-tesla-kkch81"
BRIEF_SLUG = "AI_Daily_2026-06-22_1510"
BRIEF_TITLE = "AI Daily — Monday, 22 June 2026 15:10"

CITATION_SOURCES = {"Ethan Mollick", "Andrej Karpathy", "Everyday AI", "Latent Space",
                     "Zvi Mowshowitz", "Pragmatic Engineer"}

PICKS = [
    {"url": "https://www.nature.com/articles/s42003-026-10497-1",
     "title": "Ovo, an open-source ecosystem for de novo protein design",
     "source": "Nature ML",
     "blurb": "Open-source Python toolkit enabling AI-guided generation of novel proteins from scratch — key infrastructure for drug discovery pipelines and virtual cell work."},
    {"url": "https://thezvi.substack.com/p/claude-fable-5-and-mythos-5-capabilities",
     "title": "Claude Fable 5 and Mythos 5: Capabilities",
     "source": "Zvi Mowshowitz",
     "blurb": "Deep capability analysis of Fable 5 and Mythos 5 delivered three days before the unprecedented US government-mandated withdrawal citing a critical jailbreak."},
    {"url": "https://openai.com/index/samsung-electronics-chatgpt-codex-deployment",
     "title": "Samsung Electronics brings ChatGPT and Codex to employees",
     "source": "OpenAI Blog",
     "blurb": "OpenAI's largest enterprise rollout — Samsung deploys ChatGPT Enterprise plus Codex to all employees worldwide, signalling generative AI at industrial scale."},
    {"url": "https://www.nature.com/articles/d41586-026-01954-2",
     "title": "Will AI spark a scientific renaissance — or a diffuse monoculture?",
     "source": "Nature ML",
     "blurb": "Nature asks whether AI accelerates scientific discovery or homogenises research directions — the defining strategic question for every pharma R&D leader."},
    {"url": "https://thezvi.substack.com/p/glm-52-is-the-new-best-open-model",
     "title": "GLM-5.2 Is The New Best Open Model",
     "source": "Zvi Mowshowitz",
     "blurb": "China's GLM-5.2 beats prior open-weight models on key benchmarks; Zvi provides evidence-based analysis of where the open frontier now sits."},
    {"url": "https://www.statnews.com/2026/06/22/sanofi-paulo-fontoura-houman-ashrafian-research-and-development/?utm_campaign=rss",
     "title": "Sanofi names new R&D head as it tries to jump-start pipeline",
     "source": "STAT News",
     "blurb": "Sanofi taps Xaira Therapeutics CMO as R&D chief — a direct signal that AI-native drug discovery talent is now running Big Pharma pipelines."},
    {"url": "https://techcrunch.com/2026/06/20/nobel-laureate-john-jumper-is-leaving-deepmind-for-rival-anthropic/",
     "title": "Nobel laureate John Jumper is leaving DeepMind for rival Anthropic",
     "source": "TechCrunch AI",
     "blurb": "AlphaFold's co-creator and Nobel prize winner leaves Google DeepMind for Anthropic — a seismic talent signal for both companies' biotech ambitions."},
    {"url": "https://stratechery.com/2026/apple-price-increases-apple-intelligence-and-the-e-u/",
     "title": "Apple Price Increases, Apple Intelligence and the E.U.",
     "source": "Stratechery",
     "blurb": "Stratechery on why Apple raises prices globally and withholds Apple Intelligence from the EU — regulatory arbitrage made explicit, not technical limitations."},
    {"url": "https://techcrunch.com/2026/06/19/encryption-spyware-and-now-mythos-history-shows-why-cyber-export-control-doesnt-work/",
     "title": "From PGP to Mythos: a brief history of export controls that didn't stop anyone",
     "source": "TechCrunch AI",
     "blurb": "Thirty years of software export controls have uniformly failed; the same structural logic applies to the US government's Anthropic model ban."},
    {"url": "https://simonwillison.net/2026/Jun/21/temporary-cloudflare-accounts/#atom-everything",
     "title": "Temporary Cloudflare Accounts for AI agents",
     "source": "Simon Willison",
     "blurb": "Cloudflare now provisions ephemeral scoped accounts for AI agents — builder-level infrastructure enabling stateful agentic workloads with auth isolation at the edge."},
    {"url": "https://techcrunch.com/2026/06/19/billionaire-ambani-wants-ai-in-every-call-app-and-home/",
     "title": "Billionaire Ambani wants AI in every call, app, and home",
     "source": "TechCrunch AI",
     "blurb": "Reliance integrates AI into telecom services for 500M+ users — the largest single-operator AI deployment footprint outside the US hyperscalers."},
    {"url": "https://www.statnews.com/2026/06/22/pharma-biotech-ma-boom-2026-deals-total-123-billion/?utm_campaign=rss",
     "title": "Pharma goes on a spending spree, snapping up biotechs in a hurry",
     "source": "STAT News",
     "blurb": "$123B in pharma acquisitions so far in 2026 — fastest deal pace in years, reshaping pipelines ahead of an AI-augmented R&D era."},
]


def api_post(payload, description=""):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://readwise.io/api/v3/save/",
        data=data,
        headers={
            "Authorization": f"Token {READWISE_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            return status, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        return e.code, body
    except Exception as e:
        return 0, str(e)


def fetch_article_links(url):
    """Fetch article body and extract external links."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 AI-Daily-Reader/1.0",
                     "Accept": "text/html,*/*"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Extract all href links
        links = re.findall(r'href=["\']([^"\']+)["\']', html)
        return links, html
    except Exception as e:
        print(f"  fetch_article_links error for {url}: {e}", file=sys.stderr)
        return [], ""


SOCIAL_PATTERNS = re.compile(
    r"twitter\.com|x\.com|threads\.net|mastodon\.|linkedin\.com/in|"
    r"instagram\.com|facebook\.com|youtube\.com/watch|tiktok\.com",
    re.I,
)
SPONSOR_PATTERNS = re.compile(
    r"utm_|affiliate|substack\.com/subscribe|substack\.com/refer|"
    r"substack\.com/sign-in|substack\.com/privacy|substack\.com/tos|"
    r"substack\.com/ccpa|substack\.com/@|/sign-in\?|/login\?|/signup\?|"
    r"/privacy$|/terms$|/tos$|/ccpa$|/cookie|"
    r"open\.spotify|podcasts\.apple|overcast\.fm|pocketcasts|buzzsprout|"
    r"anchor\.fm|podbean|feeds\.buzzsprout",
    re.I,
)


def is_substantive_external(link, source_domain):
    if not link.startswith("http"):
        return False
    if SOCIAL_PATTERNS.search(link):
        return False
    if SPONSOR_PATTERNS.search(link):
        return False
    # Skip source's own domain
    parsed = urllib.parse.urlparse(link)
    if source_domain and source_domain in parsed.netloc:
        return False
    # Prefer arXiv, GitHub (research), academic, named blogs
    return True


def extract_citations(pick, seen_urls):
    """Extract and save 2-4 substantive citations from a pick."""
    print(f"  Fetching citations from: {pick['url']}", file=sys.stderr)
    links, html = fetch_article_links(pick["url"])
    if not links:
        return []

    source_domain = urllib.parse.urlparse(pick["url"]).netloc.replace("www.", "")

    # Score links: arXiv > GitHub > .edu/.ac.uk > other
    def link_score(l):
        s = 0
        if "arxiv.org" in l:
            s += 10
        elif "github.com" in l and not "/issues" in l and not "/pulls" in l:
            s += 8
        elif any(x in l for x in [".edu/", ".ac.uk/", "research.", "papers.", "proceedings."]):
            s += 6
        elif any(x in l for x in ["blog.", "substack.com", "nature.com", "science.org"]):
            s += 4
        return s

    # Deduplicate and filter
    seen_in_citation = set()
    candidates = []
    for l in links:
        l = l.split("#")[0].rstrip("/")
        if not l or l in seen_in_citation or l in seen_urls:
            continue
        if not is_substantive_external(l, source_domain):
            continue
        score = link_score(l)
        if score > 0:
            seen_in_citation.add(l)
            candidates.append((score, l))

    # Sort by score, take top 4
    candidates.sort(key=lambda x: -x[0])
    top = [l for _, l in candidates[:4]]

    saved = []
    for cited_url in top:
        # Derive a short title
        parsed = urllib.parse.urlparse(cited_url)
        path_tail = parsed.path.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")[:60]
        if "arxiv.org" in cited_url:
            title_guess = f"arXiv: {path_tail}"
        elif "github.com" in cited_url:
            parts = parsed.path.strip("/").split("/")
            title_guess = "/".join(parts[:2]) if len(parts) >= 2 else path_tail
        else:
            title_guess = f"{parsed.netloc}: {path_tail}" if path_tail else parsed.netloc

        payload = {
            "url": cited_url,
            "title": title_guess,
            "summary": f"Cited in '{pick['title']}' by {pick['source']}",
            "tags": ["AI Daily", f"Cited from {pick['source']}"],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        }
        status, err = api_post(payload, f"citation from {pick['source']}")
        if status in (200, 201):
            saved.append(cited_url)
            print(f"    Citation saved ({status}): {cited_url[:80]}", file=sys.stderr)
        else:
            print(f"    Citation failed ({status}): {cited_url[:80]} — {err}", file=sys.stderr)
        time.sleep(0.2)

    return saved


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return []
    with open(SEEN_FILE) as f:
        return json.load(f)


def save_seen(seen_list):
    # Drop entries older than 14 days
    cutoff = datetime.now(timezone.utc).timestamp() - 14 * 86400
    def keep(item):
        try:
            ts = datetime.fromisoformat(item["shipped_at"].replace("Z", "+00:00")).timestamp()
            return ts >= cutoff
        except Exception:
            return True
    filtered = [item for item in seen_list if keep(item)]
    filtered.sort(key=lambda x: x.get("shipped_at", ""), reverse=True)
    with open(SEEN_FILE, "w") as f:
        json.dump(filtered, f, indent=2)


def main():
    seen_list = load_seen()
    seen_urls = {item["url"] for item in seen_list}
    now_iso = datetime.now(timezone.utc).isoformat()
    saved_urls = []

    # Step 11: Save the brief
    with open(f"briefs/{BRIEF_SLUG}.html") as f:
        brief_html = f.read()

    brief_payload = {
        "url": f"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/{BRANCH}/briefs/{BRIEF_SLUG}.html",
        "html": brief_html,
        "title": BRIEF_TITLE,
        "tags": ["AI Daily", "Brief"],
        "location": "new",
        "category": "article",
        "should_clean_html": False,
        "author": "AI Daily",
        "saved_using": "AI Daily routine",
    }
    status, err = api_post(brief_payload, "brief")
    if status not in (200, 201):
        print(f"FATAL: brief save failed with {status}: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"Brief saved: HTTP {status}", file=sys.stderr)
    saved_urls.append(brief_payload["url"])

    # Step 12: Save each pick
    pick_saved = []
    for pick in PICKS:
        payload = {
            "url": pick["url"],
            "title": pick["title"],
            "summary": pick["blurb"],
            "tags": ["AI Daily", pick["source"]],
            "location": "new",
            "category": "article",
            "saved_using": "AI Daily routine",
        }
        status, err = api_post(payload)
        if status in (200, 201):
            pick_saved.append(pick)
            saved_urls.append(pick["url"])
            print(f"Pick saved ({status}): {pick['title'][:60]}", file=sys.stderr)
        else:
            print(f"Pick FAILED ({status}): {pick['title'][:60]} — {err}", file=sys.stderr)
        time.sleep(0.2)

    # Step 13: Citations from CITATION_SOURCES picks
    citation_count = 0
    for pick in pick_saved:
        if pick["source"] in CITATION_SOURCES:
            cited = extract_citations(pick, seen_urls | set(saved_urls))
            saved_urls.extend(cited)
            citation_count += len(cited)

    # Step 14: Update seen.json
    shipped_at = now_iso
    for url in saved_urls:
        if url not in seen_urls:
            seen_list.append({"url": url, "shipped_at": shipped_at})
            seen_urls.add(url)
    save_seen(seen_list)

    print(f"\nRESULT: {len(pick_saved)} articles + {citation_count} citations + 1 brief", file=sys.stderr)
    print(f"{len(pick_saved)}|{citation_count}")


if __name__ == "__main__":
    main()
