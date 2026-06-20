#!/usr/bin/env python3
"""Fetch candidate articles from RSS sources using stdlib only."""

import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

SEEN_FILE = Path("seen.json")
LOOKBACK_DAYS = 3

SOURCES = [
    {"name": "Ethan Mollick",         "url": "https://www.oneusefulthing.org/feed",                                        "weight": 1.2, "cluster": "builder-methodology"},
    {"name": "Zvi Mowshowitz",        "url": "https://thezvi.substack.com/feed",                                           "weight": 1.2, "cluster": "governance-workforce"},
    {"name": "Pragmatic Engineer",    "url": "https://newsletter.pragmaticengineer.com/feed",                               "weight": 1.2, "cluster": "builder-methodology"},
    {"name": "Latent Space",          "url": "https://www.latent.space/feed",                                               "weight": 1.2, "cluster": "agentic-systems"},
    {"name": "Everyday AI",           "url": "https://www.everydayai.com/feed",                                             "weight": 1.1, "cluster": "enterprise-deployment"},
    {"name": "Andrej Karpathy",       "url": "https://karpathy.github.io/feed.xml",                                         "weight": 1.2, "cluster": "frontier-models"},
    {"name": "Stratechery",           "url": "https://stratechery.com/feed/",                                               "weight": 1.1, "cluster": "capital-compute"},
    {"name": "The Verge AI",          "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",           "weight": 1.0, "cluster": "frontier-models"},
    {"name": "TechCrunch AI",         "url": "https://techcrunch.com/category/artificial-intelligence/feed/",               "weight": 0.9, "cluster": "capital-compute"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/",                                      "weight": 1.0, "cluster": "ai-for-science"},
    {"name": "Ars Technica",          "url": "https://feeds.arstechnica.com/arstechnica/index",                             "weight": 0.9, "cluster": "frontier-models"},
    {"name": "VentureBeat AI",        "url": "https://venturebeat.com/category/ai/feed/",                                   "weight": 0.9, "cluster": "enterprise-deployment"},
    {"name": "Wired AI",              "url": "https://www.wired.com/feed/tag/artificial-intelligence/rss",                  "weight": 0.9, "cluster": "governance-workforce"},
    {"name": "Nature AI",             "url": "https://www.nature.com/subjects/artificial-intelligence.rss",                 "weight": 1.1, "cluster": "ai-for-science"},
    {"name": "Science Daily AI",      "url": "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml", "weight": 1.0, "cluster": "ai-for-science"},
    {"name": "The Batch",             "url": "https://www.deeplearning.ai/the-batch/feed/",                                 "weight": 1.0, "cluster": "builder-methodology"},
    {"name": "VentureBeat Enterprise","url": "https://venturebeat.com/category/enterprise/feed/",                           "weight": 0.9, "cluster": "enterprise-deployment"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DailyAIReader/1.0; research)"}
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            return {e["url"] for e in data if isinstance(e, dict) and "url" in e}
        except Exception:
            return set()
    return set()


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def parse_date(text: str) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:25], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        return None


def text(el, path: str, ns=NS) -> str:
    found = el.find(path, ns)
    return (found.text or "").strip() if found is not None and found.text else ""


def fetch_feed(source: dict, seen: set, cutoff: datetime) -> list:
    try:
        req = Request(source["url"], headers=HEADERS)
        with urlopen(req, timeout=20) as r:
            raw = r.read()
    except Exception as e:
        print(f"[WARN] {source['name']}: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(raw)
    except Exception as e:
        print(f"[WARN] XML parse {source['name']}: {e}", file=sys.stderr)
        return []

    results = []
    tag = root.tag.lower()

    if "feed" in tag:
        # Atom
        entries = root.findall("atom:entry", NS) or root.findall("{http://www.w3.org/2005/Atom}entry")
        for entry in entries[:40]:
            link_el = entry.find("atom:link[@rel='alternate']", NS) or entry.find("atom:link", NS)
            url = (link_el.get("href", "") if link_el is not None else "").strip()
            if not url or url in seen:
                continue
            title = strip_tags(text(entry, "atom:title"))
            pub_raw = text(entry, "atom:updated") or text(entry, "atom:published")
            pub = parse_date(pub_raw)
            if pub and pub < cutoff:
                continue
            summary = strip_tags(
                text(entry, "atom:summary") or
                text(entry, "atom:content") or
                text(entry, "content:encoded")
            )[:600]
            results.append({"url": url, "title": title, "source": source["name"],
                            "weight": source["weight"], "cluster": source["cluster"],
                            "published": pub.isoformat() if pub else None, "summary": summary})
    else:
        # RSS 2.0
        for item in root.iter("item"):
            url = (item.findtext("link") or "").strip()
            if not url:
                guid = item.find("guid")
                url = (guid.text or "").strip() if guid is not None else ""
            if not url or url in seen:
                continue
            title = strip_tags(item.findtext("title") or "").strip()
            if not title:
                continue
            pub_raw = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
            pub = parse_date(pub_raw)
            if pub and pub < cutoff:
                continue
            summary = strip_tags(
                item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                item.findtext("description") or ""
            )[:600]
            results.append({"url": url, "title": title, "source": source["name"],
                            "weight": source["weight"], "cluster": source["cluster"],
                            "published": pub.isoformat() if pub else None, "summary": summary})
            if len(results) >= 40:
                break

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
