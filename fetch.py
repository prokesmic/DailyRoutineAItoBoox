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

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())


NS = {"atom": "http://www.w3.org/2005/Atom"}

def parse_dt(s):
    if not s:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)

def fetch_rss(url):
    with httpx.Client(timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 AIReader/1.0"}) as c:
        r = c.get(url)
        r.raise_for_status()
    root = ET.fromstring(r.content)
    tag = root.tag.lower()
    items = []
    if "feed" in tag or root.tag.startswith("{http://www.w3.org/2005/Atom}"):
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = (link_el.get("href") if link_el is not None else "") or ""
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            title = title_el.text if title_el is not None else ""
            sum_el = entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("{http://www.w3.org/2005/Atom}content")
            summary = sum_el.text if sum_el is not None else ""
            pub_el = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")
            pub = pub_el.text if pub_el is not None else ""
            items.append({"link": link, "title": title, "summary": summary, "published": pub})
    else:
        for item in root.findall(".//item")[:25]:
            def t(tag): el = item.find(tag); return el.text if el is not None else ""
            items.append({"link": t("link"), "title": t("title"), "summary": t("description"), "published": t("pubDate")})
    return items

for feed in cfg.get("rss", []):
    try:
        entries = fetch_rss(feed["url"])
        for e in entries[:25]:
            pub_dt = parse_dt(e.get("published", ""))
            if pub_dt < cutoff: continue
            url = (e.get("link") or "").split("?")[0].rstrip("/")
            if not url or url in seen: continue
            seen.add(url)
            out.append({
                "url": url, "title": clean(e.get("title", "")),
                "source": feed["name"], "weight": feed.get("weight", 1.0),
                "summary": clean(e.get("summary", ""))[:600],
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
