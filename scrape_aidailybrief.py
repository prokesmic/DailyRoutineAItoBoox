#!/usr/bin/env python3
"""Scrape show-note links from the last 50 episodes of The AI Daily Brief."""

import json
import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser

EPISODE_URLS = [
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
    # page 5 (first 2 to get to 50 total)
    "https://aidailybrief.beehiiv.com/p/the-rise-of-the-zero-human-company",
    "https://aidailybrief.beehiiv.com/p/the-month-ai-woke-up",
]

assert len(EPISODE_URLS) == 50, f"Expected 50, got {len(EPISODE_URLS)}"

# Domains/patterns to drop
DROP_DOMAINS = {
    "aidailybrief.beehiiv.com",
    "beehiiv.com",
    "spotify.com",
    "open.spotify.com",
    "podcasts.apple.com",
    "music.apple.com",
    "podcasts.google.com",
    "google.com/podcasts",
    "overcast.fm",
    "pocketcasts.com",
    "castro.fm",
    "stitcher.com",
    "iheartradio.com",
    "tunein.com",
    "amazon.com/music",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "t.me",
    "telegram.me",
}

DROP_PATTERNS = [
    r"spotify\.com",
    r"podcasts\.apple\.com",
    r"podcasts\.google\.com",
    r"google\.com/podcasts",
    r"overcast\.fm",
    r"pocketcasts\.com",
    r"castro\.fm",
    r"stitcher\.com",
    r"iheartradio\.com",
    r"beehiiv\.com",
    r"facebook\.com/(sharer|share)",
    r"twitter\.com/(intent|share)",
    r"x\.com/(intent|share)",
    r"instagram\.com",
    r"linkedin\.com",
    r"mailto:",
    r"javascript:",
    r"#$",
]
DROP_RE = re.compile("|".join(DROP_PATTERNS), re.IGNORECASE)


class LinkExtractor(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.in_body = False
        self.current_title = None
        self._in_title_tag = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title_tag = True
        if tag == "a":
            href = attrs_dict.get("href", "")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title_tag = False

    def handle_data(self, data):
        if self._in_title_tag and self.current_title is None:
            self.current_title = data.strip()


def fetch_url(url, retries=3):
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
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ERROR fetching {url}: {e}")
                return None
            time.sleep(2 ** attempt)


def is_drop_url(url):
    if not url or url.startswith("#") or url.startswith("mailto:") or url.startswith("javascript:"):
        return True
    if DROP_RE.search(url):
        return True
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")
    if not domain:
        return True
    return False


def extract_links_from_html(html, episode_url):
    parser = LinkExtractor(episode_url)
    try:
        parser.feed(html)
    except Exception:
        pass

    title = parser.current_title or episode_url.split("/p/")[-1].replace("-", " ").title()
    # Also extract via regex to catch JS-rendered or encoded hrefs
    regex_links = re.findall(r'href=["\']([^"\']+)["\']', html)
    all_links = list(set(parser.links + regex_links))

    # Also look for links inside JSON-LD or other inline data
    # beehiiv sometimes puts content links in data attributes
    data_links = re.findall(r'"url"\s*:\s*"(https?://[^"]+)"', html)
    all_links += data_links

    results = []
    seen = set()
    for link in all_links:
        link = link.strip()
        # Resolve relative URLs
        if link.startswith("//"):
            link = "https:" + link
        elif link.startswith("/"):
            link = "https://aidailybrief.beehiiv.com" + link

        if not link.startswith("http"):
            continue

        if is_drop_url(link):
            continue

        # Dedupe within this episode
        if link in seen:
            continue
        seen.add(link)

        results.append({
            "title": title,
            "url": link,
            "episode_url": episode_url,
        })

    return title, results


def main():
    all_results = []
    global_seen_urls = set()
    episodes_processed = 0

    for i, ep_url in enumerate(EPISODE_URLS):
        print(f"[{i+1}/50] Fetching {ep_url} ...")
        html = fetch_url(ep_url)
        if not html:
            print(f"  Skipping (no content)")
            continue

        title, links = extract_links_from_html(html, ep_url)
        print(f"  Title: {title!r}  |  Links found: {len(links)}")

        new_links = []
        for entry in links:
            url = entry["url"]
            if url not in global_seen_urls:
                global_seen_urls.add(url)
                new_links.append(entry)

        all_results.extend(new_links)
        episodes_processed += 1

        # Be polite
        time.sleep(1.0)

    out_path = "/home/user/DailyRoutineAItoBoox/aidailybrief_links.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDone. Wrote {len(all_results)} entries from {episodes_processed} episodes to {out_path}")


if __name__ == "__main__":
    main()
