"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout."""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
try:
    import feedparser
    feedparser.parse  # test it works
except Exception:
    import feedparser_shim as feedparser
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

def parse_feed(url):
    """Fetch via httpx (browser UA + follow redirects) so feeds that block
    feedparser's default agent (403) or redirect (302) still parse."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=FEED_HEADERS) as client:
            return feedparser.parse(client.get(url).content)
    except Exception:
        return feedparser.parse(url)

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def entry_dt(e):
    for k in ("published_parsed", "updated_parsed"):
        v = getattr(e, k, None) or e.get(k)
        if v: return datetime(*v[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

for feed in cfg.get("rss", []):
    try:
        p = parse_feed(feed["url"])
        for e in p.entries[:25]:
            if entry_dt(e) < cutoff: continue
            url = (e.get("link") or "").split("?")[0].rstrip("/")
            if not url or url in seen: continue
            seen.add(url)
            out.append({
                "url": url, "title": clean(e.get("title", "")),
                "source": feed["name"], "weight": feed.get("weight", 1.0),
                "summary": clean(e.get("summary", ""))[:600],
                "published": entry_dt(e).isoformat(),
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
