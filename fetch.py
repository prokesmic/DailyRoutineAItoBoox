#!/usr/bin/env python3
"""Fetch AI news candidates from RSS feeds using stdlib XML + requests."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

SEEN_FILE = Path("seen.json")

FEEDS = [
    # (source_name, rss_url, weight)
    ("Ethan Mollick", "https://www.oneusefulthing.org/feed", 1.2),
    ("Latent Space", "https://www.latent.space/feed", 1.1),
    ("Zvi Mowshowitz", "https://thezvi.substack.com/feed", 1.1),
    ("Pragmatic Engineer", "https://newsletter.pragmaticengineer.com/feed", 1.1),
    ("Everyday AI", "https://www.everydayai.com/feed.xml", 1.0),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", 0.9),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", 0.9),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", 1.0),
    ("Ars Technica AI", "https://arstechnica.com/tag/ai/feed/", 0.9),
    ("The Verge AI", "https://www.theverge.com/rss/ai/index.xml", 0.9),
    ("STAT News", "https://www.statnews.com/feed/", 1.0),
    ("IEEE Spectrum AI", "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", 0.9),
    ("Import AI", "https://jack-clark.net/feed/", 1.1),
    ("AI Snake Oil", "https://aisnakeoil.substack.com/feed", 1.0),
    ("Interconnects", "https://www.interconnects.ai/feed", 1.0),
    ("Benedict Evans", "https://www.ben-evans.com/benedictevans/rss.xml", 1.0),
    ("Nature News", "https://feeds.nature.com/nature/rss/current", 1.0),
]

STRIP_HTML = re.compile(r"<[^>]+>")
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text())
        return {item["url"] for item in data}
    except Exception:
        return set()


def clean_text(text, maxlen=500):
    text = STRIP_HTML.sub(" ", text or "")
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:maxlen]


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        pass
    # Try ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str.strip()[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


def find_text(el, tags):
    for tag in tags:
        child = el.find(tag, NS)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_rss(content, name, weight, seen_urls, since):
    results = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"WARN: {name}: XML parse error: {e}", file=sys.stderr)
        return []

    # Detect RSS vs Atom
    if root.tag in ("rss", "channel") or root.find("channel") is not None:
        channel = root if root.tag == "channel" else root.find("channel")
        items = channel.findall("item") if channel is not None else []
        for item in items[:30]:
            link = find_text(item, ["link", "guid"])
            if not link or link in seen_urls:
                continue
            title = clean_text(find_text(item, ["title"]), 200)
            desc = find_text(item, [
                "content:encoded", "description",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ])
            summary = clean_text(desc, 500)
            pub_str = find_text(item, ["pubDate", "dc:date",
                                       "{http://purl.org/dc/elements/1.1/}date"])
            pub_dt = parse_date(pub_str)
            if pub_dt and pub_dt < since:
                continue
            results.append({
                "url": link, "title": title, "source": name,
                "weight": weight, "summary": summary,
                "published": pub_str,
            })
    else:
        # Atom feed
        ns_atom = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f"{{{ns_atom}}}entry")[:30]:
            link_el = entry.find(f"{{{ns_atom}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{ns_atom}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            if not link or link in seen_urls:
                continue
            title_el = entry.find(f"{{{ns_atom}}}title")
            title = clean_text(title_el.text if title_el is not None else "", 200)
            summ_el = entry.find(f"{{{ns_atom}}}summary") or entry.find(f"{{{ns_atom}}}content")
            summary = clean_text(summ_el.text if summ_el is not None else "", 500)
            pub_el = entry.find(f"{{{ns_atom}}}updated") or entry.find(f"{{{ns_atom}}}published")
            pub_str = pub_el.text if pub_el is not None else ""
            pub_dt = parse_date(pub_str)
            if pub_dt and pub_dt < since:
                continue
            results.append({
                "url": link, "title": title, "source": name,
                "weight": weight, "summary": summary,
                "published": pub_str,
            })
    return results


HEADERS = {"User-Agent": "AI-Daily-Reader/1.0 (+educational)"}


def fetch_feed(name, url, weight, seen_urls, since):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return parse_rss(resp.content, name, weight, seen_urls, since)
    except Exception as e:
        print(f"WARN: {name}: {e}", file=sys.stderr)
        return []


def main():
    seen_urls = load_seen()
    since = datetime.now(timezone.utc) - timedelta(hours=48)

    candidates = []
    for name, url, weight in FEEDS:
        items = fetch_feed(name, url, weight, seen_urls, since)
        print(f"  {name}: {len(items)} new items", file=sys.stderr)
        candidates.extend(items)

    print(f"Total candidates: {len(candidates)}", file=sys.stderr)
    print(json.dumps(candidates, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
