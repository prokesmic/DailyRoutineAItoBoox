"""Fetch RSS + HN candidates without feedparser; uses stdlib xml + requests."""
import json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import requests, yaml

cfg = yaml.safe_load(open("feeds.yaml"))
cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["lookback_hours"])

shipped = set()
if os.path.exists("seen.json"):
    try:
        shipped = {row["url"] for row in json.load(open("seen.json"))}
    except Exception as ex:
        print(f"seen.json unreadable: {ex}", file=sys.stderr)

seen, out = set(shipped), []

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_dt(s):
    if not s: return None
    s = s.strip()
    # Try RFC 2822 (RSS)
    try: return parsedate_to_datetime(s).astimezone(timezone.utc)
    except: pass
    # Try ISO-8601 / Atom
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:25], fmt[:len(s[:25])])
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except: pass
    return None

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

def get_text(el, *tags):
    for tag in tags:
        c = el.find(tag)
        if c is not None and c.text: return c.text.strip()
    return ""

def fetch_feed(url):
    """Fetch and parse RSS or Atom feed; return list of (url, title, summary, dt) tuples."""
    r = requests.get(url, timeout=20, headers={"User-Agent": "AI-Daily-Reader/1.0"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    tag = root.tag.lower()
    # Atom
    if "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
        ns = "http://www.w3.org/2005/Atom"
        for e in root.findall(f"{{{ns}}}entry"):
            link_el = e.find(f"{{{ns}}}link")
            link = (link_el.get("href") if link_el is not None else "") or ""
            title = get_text(e, f"{{{ns}}}title")
            summary_el = e.find(f"{{{ns}}}summary") or e.find(f"{{{ns}}}content")
            summary = summary_el.text if summary_el is not None else ""
            updated_el = e.find(f"{{{ns}}}updated") or e.find(f"{{{ns}}}published")
            dt = parse_dt(updated_el.text if updated_el is not None else None) or datetime.now(timezone.utc)
            items.append((link, title, clean(summary), dt))
    else:
        # RSS 2.0 — handle namespace wrapper
        channel = root.find("channel") or root
        for e in channel.findall("item"):
            link = get_text(e, "link") or get_text(e, "guid")
            title = get_text(e, "title")
            summary = get_text(e, "description") or get_text(e, f"{{{NS['content']}}}encoded")
            pub = get_text(e, "pubDate") or get_text(e, f"{{{NS['dc']}}}date")
            dt = parse_dt(pub) or datetime.now(timezone.utc)
            items.append((link, title, clean(summary), dt))
    return items

for feed in cfg.get("rss", []):
    try:
        entries = fetch_feed(feed["url"])
        for link, title, summary, dt in entries[:25]:
            if dt < cutoff: continue
            url = link.split("?")[0].rstrip("/")
            if not url or url in seen: continue
            seen.add(url)
            out.append({
                "url": url, "title": clean(title),
                "source": feed["name"], "weight": feed.get("weight", 1.0),
                "summary": summary[:600],
                "published": dt.isoformat(),
            })
    except Exception as ex:
        print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

hn = cfg.get("hackernews", {})
if hn.get("enabled"):
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
    for kw in hn.get("keywords", []):
        try:
            r = requests.get(
                f"https://hn.algolia.com/api/v1/search_by_date?query={kw}"
                f"&tags=story&numericFilters=points>={hn['min_points']},created_at_i>{cutoff_ts}",
                timeout=20)
            for h in r.json().get("hits", []):
                url = (h.get("url") or "").split("?")[0].rstrip("/")
                if not url or url in seen: continue
                seen.add(url)
                out.append({
                    "url": url, "title": clean(h.get("title") or ""),
                    "source": f"HN ({h.get('points',0)} pts)", "weight": 1.0,
                    "summary": "", "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                })
        except Exception as ex:
            print(f"HN error {kw}: {ex}", file=sys.stderr)
        time.sleep(0.1)

print(json.dumps(out, ensure_ascii=False, indent=2))
