#!/usr/bin/env python3
"""
fetch.py - Fetch AI content from RSS/Atom feeds using stdlib only.
Filters URLs already in seen.json. Outputs JSON array to stdout.
"""
import json
import sys
import os
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

SEEN_FILE = "seen.json"
MAX_AGE_DAYS = 3

FEEDS = [
    # CITATION_SOURCES
    {"url": "https://www.oneusefulthing.org/feed", "source": "Ethan Mollick", "weight": 1.2},
    {"url": "https://www.latent.space/feed", "source": "Latent Space", "weight": 1.2},
    {"url": "https://thezvi.substack.com/feed", "source": "Zvi Mowshowitz", "weight": 1.2},
    {"url": "https://newsletter.pragmaticengineer.com/feed", "source": "Pragmatic Engineer", "weight": 1.2},
    {"url": "https://www.everydayai.com/feed", "source": "Everyday AI", "weight": 1.1},
    # Other reader sources
    {"url": "https://stratechery.com/feed/", "source": "Stratechery", "weight": 1.1},
    # Technical / research
    {"url": "https://huggingface.co/blog/feed.xml", "source": "Hugging Face Blog", "weight": 1.1},
    {"url": "https://simonwillison.net/atom/everything/", "source": "Simon Willison", "weight": 1.1},
    {"url": "https://www.interconnects.ai/feed", "source": "Interconnects AI", "weight": 1.1},
    # Frontier labs
    {"url": "https://openai.com/blog/rss.xml", "source": "OpenAI Blog", "weight": 1.2},
    {"url": "https://www.anthropic.com/news/rss", "source": "Anthropic News", "weight": 1.2},
    {"url": "https://deepmind.google/blog/feed/basic/", "source": "DeepMind Blog", "weight": 1.2},
    {"url": "https://ai.meta.com/blog/rss/", "source": "Meta AI Blog", "weight": 1.1},
    # News
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/", "source": "TechCrunch AI", "weight": 1.0},
    {"url": "https://venturebeat.com/ai/feed/", "source": "VentureBeat AI", "weight": 1.0},
    {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "source": "The Verge AI", "weight": 1.0},
    # Science/pharma
    {"url": "https://www.statnews.com/feed/", "source": "STAT News", "weight": 1.1},
    {"url": "https://www.nature.com/subjects/machine-learning.rss", "source": "Nature ML", "weight": 1.1},
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
        return {item["url"] for item in data if isinstance(item, dict) and "url" in item}
    except Exception:
        return set()


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return " ".join(text.split())


def parse_date(date_str):
    if not date_str:
        return datetime.now(timezone.utc)
    # Try RFC 2822 (RSS)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    # Try ISO 8601 (Atom)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"):
        try:
            s = date_str.rstrip("Z")
            if date_str.endswith("Z"):
                s += "+00:00"
            dt = datetime.strptime(s, fmt.rstrip("z").replace("%z", ""))
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    try:
        # Python 3.7+ fromisoformat
        s = date_str
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def fetch_xml(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AI-Daily-Reader/1.0", "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def parse_rss(root, source, weight, cutoff):
    items = []
    channel = root.find("channel")
    if channel is None:
        return items
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        if not link or not link.startswith("http"):
            continue
        title = strip_html(item.findtext("title") or "")
        if not title:
            continue
        pub_str = item.findtext("pubDate") or item.findtext(f"{{{NS['dc']}}}date") or ""
        pub = parse_date(pub_str)
        if pub < cutoff:
            continue
        desc = (item.findtext("description") or
                item.findtext(f"{{{NS['content']}}}encoded") or "")
        summary = strip_html(desc)[:600]
        items.append({"url": link, "title": title, "source": source,
                       "published": pub.isoformat(), "summary": summary, "weight": weight})
    return items


def parse_atom(root, source, weight, cutoff):
    items = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f"{ns_atom}entry"):
        link_el = entry.find(f"{ns_atom}link[@rel='alternate']")
        if link_el is None:
            link_el = entry.find(f"{ns_atom}link")
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        if not link or not link.startswith("http"):
            continue
        title = strip_html((entry.findtext(f"{ns_atom}title") or ""))
        if not title:
            continue
        pub_str = (entry.findtext(f"{ns_atom}published") or
                   entry.findtext(f"{ns_atom}updated") or "")
        pub = parse_date(pub_str)
        if pub < cutoff:
            continue
        content_el = entry.find(f"{ns_atom}content")
        summary_el = entry.find(f"{ns_atom}summary")
        raw = ""
        if content_el is not None:
            raw = content_el.text or ""
        elif summary_el is not None:
            raw = summary_el.text or ""
        summary = strip_html(raw)[:600]
        items.append({"url": link, "title": title, "source": source,
                       "published": pub.isoformat(), "summary": summary, "weight": weight})
    return items


def fetch_feed(feed_config):
    url, source, weight = feed_config["url"], feed_config["source"], feed_config["weight"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    try:
        data = fetch_xml(url)
        # Handle BOM / encoding declaration issues
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        text = data.decode("utf-8", errors="replace")
        # Strip invalid XML chars
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        root = ET.fromstring(text)
        tag = root.tag.lower()
        if "rss" in tag or root.tag == "rss" or root.find("channel") is not None:
            return parse_rss(root, source, weight, cutoff)
        elif "feed" in tag or "atom" in root.tag.lower():
            return parse_atom(root, source, weight, cutoff)
        else:
            # Try both
            items = parse_rss(root, source, weight, cutoff)
            if not items:
                items = parse_atom(root, source, weight, cutoff)
            return items
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []


def main():
    seen = load_seen()
    candidates = []
    seen_in_run = set()
    for feed in FEEDS:
        items = fetch_feed(feed)
        for item in items:
            if item["url"] not in seen and item["url"] not in seen_in_run:
                seen_in_run.add(item["url"])
                candidates.append(item)
    candidates.sort(key=lambda x: x["published"], reverse=True)
    print(json.dumps(candidates, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
