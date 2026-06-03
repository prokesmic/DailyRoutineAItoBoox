"""Fetch RSS + HN candidates using xml.etree instead of feedparser, exclude already-shipped URLs."""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
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

FEED_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

DATE_FMTS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S+00:00",
]

def parse_date(s):
    if not s: return None
    s = s.strip()
    for fmt in DATE_FMTS:
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except ValueError:
            pass
    return None

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_rss(content, feed_name, weight):
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"XML parse error {feed_name}: {e}", file=sys.stderr)
        return items

    tag = root.tag.lower()
    # Atom feed
    if "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
        ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f"{{{ns}}}entry"):
            link_el = entry.find(f"{{{ns}}}link")
            url = (link_el.get("href") if link_el is not None else "") or ""
            url = url.split("?")[0].rstrip("/")
            if not url or url in seen: continue
            title_el = entry.find(f"{{{ns}}}title")
            title = clean(title_el.text if title_el is not None else "")
            pub = entry.find(f"{{{ns}}}published") or entry.find(f"{{{ns}}}updated")
            pub_dt = parse_date(pub.text if pub is not None else None) or datetime.now(timezone.utc)
            if pub_dt < cutoff: continue
            summary_el = entry.find(f"{{{ns}}}summary") or entry.find(f"{{{ns}}}content")
            summary = clean(summary_el.text if summary_el is not None else "")[:600]
            seen.add(url)
            items.append({"url": url, "title": title, "source": feed_name,
                          "weight": weight, "summary": summary, "published": pub_dt.isoformat()})
    else:
        # RSS 2.0
        for item in root.findall(".//item"):
            url = (item.findtext("link") or "").split("?")[0].rstrip("/")
            if not url or url in seen: continue
            title = clean(item.findtext("title") or "")
            pub_str = item.findtext("pubDate") or item.findtext(f"{{{NS['dc']}}}date") or ""
            pub_dt = parse_date(pub_str) or datetime.now(timezone.utc)
            if pub_dt < cutoff: continue
            summary = clean(item.findtext("description") or
                           item.findtext(f"{{{NS['content']}}}encoded") or "")[:600]
            seen.add(url)
            items.append({"url": url, "title": title, "source": feed_name,
                          "weight": weight, "summary": summary, "published": pub_dt.isoformat()})
    return items

with httpx.Client(timeout=20, follow_redirects=True, headers=FEED_HEADERS) as client:
    for feed in cfg.get("rss", []):
        try:
            r = client.get(feed["url"])
            out.extend(parse_rss(r.content, feed["name"], feed.get("weight", 1.0)))
        except Exception as ex:
            print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

    hn = cfg.get("hackernews", {})
    if hn.get("enabled"):
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
        for kw in hn.get("keywords", []):
            try:
                r = client.get(f"https://hn.algolia.com/api/v1/search_by_date?query={kw}"
                               f"&tags=story&numericFilters=points>={hn['min_points']},created_at_i>{cutoff_ts}")
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

print(json.dumps(out, ensure_ascii=False, indent=2))
