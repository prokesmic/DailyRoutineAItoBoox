#!/usr/bin/env python3
"""Fetch AI news candidates from RSS feeds, filtered by seen.json."""

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import feedparser

SEEN_FILE = Path("seen.json")
LOOKBACK_HOURS = 48  # capture items published in the last 48 h

FEEDS = [
    # CITATION_SOURCES — get weight 1.2
    {"source": "Ethan Mollick", "url": "https://www.oneusefulthing.org/feed", "weight": 1.2},
    {"source": "Latent Space", "url": "https://www.latent.space/feed", "weight": 1.2},
    {"source": "Zvi Mowshowitz", "url": "https://thezvi.substack.com/feed", "weight": 1.2},
    {"source": "Pragmatic Engineer", "url": "https://newsletter.pragmaticengineer.com/feed", "weight": 1.2},
    {"source": "Everyday AI", "url": "https://pod.link/1555689396.rss", "weight": 1.15},
    # Other reader sources
    {"source": "Stratechery", "url": "https://stratechery.com/feed", "weight": 1.1},
    {"source": "The AI Daily Brief", "url": "https://feeds.megaphone.fm/thedailybrief", "weight": 1.05},
    # Aggregators / curated AI news
    {
        "source": "Hacker News",
        "url": "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+Anthropic+OR+OpenAI+OR+Gemini+OR+GPT&points=100",
        "weight": 1.0,
    },
    {
        "source": "Hacker News",
        "url": "https://hnrss.org/frontpage?q=machine+learning+OR+neural+network+OR+agents&points=100",
        "weight": 1.0,
    },
    {
        "source": "MIT Technology Review",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "weight": 0.95,
    },
    {"source": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "weight": 0.9},
    {"source": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "weight": 0.9},
    {"source": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "weight": 0.85},
    {"source": "ArXiv AI", "url": "https://arxiv.org/rss/cs.AI", "weight": 1.1},
    {"source": "ArXiv LG", "url": "https://arxiv.org/rss/cs.LG", "weight": 1.05},
]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def load_seen() -> set:
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text())
        return {item["url"] for item in data if "url" in item}
    except Exception:
        return set()


def strip_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()


def parse_date(entry) -> Optional[datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_feed(feed_info: dict, seen: set, cutoff: datetime) -> list:
    try:
        parsed = feedparser.parse(feed_info["url"])
    except Exception as exc:
        print(f"[WARN] fetch failed {feed_info['url']}: {exc}", file=sys.stderr)
        return []

    items = []
    for entry in parsed.entries[:40]:  # cap per feed
        url = entry.get("link", "").strip()
        if not url or url in seen:
            continue

        pub_date = parse_date(entry)
        if pub_date and pub_date < cutoff:
            continue

        raw_summary = getattr(entry, "summary", "") or ""
        summary = strip_html(raw_summary)[:600]

        items.append(
            {
                "url": url,
                "title": strip_html(entry.get("title", url))[:200],
                "source": feed_info["source"],
                "weight": feed_info["weight"],
                "published_at": pub_date.isoformat() if pub_date else None,
                "summary": summary,
            }
        )
    return items


def main():
    seen = load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    all_candidates: list = []
    emitted_urls: set = set(seen)

    for feed_info in FEEDS:
        items = fetch_feed(feed_info, emitted_urls, cutoff)
        for item in items:
            if item["url"] not in emitted_urls:
                emitted_urls.add(item["url"])
                all_candidates.append(item)
        time.sleep(0.4)

    # Sort newest first
    all_candidates.sort(key=lambda x: x.get("published_at") or "", reverse=True)

    print(json.dumps(all_candidates, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
