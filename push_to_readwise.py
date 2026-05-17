"""Push podcast show-note links to Readwise Reader. Run once per batch file."""
import json, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
SEEN_PATH = "/home/user/DailyRoutineAItoBoox/seen.json"
DELAY = 0.2  # 200ms between calls

def load_seen():
    try:
        return {r["url"] for r in json.load(open(SEEN_PATH))}
    except Exception:
        return set()

def save_seen(new_urls, existing_records):
    now = datetime.now(timezone.utc).isoformat()
    records = list(existing_records)
    for url in new_urls:
        records.append({"url": url, "shipped_at": now})
    records.sort(key=lambda x: x.get("shipped_at", ""), reverse=True)
    with open(SEEN_PATH, "w") as f:
        json.dump(records, f, indent=2)

def post(entry):
    url = entry["url"].split("?")[0].rstrip("/")
    source_tag = "Latent Space" if "latent.space" in entry.get("episode_url","") else \
                 "AI Daily Brief" if "aidailybrief" in entry.get("episode_url","") else \
                 "Everyday AI"
    payload = json.dumps({
        "url": url,
        "title": entry.get("title", ""),
        "tags": ["Podcast Mention", source_tag],
        "location": "new",
        "category": "article",
        "saved_using": "AI Daily routine"
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://readwise.io/api/v3/save/",
        data=payload,
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, url
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:120]
        return e.code, f"ERROR {url}: {body}"
    except Exception as ex:
        return 0, f"EXCEPTION {url}: {ex}"

def push_files(paths, tag=None):
    seen_urls = load_seen()
    try:
        existing_records = json.load(open(SEEN_PATH))
    except Exception:
        existing_records = []

    entries = []
    deduped = set(seen_urls)
    for path in paths:
        data = json.load(open(path))
        for entry in data:
            url = entry.get("url","").split("?")[0].rstrip("/")
            if not url or url in deduped:
                continue
            deduped.add(url)
            entries.append({**entry, "url": url})

    print(f"URLs to push: {len(entries)}", flush=True)
    success_urls, errors = [], []
    for i, entry in enumerate(entries):
        status, result = post(entry)
        if 200 <= status < 300:
            success_urls.append(entry["url"])
            if (i+1) % 50 == 0:
                print(f"  {i+1}/{len(entries)} pushed ({status})", flush=True)
        else:
            errors.append(result)
            if len(errors) <= 5:
                print(f"  FAIL [{status}] {result[:80]}", file=sys.stderr, flush=True)
        if i < len(entries) - 1:
            time.sleep(DELAY)

    save_seen(success_urls, existing_records)
    print(f"Done: {len(success_urls)} success, {len(errors)} errors", flush=True)
    return success_urls, errors

if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else [
        "/home/user/DailyRoutineAItoBoox/podcast_urls_all.json",
        "/home/user/DailyRoutineAItoBoox/latent_space_links.json",
    ]
    push_files(files)
