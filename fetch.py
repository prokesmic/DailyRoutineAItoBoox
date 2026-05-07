#!/usr/bin/env python3
"""fetch.py - Fetch AI news candidates, filtering already-seen URLs.

Outputs JSON array to stdout. Each item:
  {url, title, source, description, published, weight}
Weight is clamped [0.8, 1.2] and used as a scoring multiplier downstream.
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AIReaderBot/1.0; RSS reader)"
    )
}
TIMEOUT = 15  # seconds per feed

# (rss_url, display_name, base_weight)
FEEDS = [
    # Core AI research / practitioner
    ("https://www.latent.space/feed",                                "Latent Space",                   1.15),
    ("https://www.deeplearning.ai/the-batch/feed/xml/",              "The Batch (DeepLearning.AI)",     1.10),
    ("https://jack-clark.net/feed/",                                 "Import AI",                      1.15),
    ("https://bair.berkeley.edu/blog/feed.xml",                      "BAIR Blog",                      1.10),
    ("https://thegradient.pub/rss/",                                 "The Gradient",                   1.10),
    # Frontier labs
    ("https://openai.com/blog/rss.xml",                              "OpenAI Blog",                    1.15),
    ("https://www.anthropic.com/rss.xml",                            "Anthropic Blog",                 1.15),
    ("https://huggingface.co/blog/feed.xml",                         "Hugging Face Blog",              1.10),
    ("https://ai.googleblog.com/feeds/posts/default",                "Google AI Blog",                 1.10),
    ("https://blog.research.google/feeds/posts/default",             "Google Research Blog",           1.10),
    # Capital / enterprise analysis
    ("https://a16z.com/feed/",                                       "a16z",                           1.10),
    ("https://www.semianalysis.com/feed",                            "SemiAnalysis",                   1.15),
    # Tech news
    ("https://www.technologyreview.com/feed/",                       "MIT Tech Review",                1.05),
    ("https://techcrunch.com/category/artificial-intelligence/feed/","TechCrunch AI",                  1.00),
    ("https://venturebeat.com/category/ai/feed/",                    "VentureBeat AI",                 1.00),
    # Science / pharma-adjacent (high priority)
    ("https://feeds.nature.com/nature/rss/current",                  "Nature",                         1.15),
    ("https://www.science.org/rss/news_current.xml",                 "Science News",                   1.15),
    # Podcasts (publish show-notes as RSS)
    ("https://feeds.transistor.fm/everyday-ai",                      "Everyday AI (Wilson)",           1.10),
    ("https://api.substack.com/feed/podcast/3881729.rss",            "The AI Daily Brief (Whittemore)",1.10),
]

BOOST_MAP = {
    # Money attached
    "funding": 0.05, "raises": 0.05, "investment": 0.04, "acquisition": 0.05,
    "billion": 0.06, "million": 0.04, "deal": 0.03, "capex": 0.05, "opex": 0.04,
    # Frontier lab signals
    "openai": 0.04, "anthropic": 0.04, "deepmind": 0.04, "mistral": 0.04,
    "meta-fair": 0.04, "microsoft research": 0.04, "nvidia research": 0.04,
    # Enterprise deployment
    "deployment": 0.04, "production": 0.04, "enterprise": 0.04,
    "jpmorgan": 0.05, "mckinsey": 0.05, "kpmg": 0.04,
    # Pharma / bio (highest priority for this reader)
    "pharma": 0.08, "drug discovery": 0.09, "clinical trial": 0.09,
    "protein": 0.07, "genomic": 0.07, "alphafold": 0.09, "virtual cell": 0.09,
    "biology": 0.06, "biomedical": 0.07, "therapeutic": 0.07, "oncology": 0.07,
    "fda": 0.07, "ema": 0.07, "regulatory": 0.05,
    # Agentic / coding agents
    "agent": 0.04, "agentic": 0.05, "cursor": 0.04, "coding agent": 0.05,
    "benchmark": 0.04, "eval": 0.03,
    # Governance / workforce
    "regulation": 0.05, "policy": 0.04, "layoff": 0.05, "workforce": 0.04,
    "eu ai act": 0.07, "gdpr": 0.05,
    # Open weights / reproducible
    "open source": 0.04, "weights": 0.03, "dataset": 0.04, "checkpoint": 0.04,
}

PENALTY_MAP = {
    "crypto": -0.08, "bitcoin": -0.08, "nft": -0.10, "web3": -0.07,
    "beginners guide": -0.06, "what is ai": -0.06, "consumer review": -0.05,
}

# XML namespaces used in Atom feeds
NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "media":   "http://search.yahoo.com/mrss/",
}


def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        data = json.load(f)
    return {item["url"] for item in data}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    # Try RFC 2822 (most RSS)
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        pass
    # Try ISO 8601 (Atom)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:len(fmt)], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def _first_text(el, *paths) -> str:
    for path in paths:
        child = el.find(path)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def parse_rss(root: ET.Element, source: str, base_weight: float,
              seen_urls: set, cutoff: datetime) -> list:
    candidates = []
    channel = root.find("channel")
    items = (channel or root).findall("item")
    for item in items:
        link = _first_text(item, "link", "guid")
        if not link or link in seen_urls:
            continue
        title = _first_text(item, "title")
        if not title:
            continue
        raw_desc = _first_text(item, "description",
                               f"content:encoded",
                               "{http://purl.org/rss/1.0/modules/content/}encoded")
        desc = _strip_html(raw_desc)[:600]
        pub_str = _first_text(item, "pubDate", "dc:date",
                               "{http://purl.org/dc/elements/1.1/}date")
        published = _parse_date(pub_str)
        if published and published < cutoff:
            continue
        weight = _compute_weight(title, desc, base_weight)
        candidates.append({
            "url": link, "title": title, "source": source,
            "description": desc,
            "published": published.isoformat() if published else None,
            "weight": weight,
        })
    return candidates


def parse_atom(root: ET.Element, source: str, base_weight: float,
               seen_urls: set, cutoff: datetime) -> list:
    atom_ns = "http://www.w3.org/2005/Atom"
    candidates = []
    for entry in root.findall(f"{{{atom_ns}}}entry"):
        # link: prefer rel="alternate"
        link = ""
        for lnk in entry.findall(f"{{{atom_ns}}}link"):
            rel = lnk.get("rel", "alternate")
            href = lnk.get("href", "")
            if rel == "alternate" and href:
                link = href
                break
            if href and not link:
                link = href
        if not link or link in seen_urls:
            continue
        title_el = entry.find(f"{{{atom_ns}}}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue
        summary_el = entry.find(f"{{{atom_ns}}}summary") or entry.find(f"{{{atom_ns}}}content")
        raw_desc = (summary_el.text or "") if summary_el is not None else ""
        desc = _strip_html(raw_desc)[:600]
        pub_el = entry.find(f"{{{atom_ns}}}published") or entry.find(f"{{{atom_ns}}}updated")
        published = _parse_date(pub_el.text if pub_el is not None else None)
        if published and published < cutoff:
            continue
        weight = _compute_weight(title, desc, base_weight)
        candidates.append({
            "url": link, "title": title, "source": source,
            "description": desc,
            "published": published.isoformat() if published else None,
            "weight": weight,
        })
    return candidates


def _compute_weight(title: str, description: str, base_weight: float) -> float:
    combined = (title + " " + (description or "")).lower()
    delta = 0.0
    for kw, w in BOOST_MAP.items():
        if kw in combined:
            delta += w
    for kw, w in PENALTY_MAP.items():
        if kw in combined:
            delta += w
    return round(min(max(base_weight + delta, 0.8), 1.2), 3)


def fetch_feed(url: str, source: str, base_weight: float,
               seen_urls: set, cutoff: datetime) -> list:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.content

        root = ET.fromstring(raw)
        tag = root.tag.lower()

        if "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
            return parse_atom(root, source, base_weight, seen_urls, cutoff)
        else:
            return parse_rss(root, source, base_weight, seen_urls, cutoff)
    except Exception as exc:
        print(f"Warning: failed to fetch {source} ({url}): {exc}", file=sys.stderr)
        return []


def main():
    seen_urls = load_seen()
    # 48 h lookback: generous enough for first run, safe for regular runs
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    all_candidates: list = []
    seen_in_batch: set = set()

    for url, source, base_weight in FEEDS:
        items = fetch_feed(url, source, base_weight, seen_urls, cutoff)
        added = 0
        for item in items:
            if item["url"] not in seen_in_batch:
                seen_in_batch.add(item["url"])
                all_candidates.append(item)
                added += 1
        print(f"[fetch] {source}: {added} new items", file=sys.stderr)

    all_candidates.sort(
        key=lambda x: (x["weight"], x["published"] or ""),
        reverse=True,
    )

    print(json.dumps(all_candidates, indent=2, ensure_ascii=False))
    print(f"[fetch] Total candidates: {len(all_candidates)}", file=sys.stderr)


if __name__ == "__main__":
    main()
