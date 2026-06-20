#!/usr/bin/env python3
"""Fetch candidate articles from configured RSS sources, filtering already-seen URLs."""

import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests

SEEN_FILE = Path("seen.json")
LOOKBACK_DAYS = 3

SOURCES = [
    # CITATION_SOURCES — newsletter/blog voices
    {"name": "Ethan Mollick",              "url": "https://www.oneusefulthing.org/feed",                                       "weight": 1.2, "cluster": "builder-methodology"},
    {"name": "Zvi Mowshowitz",             "url": "https://thezvi.substack.com/feed",                                          "weight": 1.2, "cluster": "governance-workforce"},
    {"name": "Pragmatic Engineer",         "url": "https://newsletter.pragmaticengineer.com/feed",                              "weight": 1.2, "cluster": "builder-methodology"},
    {"name": "Latent Space",               "url": "https://www.latent.space/feed",                                              "weight": 1.2, "cluster": "agentic-systems"},
    {"name": "Everyday AI",                "url": "https://www.everydayai.com/feed",                                            "weight": 1.1, "cluster": "enterprise-deployment"},
    {"name": "Andrej Karpathy",            "url": "https://karpathy.github.io/feed.xml",                                        "weight": 1.2, "cluster": "frontier-models"},
    {"name": "Stratechery",                "url": "https://stratechery.com/feed/",                                              "weight": 1.1, "cluster": "capital-compute"},
    # General AI news
    {"name": "The Verge AI",               "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",          "weight": 1.0, "cluster": "frontier-models"},
    {"name": "TechCrunch AI",              "url": "https://techcrunch.com/category/artificial-intelligence/feed/",              "weight": 0.9, "cluster": "capital-compute"},
    {"name": "MIT Technology Review",      "url": "https://www.technologyreview.com/feed/",                                     "weight": 1.0, "cluster": "ai-for-science"},
    {"name": "Ars Technica",               "url": "https://feeds.arstechnica.com/arstechnica/index",                            "weight": 0.9, "cluster": "frontier-models"},
    {"name": "VentureBeat AI",             "url": "https://venturebeat.com/category/ai/feed/",                                  "weight": 0.9, "cluster": "enterprise-deployment"},
    {"name": "Wired AI",                   "url": "https://www.wired.com/feed/tag/artificial-intelligence/rss",                 "weight": 0.9, "cluster": "governance-workforce"},
    {"name": "Nature AI",                  "url": "https://www.nature.com/subjects/artificial-intelligence.rss",                "weight": 1.1, "cluster": "ai-for-science"},
    {"name": "Science Daily AI",           "url": "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml","weight": 1.0, "cluster": "ai-for-science"},
    {"name": "The Batch",                  "url": "https://www.deeplearning.ai/the-batch/feed/",                                "weight": 1.0, "cluster": "builder-methodology"},
    {"name": "AI Business",               "url": "https://aibusiness.com/rss.xml",                                             "weight": 0.9, "cluster": "enterprise-deployment"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DailyAIReader/1.0; research)"
}


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            return {entry["url"] for entry in data if isinstance(entry, dict) and "url" in entry}
        except Exception:
            return set()
    return set()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def fetch_feed(source: dict, seen: set, cutoff: datetime) -> list:
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"[WARN] {source['name']}: {e}", file=sys.stderr)
        return []

    results = []
    for entry in feed.entries[:40]:
        url = (entry.get("link") or "").strip()
        if not url or url in seen:
            continue

        pub = None
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    pub = datetime(*val[:6], tzinfo=timezone.utc)
                    break
                except Exception:
                    pass

        if pub and pub < cutoff:
            continue

        title = strip_html(entry.get("title", "")).strip()
        if not title:
            continue

        summary = strip_html(
            entry.get("summary", "") or entry.get("description", "")
        )[:600]

        results.append({
            "url": url,
            "title": title,
            "source": source["name"],
            "weight": source["weight"],
            "cluster": source["cluster"],
            "published": pub.isoformat() if pub else None,
            "summary": summary,
        })

    return results


def main():
    seen = load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    candidates = []
    seen_in_run: set = set()

    for source in SOURCES:
        items = fetch_feed(source, seen, cutoff)
        for item in items:
            if item["url"] not in seen_in_run:
                seen_in_run.add(item["url"])
                candidates.append(item)
        time.sleep(0.3)

    json.dump(candidates, sys.stdout, indent=2, ensure_ascii=False)
    print(f"[INFO] {len(candidates)} candidates from {len(SOURCES)} sources", file=sys.stderr)


if __name__ == "__main__":
    main()
