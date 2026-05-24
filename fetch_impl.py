"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout.
Uses httpx + stdlib xml.etree.ElementTree instead of feedparser to avoid sgmllib3k issue."""
import json, os, re, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import httpx, yaml

cfg = yaml.safe_load(open("feeds.yaml"))
cutoff = datetime.now(timezone.utc) - timedelta(hours=cfg["lookback_hours"])

shipped = set()
if os.path.exists("seen.json"):
    try:
        shipped = {row["url"] for row in json.load(open("seen.json"))}
    except Exception as ex:
        print(f"seen.json unreadable: {ex}", file=sys.stderr)

seen, out = set(shipped), []

FEED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'media': 'http://search.yahoo.com/mrss/',
}

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    # Try ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s[:25], fmt[:len(fmt)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    # Try RFC 2822
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def get_text(el, tag, ns_prefix=None):
    if ns_prefix:
        t = el.find(f"{{{NS[ns_prefix]}}}{tag}")
    else:
        t = el.find(tag)
    if t is not None and t.text:
        return t.text.strip()
    return ""

def fetch_feed(url):
    with httpx.Client(timeout=25, follow_redirects=True, headers=FEED_HEADERS) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text

def parse_atom(root, feed_name, feed_weight):
    entries = []
    ns = NS['atom']
    for entry in root.findall(f"{{{ns}}}entry"):
        title_el = entry.find(f"{{{ns}}}title")
        title = clean(title_el.text if title_el is not None else "")

        # Link: prefer rel=alternate
        link = ""
        for l in entry.findall(f"{{{ns}}}link"):
            rel = l.get("rel", "alternate")
            href = l.get("href", "")
            if rel == "alternate" and href:
                link = href
                break
        if not link:
            l = entry.find(f"{{{ns}}}link")
            if l is not None:
                link = l.get("href", "")

        # Date
        updated = entry.find(f"{{{ns}}}updated") or entry.find(f"{{{ns}}}published")
        dt = parse_date(updated.text if updated is not None else "")

        # Summary
        summary_el = entry.find(f"{{{ns}}}summary") or entry.find(f"{{{ns}}}content")
        summary = clean(summary_el.text if summary_el is not None else "")[:600]

        url = link.split("?")[0].rstrip("/")
        if url and url not in seen and dt >= cutoff:
            seen.add(url)
            entries.append({
                "url": url, "title": title, "source": feed_name,
                "weight": feed_weight, "summary": summary,
                "published": dt.isoformat(),
            })
    return entries

def parse_rss(root, feed_name, feed_weight):
    entries = []
    channel = root.find("channel")
    if channel is None:
        channel = root
    for item in channel.findall("item"):
        title = clean(get_text(item, "title"))
        link = get_text(item, "link")
        if not link:
            guid = item.find("guid")
            if guid is not None and guid.get("isPermaLink", "true").lower() == "true":
                link = guid.text or ""

        pub_date = get_text(item, "pubDate")
        if not pub_date:
            dc_date = item.find(f"{{{NS['dc']}}}date")
            pub_date = dc_date.text if dc_date is not None else ""
        dt = parse_date(pub_date)

        # Summary: try content:encoded, then description
        summary_el = item.find(f"{{{NS['content']}}}encoded") or item.find("description")
        summary = clean(summary_el.text if summary_el is not None else "")[:600]

        url = link.split("?")[0].rstrip("/")
        if url and url not in seen and dt >= cutoff:
            seen.add(url)
            entries.append({
                "url": url, "title": title, "source": feed_name,
                "weight": feed_weight, "summary": summary,
                "published": dt.isoformat(),
            })
    return entries

for feed in cfg.get("rss", []):
    try:
        content = fetch_feed(feed["url"])
        root = ET.fromstring(content)
        # Detect Atom vs RSS
        atom_ns = NS['atom']
        if root.tag == f"{{{atom_ns}}}feed" or "feed" in root.tag.lower():
            entries = parse_atom(root, feed["name"], feed.get("weight", 1.0))
        else:
            entries = parse_rss(root, feed["name"], feed.get("weight", 1.0))
        out.extend(entries)
    except Exception as ex:
        print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

hn = cfg.get("hackernews", {})
if hn.get("enabled"):
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
    with httpx.Client(timeout=20) as c:
        for kw in hn.get("keywords", []):
            try:
                r = c.get(
                    f"https://hn.algolia.com/api/v1/search_by_date?query={kw}"
                    f"&tags=story&numericFilters=points>={hn['min_points']},created_at_i>{cutoff_ts}"
                )
                for h in r.json().get("hits", []):
                    url = (h.get("url") or "").split("?")[0].rstrip("/")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append({
                        "url": url, "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points',0)} pts)", "weight": 1.0,
                        "summary": "", "published": datetime.fromtimestamp(
                            h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
