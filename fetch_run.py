"""Fetch RSS/Atom + HN candidates without feedparser dependency."""
import json, os, re, sys, time
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

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc) if fmt.endswith("GMT") else datetime.strptime(s, fmt).astimezone(timezone.utc)
        except Exception:
            pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def parse_feed(text, feed_name, weight):
    items = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # Try stripping namespace junk
        text2 = re.sub(r' xmlns[^"]*"[^"]*"', '', text)
        try:
            root = ET.fromstring(text2)
        except Exception:
            return items

    tag = root.tag
    # Atom
    if "Atom" in tag or tag.endswith("}feed") or tag == "feed":
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry") or root.findall(".//entry"):
            link_el = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']") or \
                      entry.find("{http://www.w3.org/2005/Atom}link") or \
                      entry.find("link")
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or (link_el.text or "")
            url = url.split("?")[0].rstrip("/")
            title_el = entry.find("{http://www.w3.org/2005/Atom}title") or entry.find("title")
            title = clean(title_el.text if title_el is not None else "")
            pub_el = entry.find("{http://www.w3.org/2005/Atom}published") or \
                     entry.find("{http://www.w3.org/2005/Atom}updated") or \
                     entry.find("published") or entry.find("updated")
            pub = parse_date(pub_el.text if pub_el is not None else None)
            summ_el = entry.find("{http://www.w3.org/2005/Atom}summary") or \
                      entry.find("{http://www.w3.org/2005/Atom}content") or \
                      entry.find("summary") or entry.find("content")
            summ = clean(summ_el.text if summ_el is not None else "")[:600]
            if url and pub >= cutoff:
                items.append((url, title, summ, pub))
        return items
    # RSS
    for item in root.findall(".//item"):
        link_el = item.find("link")
        url = (link_el.text or "") if link_el is not None else ""
        url = url.split("?")[0].rstrip("/")
        title_el = item.find("title")
        title = clean(title_el.text if title_el is not None else "")
        pub_el = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
        pub = parse_date(pub_el.text if pub_el is not None else None)
        desc_el = item.find("description") or item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        summ = clean(desc_el.text if desc_el is not None else "")[:600]
        if url and pub >= cutoff:
            items.append((url, title, summ, pub))
    return items

headers = {"User-Agent": "Mozilla/5.0 (AI Daily Reader pipeline; +https://github.com/prokesmic/DailyRoutineAItoBoox)"}

with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as c:
    for feed in cfg.get("rss", []):
        try:
            r = c.get(feed["url"])
            if r.status_code != 200:
                print(f"HTTP {r.status_code} for {feed['name']}", file=sys.stderr)
                continue
            items = parse_feed(r.text, feed["name"], feed.get("weight", 1.0))
            for url, title, summ, pub in items[:25]:
                if url in seen or not title:
                    continue
                seen.add(url)
                out.append({
                    "url": url, "title": title,
                    "source": feed["name"], "weight": feed.get("weight", 1.0),
                    "summary": summ, "published": pub.isoformat(),
                })
        except Exception as ex:
            print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

    hn = cfg.get("hackernews", {})
    if hn.get("enabled"):
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
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
                        "url": url, "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points', 0)} pts)", "weight": 1.0,
                        "summary": "", "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
