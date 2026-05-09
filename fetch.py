"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout."""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
import feedparser, httpx, yaml

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

def entry_dt(e):
    for k in ("published_parsed", "updated_parsed"):
        v = getattr(e, k, None) or e.get(k)
        if v: return datetime(*v[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

for feed in cfg.get("rss", []):
    try:
        p = feedparser.parse(feed["url"])
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
