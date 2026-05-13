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

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_dt(s):
    if not s:
        return datetime.now(timezone.utc)
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s.strip(), fmt).astimezone(timezone.utc)
        except Exception:
            pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc":   "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
}

def parse_feed(xml_bytes):
    """Parse RSS or Atom feed bytes, return list of {url, title, summary, published}."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        # Try stripping bad bytes
        try:
            cleaned = xml_bytes.decode("utf-8", errors="replace").encode("utf-8")
            root = ET.fromstring(cleaned)
        except Exception:
            raise e

    tag = root.tag.lower()
    entries = []

    # Atom feed
    if "atom" in tag or root.tag == "{http://www.w3.org/2005/Atom}feed":
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            link_el = entry.find("{http://www.w3.org/2005/Atom}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            url = (link_el.get("href") if link_el is not None else "") or ""
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            title = clean(title_el.text if title_el is not None else "")
            summary_el = (entry.find("{http://www.w3.org/2005/Atom}summary") or
                          entry.find("{http://www.w3.org/2005/Atom}content"))
            summary = clean(summary_el.text if summary_el is not None else "")
            pub_el = (entry.find("{http://www.w3.org/2005/Atom}updated") or
                      entry.find("{http://www.w3.org/2005/Atom}published"))
            pub = parse_dt(pub_el.text if pub_el is not None else None)
            entries.append({"url": url, "title": title, "summary": summary, "published": pub})
        return entries

    # RSS 2.0 / RSS 1.0
    channel = root.find("channel") or root
    for item in list(channel.findall("item")) + list(root.findall("item")):
        link_el = item.find("link")
        url = (link_el.text if link_el is not None else "") or ""
        # Some feeds put URL in link tail (CDATA hack)
        if not url:
            url = (link_el.tail or "").strip() if link_el is not None else ""
        title_el = item.find("title")
        title = clean(title_el.text if title_el is not None else "")
        desc_el = (item.find("{http://purl.org/rss/1.0/modules/content/}encoded") or
                   item.find("description"))
        summary = clean(desc_el.text if desc_el is not None else "")
        pub_el = (item.find("pubDate") or
                  item.find("{http://purl.org/dc/elements/1.1/}date"))
        pub = parse_dt(pub_el.text if pub_el is not None else None)
        entries.append({"url": url, "title": title, "summary": summary, "published": pub})
    return entries

with httpx.Client(timeout=20, follow_redirects=True,
                  headers={"User-Agent": "AIDaily/1.0 (+https://github.com/prokesmic/DailyRoutineAItoBoox)"}) as client:
    for feed in cfg.get("rss", []):
        try:
            r = client.get(feed["url"])
            entries = parse_feed(r.content)
            for e in entries[:25]:
                pub = e["published"]
                if pub < cutoff:
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
                    "summary": e["summary"][:600],
                    "published": pub.isoformat(),
                })
        except Exception as ex:
            print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

    hn = cfg.get("hackernews", {})
    if hn.get("enabled"):
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp())
        for kw in hn.get("keywords", []):
            try:
                r = client.get(
                    f"https://hn.algolia.com/api/v1/search_by_date?query={kw}"
                    f"&tags=story&numericFilters=points>={hn['min_points']},created_at_i>{cutoff_ts}"
                )
                for h in r.json().get("hits", []):
                    url = (h.get("url") or "").split("?")[0].rstrip("/")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append({
                        "url": url,
                        "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points', 0)} pts)",
                        "weight": 1.0,
                        "summary": "",
                        "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
