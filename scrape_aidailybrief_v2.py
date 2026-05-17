#!/usr/bin/env python3
"""Scrape show-note links from the last 50 episodes of The AI Daily Brief."""

import json
import re
import time
import urllib.request
import urllib.parse

EPISODE_URLS = [
    # page 1
    "https://aidailybrief.beehiiv.com/p/google-s-big-ai-test-comes-next-week",
    "https://aidailybrief.beehiiv.com/p/rip-golden-age-of-agent-experimentation-2026-2026",
    "https://aidailybrief.beehiiv.com/p/in-defense-of-tokenmaxxing",
    "https://aidailybrief.beehiiv.com/p/towards-ai-that-can-actually-interact",
    "https://aidailybrief.beehiiv.com/p/the-best-way-to-talk-to-your-agents",
    "https://aidailybrief.beehiiv.com/p/suprise-elon-anthropic-team-up-reshapes-the-ai-race",
    "https://aidailybrief.beehiiv.com/p/who-cares-about-consumer-ai",
    "https://aidailybrief.beehiiv.com/p/why-openai-and-anthropic-are-becoming-consultants",
    "https://aidailybrief.beehiiv.com/p/is-ai-doom-going-out-of-style",
    "https://aidailybrief.beehiiv.com/p/the-week-ai-grew-up",
    "https://aidailybrief.beehiiv.com/p/harness-as-a-service",
    "https://aidailybrief.beehiiv.com/p/ai-lab-power-rankings",
    # page 2
    "https://aidailybrief.beehiiv.com/p/the-ai-subsidy-era-is-over",
    "https://aidailybrief.beehiiv.com/p/how-deepseek-v4-connects-to-the-us-power-grid",
    "https://aidailybrief.beehiiv.com/p/what-i-learned-testing-gpt-5-5",
    "https://aidailybrief.beehiiv.com/p/how-headless-agents-will-change-work",
    "https://aidailybrief.beehiiv.com/p/what-gpt-images-2-unlocks",
    "https://aidailybrief.beehiiv.com/p/how-apple-s-ai-strategy-changes-with-a-new-ceo",
    "https://aidailybrief.beehiiv.com/p/what-to-build-first-with-claude-design",
    "https://aidailybrief.beehiiv.com/p/how-to-use-opus-4-7-and-the-new-codex",
    "https://aidailybrief.beehiiv.com/p/ai-s-great-divergence",
    "https://aidailybrief.beehiiv.com/p/vibe-coding-gets-an-upgrade",
    "https://aidailybrief.beehiiv.com/p/ai-populism-turns-violent",
    "https://aidailybrief.beehiiv.com/p/harness-engineering-101",
    # page 3
    "https://aidailybrief.beehiiv.com/p/why-enterprise-ai-has-a-leadership-problem",
    "https://aidailybrief.beehiiv.com/p/all-of-ai-s-new-models-and-tools",
    "https://aidailybrief.beehiiv.com/p/should-we-be-scared-of-anthropic-s-mythos",
    "https://aidailybrief.beehiiv.com/p/openai-proposes-a-new-deal",
    "https://aidailybrief.beehiiv.com/p/the-calm-before-the-agi-storm",
    "https://aidailybrief.beehiiv.com/p/ai-build-week",
    "https://aidailybrief.beehiiv.com/p/anthropic-accidentally-revealed-their-most-powerful-model-ever",
    "https://aidailybrief.beehiiv.com/p/why-ai-needs-better-benchmarks",
    "https://aidailybrief.beehiiv.com/p/work-agi-is-the-only-agi-that-matters",
    "https://aidailybrief.beehiiv.com/p/modify-title-xxxxxxx-7914af860b5de9d1",
    "https://aidailybrief.beehiiv.com/p/the-coming-ai-rules-battle",
    "https://aidailybrief.beehiiv.com/p/every-ai-product-is-becoming-every-other-ai-product",
    # page 4
    "https://aidailybrief.beehiiv.com/p/what-people-really-want-from-ai",
    "https://aidailybrief.beehiiv.com/p/how-to-use-agent-skills",
    "https://aidailybrief.beehiiv.com/p/the-race-to-put-ai-agents-everywhere",
    "https://aidailybrief.beehiiv.com/p/a-guy-used-ai-to-cure-his-dog-s-cancer",
    "https://aidailybrief.beehiiv.com/p/pro-worker-ai",
    "https://aidailybrief.beehiiv.com/p/what-vibe-coding-is-turning-into",
    "https://aidailybrief.beehiiv.com/p/why-google-workspace-cli-is-such-a-big-deal",
    "https://aidailybrief.beehiiv.com/p/the-debate-over-anthropic-s-new-product-price-or-existential-dread",
    "https://aidailybrief.beehiiv.com/p/autoresearch-agent-loops-and-the-future-of-work",
    "https://aidailybrief.beehiiv.com/p/gpt-5-4-first-test-results",
    "https://aidailybrief.beehiiv.com/p/ai-is-officially-political",
    "https://aidailybrief.beehiiv.com/p/the-big-questions-that-will-decide-the-consumer-ai-war",
    # page 5 (first 2 to reach 50 total)
    "https://aidailybrief.beehiiv.com/p/the-rise-of-the-zero-human-company",
    "https://aidailybrief.beehiiv.com/p/the-month-ai-woke-up",
]

assert len(EPISODE_URLS) == 50, f"Expected 50 episodes, got {len(EPISODE_URLS)}"

# Domains/patterns to DROP (nav, social share buttons, podcast platforms)
DROP_PATTERNS = re.compile(
    r"beehiiv\.com|"
    r"open\.spotify\.com|"
    r"spotify\.com/episode|"
    r"podcasts\.apple\.com|"
    r"music\.apple\.com/.*podcast|"
    r"podcasts\.google\.com|"
    r"google\.com/podcasts|"
    r"overcast\.fm|"
    r"pocketcasts\.com|"
    r"castro\.fm|"
    r"stitcher\.com|"
    r"iheartradio\.com|"
    r"tunein\.com|"
    r"amazon\.com/music|"
    r"facebook\.com/sharer|"
    r"facebook\.com/share|"
    r"twitter\.com/intent|"
    r"x\.com/intent|"
    r"threads\.net/intent|"
    r"linkedin\.com/sharing|"
    r"fonts\.googleapis\.com|"
    r"fonts\.gstatic\.com|"
    r"media\.beehiiv\.com|"
    r"beehiiv-images-production\.s3\.amazonaws\.com",
    re.IGNORECASE,
)

def strip_utm(url):
    """Remove utm_* tracking parameters from a URL."""
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in qs.items() if not k.startswith("utm_")}
    new_query = urllib.parse.urlencode(filtered, doseq=True)
    clean = parsed._replace(query=new_query)
    return urllib.parse.urlunparse(clean)


def fetch_html(url, retries=3):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ERROR fetching {url}: {e}")
                return None
            time.sleep(2 ** attempt)


def extract_title(html):
    """Extract page title from <title> tag."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        # beehiiv titles often end with " | Publication Name"
        # keep the part before the last " | "
        if " | " in title:
            title = title.rsplit(" | ", 1)[0].strip()
        return title
    return None


def extract_links(html):
    """Extract all http href values from HTML."""
    # Match href="..." with http links
    return re.findall(r'href="(https?://[^"]+)"', html)


def is_keep_url(url):
    """Return True if this URL should be kept as a show-note link."""
    if not url or not url.startswith("http"):
        return False
    if DROP_PATTERNS.search(url):
        return False
    return True


def main():
    all_results = []
    global_seen_urls = set()  # deduplicate across all episodes
    episodes_processed = 0

    for i, ep_url in enumerate(EPISODE_URLS):
        print(f"[{i+1}/50] {ep_url}")
        html = fetch_html(ep_url)
        if not html:
            print("  Skipped (fetch failed)")
            continue

        title = extract_title(html) or ep_url.split("/p/")[-1].replace("-", " ").title()
        raw_links = extract_links(html)

        episode_links = []
        ep_seen = set()  # deduplicate within episode

        for raw_url in raw_links:
            # Unescape HTML entities (e.g. &amp; -> &)
            url = raw_url.replace("&amp;", "&")
            if not is_keep_url(url):
                continue
            clean_url = strip_utm(url)
            if clean_url in ep_seen:
                continue
            ep_seen.add(clean_url)

            episode_links.append(clean_url)

        print(f"  Title: {title!r}  |  Links: {len(episode_links)}")

        for url in episode_links:
            if url not in global_seen_urls:
                global_seen_urls.add(url)
                all_results.append({
                    "title": title,
                    "url": url,
                    "episode_url": ep_url,
                })

        episodes_processed += 1
        time.sleep(1.0)  # polite crawl delay

    out_path = "/home/user/DailyRoutineAItoBoox/aidailybrief_links.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDone. Wrote {len(all_results)} entries from {episodes_processed} episodes to {out_path}")


if __name__ == "__main__":
    main()
