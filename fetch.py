"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout."""
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

FEED_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_dt(s):
    if not s:
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S GMT", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(s)
    except Exception:
        return datetime.now(timezone.utc)

def parse_feed_xml(content):
    """Parse RSS or Atom feed bytes, return list of {url, title, summary, published}."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    tag = root.tag.lower()
    entries = []

    # Atom feed
    if "atom" in tag or root.tag.endswith("}feed") or root.tag == "feed":
        ns = {"a": "http://www.w3.org/2005/Atom"}
        items = root.findall("a:entry", ns) or root.findall("entry")
        for e in items:
            link_el = e.find("a:link[@rel='alternate']", ns) or e.find("a:link", ns) or e.find("link")
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or link_el.text or ""
            title_el = e.find("a:title", ns) or e.find("title")
            title = clean(title_el.text if title_el is not None else "")
            summary_el = e.find("a:summary", ns) or e.find("a:content", ns) or e.find("summary") or e.find("content")
            summary = clean(summary_el.text if summary_el is not None else "")[:600]
            pub_el = e.find("a:published", ns) or e.find("a:updated", ns) or e.find("published") or e.find("updated")
            pub = parse_dt(pub_el.text if pub_el is not None else "")
            entries.append({"url": url.split("?")[0].rstrip("/"), "title": title, "summary": summary, "published": pub})
        return entries

    # RSS 2.0 / RSS 1.0
    channel = root.find("channel") or root
    items = channel.findall("item") or root.findall("item")
    for e in items:
        link_el = e.find("link")
        url = link_el.text.strip() if link_el is not None and link_el.text else ""
        # Also check atom:link
        if not url:
            al = e.find("{http://www.w3.org/2005/Atom}link")
            if al is not None:
                url = al.get("href", "")
        title_el = e.find("title")
        title = clean(title_el.text if title_el is not None else "")
        desc_el = e.find("description") or e.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        summary = clean(desc_el.text if desc_el is not None else "")[:600]
        pub_el = e.find("pubDate") or e.find("dc:date") or e.find("{http://purl.org/dc/elements/1.1/}date")
        pub = parse_dt(pub_el.text if pub_el is not None else "")
        entries.append({"url": url.split("?")[0].rstrip("/"), "title": title, "summary": summary, "published": pub})
    return entries

def fetch_feed(url):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=FEED_HEADERS) as client:
            r = client.get(url)
            r.raise_for_status()
            return parse_feed_xml(r.content)
    except Exception as ex:
        raise ex

for feed in cfg.get("rss", []):
    try:
        entries = fetch_feed(feed["url"])
        for e in entries[:30]:
            if e["published"] < cutoff:
                continue
            url = e["url"]
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "url": url, "title": e["title"],
                "source": feed["name"], "weight": feed.get("weight", 1.0),
                "summary": e["summary"],
                "published": e["published"].isoformat(),
            })
    except Exception as ex:
        print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

hn = cfg.get("hackernews", {})
if hn.get("enabled"):
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
    with httpx.Client(timeout=20) as c:
        for kw in hn.get("keywords", []):
            try:
                r = c.get(f"https://hn.algolia.com/api/v1/search_by_date?query={kw}"
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
