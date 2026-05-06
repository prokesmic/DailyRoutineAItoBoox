#!/usr/bin/env python3
"""
fetch.py — pull fresh AI-news candidates from RSS/Atom feeds, filter against seen.json.
Uses stdlib xml.etree + requests (no feedparser).
Output: JSON array of candidate dicts to stdout.
"""
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

SEEN_FILE = Path(__file__).parent / "seen.json"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

# (feed_url, source_label, weight)
FEEDS = [
    ("https://www.latent.space/feed", "Latent Space", 1.2),
    ("https://www.aidailybrief.com/feed", "AI Daily Brief", 1.2),
    ("https://www.aidailybrief.com/feed.xml", "AI Daily Brief", 1.2),
    ("https://everydayai.show/feed", "Everyday AI", 1.1),
    ("https://openai.com/blog/rss.xml", "OpenAI", 1.2),
    ("https://www.anthropic.com/rss", "Anthropic", 1.2),
    ("https://deepmind.google/discover/blog/rss/", "DeepMind", 1.2),
    ("https://ai.googleblog.com/feeds/posts/default", "Google AI Blog", 1.1),
    ("https://blogs.microsoft.com/ai/feed/", "Microsoft AI", 1.1),
    ("https://venturebeat.com/category/ai/feed/", "VentureBeat AI", 1.0),
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch AI", 0.9),
    ("https://a16z.com/feed/", "a16z", 1.1),
    ("https://www.technologyreview.com/topic/artificial-intelligence/feed", "MIT Tech Review AI", 1.0),
    ("https://jack-clark.net/feed/", "Import AI (Jack Clark)", 1.1),
    ("https://simonwillison.net/atom/everything/", "Simon Willison", 1.0),
    ("https://www.interconnects.ai/feed", "Interconnects AI", 1.1),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face", 1.0),
    ("https://bair.berkeley.edu/blog/feed.xml", "BAIR Blog", 1.1),
    ("https://www.semianalysis.com/feed", "SemiAnalysis", 1.1),
    ("https://www.biopharmadive.com/feeds/news/", "BioPharma Dive", 1.1),
    ("https://www.fiercebiotech.com/rss/xml", "Fierce Biotech", 1.0),
]

MAX_AGE_HOURS = 24
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIDaily/1.0)"}


def load_seen():
    if SEEN_FILE.exists():
        try:
            data = json.loads(SEEN_FILE.read_text())
            return {item["url"] for item in data if "url" in item}
        except Exception:
            return set()
    return set()


def strip_html(text):
    return " ".join(re.sub(r"<[^>]+>", " ", text or "").split())


def parse_dt(s):
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt)], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def text(el, path, ns=None):
    found = el.find(path, ns or NS)
    return (found.text or "").strip() if found is not None else ""


def parse_rss(root, source, weight, seen_urls, max_age_hours):
    items = []
    channel = root.find("channel")
    if channel is None:
        return items
    for item in channel.findall("item"):
        url = text(item, "link")
        if not url:
            url = text(item, "guid")
        url = url.strip()
        if not url or url in seen_urls:
            continue

        title = strip_html(text(item, "title"))
        summary = strip_html(
            text(item, "description") or text(item, "content:encoded", NS) or ""
        )[:600]

        pub_str = text(item, "pubDate") or text(item, "dc:date", NS)
        pub_dt = parse_dt(pub_str)
        if pub_dt:
            age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            if age_h > max_age_hours:
                continue
            published_at = pub_dt.isoformat()
        else:
            published_at = datetime.now(timezone.utc).isoformat()

        items.append({
            "url": url,
            "title": title,
            "source": source,
            "published_at": published_at,
            "summary": summary,
            "weight": weight,
        })
    return items


def parse_atom(root, source, weight, seen_urls, max_age_hours):
    items = []
    for entry in root.findall("atom:entry", NS):
        url = ""
        for link in entry.findall("atom:link", NS):
            rel = link.get("rel", "alternate")
            if rel in ("alternate", ""):
                url = link.get("href", "")
                break
        if not url:
            url = text(entry, "atom:id", NS)
        url = url.strip()
        if not url or url in seen_urls:
            continue

        title = strip_html(text(entry, "atom:title", NS))
        summary = strip_html(
            text(entry, "atom:summary", NS) or text(entry, "atom:content", NS) or ""
        )[:600]

        pub_str = text(entry, "atom:published", NS) or text(entry, "atom:updated", NS)
        pub_dt = parse_dt(pub_str)
        if pub_dt:
            age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            if age_h > max_age_hours:
                continue
            published_at = pub_dt.isoformat()
        else:
            published_at = datetime.now(timezone.utc).isoformat()

        items.append({
            "url": url,
            "title": title,
            "source": source,
            "published_at": published_at,
            "summary": summary,
            "weight": weight,
        })
    return items


def fetch_feed(feed_url, source, weight, seen_urls):
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        tag = root.tag.lower()
        if "rss" in tag or root.tag == "rss":
            return parse_rss(root, source, weight, seen_urls, MAX_AGE_HOURS)
        if "feed" in tag or "atom" in tag:
            return parse_atom(root, source, weight, seen_urls, MAX_AGE_HOURS)
        # Try both
        items = parse_rss(root, source, weight, seen_urls, MAX_AGE_HOURS)
        if not items:
            items = parse_atom(root, source, weight, seen_urls, MAX_AGE_HOURS)
        return items
    except Exception as e:
        print(f"Warning: {source} ({feed_url}): {e}", file=sys.stderr)
        return []


def main():
    seen_urls = load_seen()
    candidates = []
    seen_in_run = set()

    for feed_url, source, weight in FEEDS:
        for item in fetch_feed(feed_url, source, weight, seen_urls):
            if item["url"] not in seen_in_run:
                seen_in_run.add(item["url"])
                candidates.append(item)

    candidates.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    print(json.dumps(candidates, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
