"""Fetch RSS + podcast citations + HN candidates; exclude already-shipped URLs."""
import json, os, re, sys, time
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
        if v:
            return datetime(*v[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def normalise_url(u):
    return u.split("?")[0].rstrip("/").rstrip(")")


# ── Regular RSS feeds ─────────────────────────────────────────────────────────
for feed in cfg.get("rss", []):
    try:
        p = feedparser.parse(feed["url"])
        for e in p.entries[:30]:
            if entry_dt(e) < cutoff:
                continue
            url = normalise_url(e.get("link") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "url": url,
                "title": clean(e.get("title", "")),
                "source": feed["name"],
                "weight": feed.get("weight", 1.0),
                "summary": clean(e.get("summary", ""))[:600],
                "published": entry_dt(e).isoformat(),
            })
    except Exception as ex:
        print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)


# ── Podcast show-notes citation extraction ────────────────────────────────────
# Domains that are never useful article targets (social, podcast infra, tracking)
_SKIP_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "youtube.com", "youtu.be",
    "itunes.apple.com", "podcasts.apple.com", "open.spotify.com",
    "anchor.fm", "transistor.fm", "buzzsprout.com", "podbean.com",
    "simplecast.com", "overcast.fm", "pocketcasts.com",
    "feeds.feedburner.com", "feedproxy.google.com",
    "substack.com/subscribe", "beehiiv.com/subscribe",
    "mailchimp.com", "convertkit.com",
    "amzn.to", "bit.ly", "tinyurl.com", "ow.ly",
}

_URL_RE = re.compile(r'https?://[^\s"\'<>\]]+')
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{5,200})</title>", re.I)


def _extract_cited_urls(html_content, own_domain):
    urls = []
    for m in _URL_RE.finditer(html_content):
        u = normalise_url(m.group(0))
        if len(u) < 20:
            continue
        try:
            domain = u.split("/")[2].lower().lstrip("www.")
        except IndexError:
            continue
        if domain == own_domain:
            continue
        if any(skip in domain for skip in _SKIP_DOMAINS):
            continue
        if u not in seen:
            urls.append(u)
    return list(dict.fromkeys(urls))  # dedupe while preserving order


def _resolve_title(url, client):
    try:
        r = client.get(
            url, timeout=6, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIDailyBot/1.0)"},
        )
        if r.status_code == 200:
            m = _TITLE_RE.search(r.text[:8000])
            if m:
                return clean(m.group(1))
    except Exception:
        pass
    return ""


with httpx.Client(timeout=8) as http_client:
    for feed in cfg.get("podcast_shownotes", []):
        if not feed.get("url"):
            continue
        try:
            own_domain = feed["url"].split("/")[2].lower().lstrip("www.")
            p = feedparser.parse(feed["url"])
            for e in p.entries[:5]:  # only the 5 most recent episodes
                if entry_dt(e) < cutoff:
                    continue
                # gather all HTML content from the entry
                content = "".join(
                    c.get("value", "") for c in (e.get("content") or [])
                )
                content = content or e.get("summary", "")

                cited = _extract_cited_urls(content, own_domain)
                for url in cited[:40]:  # cap per episode to avoid explosion
                    if url in seen:
                        continue
                    seen.add(url)
                    title = _resolve_title(url, http_client) or url
                    out.append({
                        "url": url,
                        "title": title,
                        "source": f"{feed['name']} (cited)",
                        "weight": min(feed.get("weight", 1.0), 1.2),
                        "summary": "",
                        "published": entry_dt(e).isoformat(),
                    })
                    time.sleep(0.05)  # gentle crawl rate
        except Exception as ex:
            print(f"Podcast shownotes error {feed['name']}: {ex}", file=sys.stderr)


# ── Hacker News ───────────────────────────────────────────────────────────────
hn = cfg.get("hackernews", {})
if hn.get("enabled"):
    hn_cutoff_ts = int(
        (datetime.now(timezone.utc) - timedelta(hours=hn["lookback_hours"])).timestamp()
    )
    with httpx.Client(timeout=20) as c:
        for kw in hn.get("keywords", []):
            try:
                r = c.get(
                    f"https://hn.algolia.com/api/v1/search_by_date"
                    f"?query={kw}&tags=story"
                    f"&numericFilters=points>={hn['min_points']},created_at_i>{hn_cutoff_ts}"
                )
                for h in r.json().get("hits", []):
                    url = normalise_url(h.get("url") or "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append({
                        "url": url,
                        "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points', 0)} pts)",
                        "weight": 1.0,
                        "summary": "",
                        "published": datetime.fromtimestamp(
                            h["created_at_i"], tz=timezone.utc
                        ).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)


print(json.dumps(out, ensure_ascii=False, indent=2))
