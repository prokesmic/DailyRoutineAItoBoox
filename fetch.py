"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout."""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
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
    "dc":   "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_dt(s):
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(s, fmt).astimezone(timezone.utc)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def text(el, tag):
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""

def attr_or_text(el, tag, attr):
    child = el.find(tag)
    if child is None:
        return ""
    return child.get(attr, child.text or "").strip()

def parse_feed_xml(content):
    """Return list of dicts with url, title, summary, published."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    tag = root.tag.lower()
    entries = []

    # Atom feed
    if "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
        ns = "http://www.w3.org/2005/Atom"
        for e in root.findall(f"{{{ns}}}entry"):
            url = ""
            for link in e.findall(f"{{{ns}}}link"):
                if link.get("rel", "alternate") in ("alternate", ""):
                    url = link.get("href", "")
                    break
            if not url:
                for link in e.findall(f"{{{ns}}}link"):
                    url = link.get("href", "")
                    break
            title = text(e, f"{{{ns}}}title")
            summary_el = e.find(f"{{{ns}}}summary") or e.find(f"{{{ns}}}content")
            summary = clean((summary_el.text or "") if summary_el is not None else "")
            pub = text(e, f"{{{ns}}}published") or text(e, f"{{{ns}}}updated")
            entries.append({"url": url, "title": clean(title), "summary": summary[:600], "published": pub})
        return entries

    # RSS 2.0 / RSS 1.0
    channel = root.find("channel")
    items = (channel or root).findall("item")
    for e in items:
        url = text(e, "link") or attr_or_text(e, "{http://www.w3.org/2005/Atom}link", "href")
        title = text(e, "title")
        summary = clean(text(e, "description") or text(e, "{http://purl.org/rss/1.0/modules/content/}encoded"))
        pub = text(e, "pubDate") or text(e, "{http://purl.org/dc/elements/1.1/}date")
        entries.append({"url": url, "title": clean(title), "summary": summary[:600], "published": pub})
    return entries

def fetch_feed(url):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=FEED_HEADERS) as client:
            r = client.get(url)
            r.raise_for_status()
            return parse_feed_xml(r.content)
    except Exception as ex:
        raise RuntimeError(str(ex))

for feed in cfg.get("rss", []):
    try:
        entries = fetch_feed(feed["url"])
        for e in entries[:25]:
            pub_dt = parse_dt(e["published"])
            if pub_dt < cutoff:
                continue
            url = e["url"].split("?")[0].rstrip("/")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "url": url,
                "title": e["title"],
                "source": feed["name"],
                "weight": feed.get("weight", 1.0),
                "summary": e["summary"],
                "published": pub_dt.isoformat(),
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
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append({
                        "url": url,
                        "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points',0)} pts)",
                        "weight": 1.0,
                        "summary": "",
                        "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
