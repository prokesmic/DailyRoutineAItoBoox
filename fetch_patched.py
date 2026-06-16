"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout.
This version uses httpx + ElementTree instead of feedparser to avoid sgmllib dependency."""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import httpx
import yaml

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
    'atom': 'http://www.w3.org/2005/Atom',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'media': 'http://search.yahoo.com/mrss/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rss1': 'http://purl.org/rss/1.0/',
}

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    # Try ISO 8601
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(s[:len(fmt)], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    # Try RFC 2822 (RSS)
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc)

def text_of(el, *paths):
    for path in paths:
        try:
            found = el.find(path, NS)
            if found is not None and found.text:
                return found.text.strip()
        except Exception:
            pass
    return ""

def attr_of(el, *path_attr_pairs):
    for path, attr in path_attr_pairs:
        try:
            found = el.find(path, NS) if path else el
            if found is not None:
                v = found.get(attr, "")
                if v:
                    return v.strip()
        except Exception:
            pass
    return ""

def parse_feed_content(content, feed_name):
    """Parse RSS/Atom feed content, return list of (url, title, summary, pub_date)."""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"XML parse error for {feed_name}: {e}", file=sys.stderr)
        return items

    tag = root.tag.lower()
    ns_stripped = re.sub(r'\{[^}]*\}', '', root.tag).lower()

    # Atom feed
    if 'atom' in tag or ns_stripped == 'feed':
        entries = root.findall('{http://www.w3.org/2005/Atom}entry')
        if not entries:
            entries = root.findall('entry')
        for entry in entries:
            # URL
            url = ""
            link_el = entry.find('{http://www.w3.org/2005/Atom}link[@rel="alternate"]')
            if link_el is None:
                link_el = entry.find('{http://www.w3.org/2005/Atom}link')
            if link_el is None:
                link_el = entry.find('link[@rel="alternate"]')
            if link_el is None:
                link_el = entry.find('link')
            if link_el is not None:
                url = link_el.get('href', '') or link_el.text or ''
            if not url:
                continue

            # Title
            title = ""
            for tpath in ['{http://www.w3.org/2005/Atom}title', 'title']:
                tel = entry.find(tpath)
                if tel is not None:
                    title = tel.text or ''
                    break

            # Summary
            summary = ""
            for spath in ['{http://www.w3.org/2005/Atom}summary', '{http://www.w3.org/2005/Atom}content', 'summary', 'content']:
                sel = entry.find(spath)
                if sel is not None and sel.text:
                    summary = sel.text
                    break

            # Published
            pub = ""
            for ppath in ['{http://www.w3.org/2005/Atom}published', '{http://www.w3.org/2005/Atom}updated', 'published', 'updated']:
                pel = entry.find(ppath)
                if pel is not None and pel.text:
                    pub = pel.text
                    break

            items.append((url.strip(), clean(title), clean(summary)[:600], parse_date(pub)))

    else:
        # RSS 2.0 / RSS 1.0 (RDF)
        channel = root.find('channel')
        if channel is None:
            channel = root.find('{http://purl.org/rss/1.0/}channel')

        # RSS 1.0 items are at root level
        rss1_items = root.findall('{http://purl.org/rss/1.0/}item')

        rss_items = []
        if channel is not None:
            rss_items = channel.findall('item')
        if not rss_items:
            rss_items = root.findall('.//item')
        if not rss_items and rss1_items:
            rss_items = rss1_items

        for item in rss_items:
            url = ""
            link_el = item.find('link')
            if link_el is not None:
                url = (link_el.text or '').strip()
            if not url:
                # Try guid with isPermaLink
                guid_el = item.find('guid')
                if guid_el is not None and guid_el.get('isPermaLink', 'true').lower() == 'true':
                    url = (guid_el.text or '').strip()
            if not url:
                # RSS 1.0 link
                link_el = item.find('{http://purl.org/rss/1.0/}link')
                if link_el is not None:
                    url = (link_el.text or '').strip()
            if not url:
                continue

            title = ""
            for tpath in ['title', '{http://purl.org/rss/1.0/}title']:
                tel = item.find(tpath)
                if tel is not None:
                    title = tel.text or ''
                    break

            summary = ""
            for spath in ['description', '{http://purl.org/rss/1.0/}description',
                          '{http://purl.org/rss/1.0/modules/content/}encoded']:
                sel = item.find(spath)
                if sel is not None and sel.text:
                    summary = sel.text
                    break

            pub = ""
            for ppath in ['pubDate', '{http://purl.org/dc/elements/1.1/}date', 'published']:
                pel = item.find(ppath)
                if pel is not None and pel.text:
                    pub = pel.text
                    break

            items.append((url.strip(), clean(title), clean(summary)[:600], parse_date(pub)))

    return items


for feed in cfg.get("rss", []):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=FEED_HEADERS) as client:
            resp = client.get(feed["url"])
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code} for {feed['name']}", file=sys.stderr)
            continue
        entries = parse_feed_content(resp.content, feed["name"])
        count = 0
        for url, title, summary, pub_dt in entries[:25]:
            if pub_dt < cutoff:
                continue
            url = url.split("?")[0].rstrip("/")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "url": url, "title": title,
                "source": feed["name"], "weight": feed.get("weight", 1.0),
                "summary": summary,
                "published": pub_dt.isoformat(),
            })
            count += 1
        print(f"  {feed['name']}: {count} new items (from {len(entries)} entries)", file=sys.stderr)
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
                added = 0
                for h in r.json().get("hits", []):
                    url = (h.get("url") or "").split("?")[0].rstrip("/")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    out.append({
                        "url": url, "title": clean(h.get("title") or ""),
                        "source": f"HN ({h.get('points',0)} pts)", "weight": 1.0,
                        "summary": "", "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
                    added += 1
                if added:
                    print(f"  HN '{kw}': {added} new items", file=sys.stderr)
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
