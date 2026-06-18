#!/usr/bin/env python3
"""Fetch candidate articles from RSS/Atom feeds using stdlib only."""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from time import sleep
from xml.etree import ElementTree as ET

import requests

SEEN_FILE = "seen.json"
LOOKBACK_DAYS = 3

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}

FEEDS = [
    # CITATION_SOURCES — weight 1.2
    {"url": "https://www.oneusefulthing.org/feed", "source": "Ethan Mollick", "weight": 1.2},
    {"url": "https://karpathy.bearblog.dev/feed/", "source": "Andrej Karpathy", "weight": 1.2},
    {"url": "https://www.latent.space/feed", "source": "Latent Space", "weight": 1.2},
    {"url": "https://thezvi.substack.com/feed", "source": "Zvi Mowshowitz", "weight": 1.2},
    {"url": "https://newsletter.pragmaticengineer.com/feed", "source": "Pragmatic Engineer", "weight": 1.2},
    {"url": "https://www.everydayai.com/feed", "source": "Everyday AI", "weight": 1.2},
    # Quality AI commentary — weight 1.1
    {"url": "https://stratechery.com/feed/", "source": "Stratechery", "weight": 1.1},
    {"url": "https://importai.substack.com/feed", "source": "Import AI", "weight": 1.1},
    {"url": "https://www.interconnects.ai/feed", "source": "Interconnects", "weight": 1.1},
    {"url": "https://simonwillison.net/atom/everything/", "source": "Simon Willison", "weight": 1.1},
    {"url": "https://www.aisnakeoil.com/feed", "source": "AI Snake Oil", "weight": 1.1},
    {"url": "https://astralcodexten.com/feed", "source": "Astral Codex Ten", "weight": 1.1},
    # General AI news — weight 1.0
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch AI", "weight": 1.0},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "source": "The Verge AI", "weight": 1.0},
    {"url": "https://www.technologyreview.com/feed/", "source": "MIT Tech Review", "weight": 1.0},
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "source": "Ars Technica", "weight": 1.0},
    {"url": "https://venturebeat.com/category/ai/feed/", "source": "VentureBeat AI", "weight": 1.0},
    {"url": "https://www.wired.com/feed/tag/ai/latest/rss", "source": "Wired AI", "weight": 1.0},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIDaily/1.0; +https://github.com/prokesmic/DailyRoutineAItoBoox)"
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        data = json.load(f)
    return {item["url"] for item in data}


def strip_html(text):
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()[:600]


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    # RFC 2822 (RSS)
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    # ISO 8601 / Atom
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def text_of(el):
    return (el.text or "").strip() if el is not None else ""


def parse_atom(root, cfg, seen, cutoff):
    results = []
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        link_el = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']")
        if link_el is None:
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
        url = (link_el.get("href") or "") if link_el is not None else ""
        if not url or url in seen:
            continue
        title = text_of(entry.find("{http://www.w3.org/2005/Atom}title"))
        pub_raw = text_of(entry.find("{http://www.w3.org/2005/Atom}published")) or \
                  text_of(entry.find("{http://www.w3.org/2005/Atom}updated"))
        pub_dt = parse_date(pub_raw)
        if pub_dt and pub_dt < cutoff:
            continue
        summary_el = entry.find("{http://www.w3.org/2005/Atom}summary") or \
                     entry.find("{http://www.w3.org/2005/Atom}content")
        summary = strip_html(text_of(summary_el))
        results.append({
            "url": url, "title": title, "source": cfg["source"],
            "weight": cfg["weight"],
            "published_at": (pub_dt or datetime.now(timezone.utc)).isoformat(),
            "description": summary,
        })
    return results


def parse_rss(root, cfg, seen, cutoff):
    results = []
    channel = root.find("channel") or root
    for item in channel.findall("item"):
        url = text_of(item.find("link"))
        if not url:
            guid = item.find("guid")
            if guid is not None and (guid.get("isPermaLink", "true") == "true"):
                url = text_of(guid)
        if not url or url in seen:
            continue
        title = text_of(item.find("title"))
        pub_raw = text_of(item.find("pubDate")) or text_of(item.find("{http://purl.org/dc/elements/1.1/}date"))
        pub_dt = parse_date(pub_raw)
        if pub_dt and pub_dt < cutoff:
            continue
        desc = strip_html(
            text_of(item.find("{http://purl.org/rss/1.0/modules/content/}encoded")) or
            text_of(item.find("description"))
        )
        results.append({
            "url": url, "title": title, "source": cfg["source"],
            "weight": cfg["weight"],
            "published_at": (pub_dt or datetime.now(timezone.utc)).isoformat(),
            "description": desc,
        })
    return results


def fetch_feed(cfg, seen, cutoff):
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        tag = root.tag.lower()
        if "atom" in tag or "feed" in tag:
            return parse_atom(root, cfg, seen, cutoff)
        else:
            return parse_rss(root, cfg, seen, cutoff)
    except Exception as e:
        print(f"WARN [{cfg['source']}]: {e}", file=sys.stderr)
        return []


def main():
    seen = load_seen()
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    candidates = []
    seen_urls = set(seen)

    for cfg in FEEDS:
        items = fetch_feed(cfg, seen_urls, cutoff)
        for item in items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                candidates.append(item)
        sleep(0.15)

    print(json.dumps(candidates, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
