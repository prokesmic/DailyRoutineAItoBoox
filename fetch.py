#!/usr/bin/env python3
"""Fetch AI articles from RSS feeds, filtering already-seen URLs. Outputs JSON to stdout."""
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import feedparser
    import requests
except ImportError as e:
    print(f"Missing dependency: {e}", file=sys.stderr)
    sys.exit(1)

FEEDS = [
    # Citation sources (higher weight)
    {"url": "https://www.oneusefulthing.org/feed", "source": "Ethan Mollick", "weight": 1.1},
    {"url": "https://www.latent.space/feed", "source": "Latent Space", "weight": 1.1},
    {"url": "https://thezvi.substack.com/feed", "source": "Zvi Mowshowitz", "weight": 1.1},
    {"url": "https://newsletter.pragmaticengineer.com/feed", "source": "Pragmatic Engineer", "weight": 1.0},
    # Everyday AI — try multiple known feed URLs
    {"url": "https://www.everydayai.com/feed", "source": "Everyday AI", "weight": 1.0},
    {"url": "https://feeds.buzzsprout.com/1946661.rss", "source": "Everyday AI", "weight": 1.0},
    # Andrej Karpathy — GitHub Pages blog
    {"url": "https://karpathy.github.io/feed.xml", "source": "Andrej Karpathy", "weight": 1.2},
    # Frontier labs — primary sources
    {"url": "https://openai.com/news/rss.xml", "source": "OpenAI", "weight": 1.1},
    {"url": "https://www.anthropic.com/rss.xml", "source": "Anthropic", "weight": 1.1},
    {"url": "https://research.google/blog/rss/", "source": "Google Research", "weight": 1.0},
    {"url": "https://ai.meta.com/blog/feed/", "source": "Meta AI", "weight": 1.0},
    {"url": "https://mistral.ai/news/rss.xml", "source": "Mistral AI", "weight": 1.0},
    {"url": "https://blogs.microsoft.com/ai/feed/", "source": "Microsoft AI", "weight": 0.9},
    # NVIDIA
    {"url": "https://blogs.nvidia.com/feed/", "source": "NVIDIA", "weight": 0.9},
    # Stratechery (free articles only)
    {"url": "https://stratechery.com/feed/", "source": "Stratechery", "weight": 1.0},
    # AI news aggregators
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch AI", "weight": 0.9},
    {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI", "weight": 0.9},
    {"url": "https://www.technologyreview.com/feed/", "source": "MIT Tech Review", "weight": 0.95},
    # Science / pharma adjacent
    {"url": "https://www.nature.com/natmachintell.rss", "source": "Nature Machine Intelligence", "weight": 1.0},
    {"url": "https://www.biorxiv.org/rss/category/bioinformatics+ai", "source": "bioRxiv AI", "weight": 0.95},
    # The Information (free articles)
    {"url": "https://www.theinformation.com/feed", "source": "The Information", "weight": 1.0},
    # LessWrong AI posts
    {"url": "https://www.lesswrong.com/feed.xml?view=curated", "source": "LessWrong", "weight": 0.9},
    # AI research blogs
    {"url": "https://huggingface.co/blog/feed.xml", "source": "Hugging Face", "weight": 0.95},
    {"url": "https://research.character.ai/feed", "source": "Character AI Research", "weight": 0.9},
]

MAX_ITEM_AGE_DAYS = 7
MAX_ITEMS_PER_FEED = 15


def load_seen() -> set:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path) as f:
            data = json.load(f)
        return {item["url"] for item in data if isinstance(item, dict) and "url" in item}
    except Exception as e:
        print(f"Warning: could not load seen.json: {e}", file=sys.stderr)
        return set()


def entry_published(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        ts = entry.get(field)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def fetch_feed(cfg: dict, seen: set, now: datetime) -> list:
    items = []
    try:
        parsed = feedparser.parse(cfg["url"], request_headers={"User-Agent": "AIDaily/1.0"})
        if parsed.bozo and not parsed.entries:
            print(f"  Feed error ({cfg['source']}): {getattr(parsed, 'bozo_exception', 'unknown')}", file=sys.stderr)
            return items
        for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
            url = (entry.get("link") or "").strip()
            if not url or url in seen:
                continue
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            pub = entry_published(entry)
            if pub:
                age_days = (now - pub).days
                if age_days > MAX_ITEM_AGE_DAYS:
                    continue
                pub_str = pub.isoformat()
            else:
                age_days = 0
                pub_str = now.isoformat()
            summary = (entry.get("summary") or entry.get("description") or "")[:600]
            # strip tags from summary
            import re
            summary = re.sub(r"<[^>]+>", " ", summary).strip()
            summary = re.sub(r"\s+", " ", summary)[:500]
            items.append({
                "url": url,
                "title": title,
                "source": cfg["source"],
                "weight": cfg["weight"],
                "summary": summary,
                "published_at": pub_str,
                "age_days": age_days,
            })
    except Exception as e:
        print(f"  Exception fetching {cfg['source']}: {e}", file=sys.stderr)
    return items


def main():
    seen = load_seen()
    now = datetime.now(timezone.utc)
    all_items: list = []
    seen_urls: set = set(seen)
    seen_sources: set = set()

    for cfg in FEEDS:
        # skip duplicate source already fetched with same source name
        source_key = cfg["source"] + cfg["url"]
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        print(f"Fetching {cfg['source']} …", file=sys.stderr)
        items = fetch_feed(cfg, seen_urls, now)
        for item in items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)
        time.sleep(0.4)

    all_items.sort(key=lambda x: x.get("age_days", 99))
    print(json.dumps(all_items, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
