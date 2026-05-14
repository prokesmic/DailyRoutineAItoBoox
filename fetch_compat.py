"""Fetch RSS + HN candidates, exclude already-shipped URLs, print JSON to stdout.
Drop-in replacement for fetch.py using stdlib XML parser instead of feedparser."""
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

def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

def get_text(el, *paths):
    for path in paths:
        for ns_name, ns_uri in [('', '')] + list(NS.items()):
            try:
                found = el.find(path.format(ns=ns_name + ':' if ns_name else '', nsuri=ns_uri))
                if found is not None and found.text:
                    return found.text.strip()
            except Exception:
                pass
        # try with explicit namespace
        for ns_name, ns_uri in NS.items():
            try:
                found = el.find(path.replace('{ns}', '{' + ns_uri + '}'))
                if found is not None and found.text:
                    return found.text.strip()
            except Exception:
                pass
    return ""

def parse_feed(content):
    """Parse RSS or Atom feed, return list of (url, title, date_str, summary)."""
    items = []
    try:
        root = ET.fromstring(content)
    except Exception as ex:
        print(f"XML parse error: {ex}", file=sys.stderr)
        return items

    tag = root.tag.lower()
    # Strip namespace
    if '}' in tag:
        tag = tag.split('}')[1]

    if tag == 'feed':
        # Atom
        atom_ns = 'http://www.w3.org/2005/Atom'
        for entry in root.findall(f'{{{atom_ns}}}entry') or root.findall('entry'):
            # Get link
            url = ''
            for link in (entry.findall(f'{{{atom_ns}}}link') or entry.findall('link')):
                rel = link.get('rel', 'alternate')
                if rel in ('alternate', '') or rel is None:
                    url = link.get('href', '')
                    if url:
                        break
            if not url:
                url = (entry.findtext(f'{{{atom_ns}}}id') or entry.findtext('id') or '').strip()

            title = (entry.findtext(f'{{{atom_ns}}}title') or entry.findtext('title') or '').strip()
            date_str = (entry.findtext(f'{{{atom_ns}}}published') or
                        entry.findtext(f'{{{atom_ns}}}updated') or
                        entry.findtext('published') or entry.findtext('updated') or '')
            summary_el = (entry.find(f'{{{atom_ns}}}summary') or
                          entry.find(f'{{{atom_ns}}}content') or
                          entry.find('summary') or entry.find('content'))
            summary = (summary_el.text if summary_el is not None else '') or ''
            items.append((url, title, date_str, summary))
    else:
        # RSS 2.0
        channel = root.find('channel')
        if channel is None:
            channel = root
        for item in channel.findall('item'):
            url = (item.findtext('link') or '').strip()
            if not url:
                # Try guid
                guid = item.find('guid')
                if guid is not None and guid.get('isPermaLink', 'true').lower() == 'true':
                    url = (guid.text or '').strip()
            title = (item.findtext('title') or '').strip()
            date_str = (item.findtext('pubDate') or
                        item.findtext(f'{{{NS["dc"]}}}date') or '')
            desc = item.find('description')
            summary = (desc.text if desc is not None else '') or ''
            items.append((url, title, date_str, summary))

    return items

with httpx.Client(timeout=20, follow_redirects=True,
                  headers={'User-Agent': 'AI-Daily-Reader/1.0'}) as client:
    for feed in cfg.get("rss", []):
        try:
            r = client.get(feed["url"])
            r.raise_for_status()
            items = parse_feed(r.content)
            for url_raw, title, date_str, summary in items[:25]:
                try:
                    pub = parse_date(date_str)
                except Exception:
                    pub = datetime.now(timezone.utc)
                if pub < cutoff:
                    continue
                url = url_raw.split("?")[0].rstrip("/")
                if not url or url in seen:
                    continue
                seen.add(url)
                out.append({
                    "url": url,
                    "title": clean(title),
                    "source": feed["name"],
                    "weight": feed.get("weight", 1.0),
                    "summary": clean(summary)[:600],
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
                        "source": f"HN ({h.get('points',0)} pts)",
                        "weight": 1.0,
                        "summary": "",
                        "published": datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc).isoformat(),
                    })
            except Exception as ex:
                print(f"HN error {kw}: {ex}", file=sys.stderr)

print(json.dumps(out, ensure_ascii=False, indent=2))
