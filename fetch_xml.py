"""Fetch RSS/Atom candidates using xml.etree + httpx; no feedparser needed."""
import json, os, re, sys, time
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
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

def clean(s):
    return " ".join(re.sub(r"<[^>]+>", "", s or "").split())

def parse_date(s):
    if not s: return None
    s = s.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return None

def fetch_feed(url):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        print(f"fetch error {url}: {e}", file=sys.stderr)
        return None

def parse_rss(content, feed_name, feed_weight):
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"XML parse error ({feed_name}): {e}", file=sys.stderr)
        return items

    # Atom feed
    atom_ns = 'http://www.w3.org/2005/Atom'
    if root.tag in (f'{{{atom_ns}}}feed', 'feed') or root.tag.endswith('}feed'):
        for entry in root.findall(f'{{{atom_ns}}}entry') or root.findall('entry') or root.iter('{http://www.w3.org/2005/Atom}entry'):
            link_el = entry.find(f'{{{atom_ns}}}link') or entry.find('link')
            url = ''
            if link_el is not None:
                url = link_el.get('href', '') or link_el.text or ''
            url = url.split('?')[0].rstrip('/')
            if not url or url in seen: continue
            
            title_el = entry.find(f'{{{atom_ns}}}title') or entry.find('title')
            title = clean(title_el.text if title_el is not None else '')
            
            updated_el = entry.find(f'{{{atom_ns}}}updated') or entry.find(f'{{{atom_ns}}}published') or entry.find('updated') or entry.find('published')
            pub_date = parse_date(updated_el.text if updated_el is not None else None) or datetime.now(timezone.utc)
            
            if pub_date < cutoff: continue
            
            summary_el = entry.find(f'{{{atom_ns}}}summary') or entry.find(f'{{{atom_ns}}}content') or entry.find('summary') or entry.find('content')
            summary = clean(summary_el.text if summary_el is not None else '')[:600]
            
            seen.add(url)
            items.append({'url': url, 'title': title, 'source': feed_name, 'weight': feed_weight,
                         'summary': summary, 'published': pub_date.isoformat()})
        return items

    # RSS feed
    channel = root.find('channel') or root
    for item in channel.findall('.//item'):
        link_el = item.find('link')
        url = (link_el.text or '').strip().split('?')[0].rstrip('/') if link_el is not None else ''
        if not url or url in seen: continue
        
        title_el = item.find('title')
        title = clean(title_el.text if title_el is not None else '')
        
        pub_el = item.find('pubDate') or item.find('{http://purl.org/dc/elements/1.1/}date')
        pub_date = parse_date(pub_el.text if pub_el is not None else None) or datetime.now(timezone.utc)
        
        if pub_date < cutoff: continue
        
        desc_el = item.find('{http://purl.org/rss/1.0/modules/content/}encoded') or item.find('description')
        summary = clean(desc_el.text if desc_el is not None else '')[:600]
        
        seen.add(url)
        items.append({'url': url, 'title': title, 'source': feed_name, 'weight': feed_weight,
                     'summary': summary, 'published': pub_date.isoformat()})
    return items

for feed in cfg.get("rss", []):
    try:
        content = fetch_feed(feed["url"])
        if content:
            items = parse_rss(content, feed["name"], feed.get("weight", 1.0))
            out.extend(items[:25])
    except Exception as ex:
        print(f"RSS error {feed['name']}: {ex}", file=sys.stderr)

# HN
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
