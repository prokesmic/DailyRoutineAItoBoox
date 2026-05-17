"""Push URLs to Readwise with rate-limit backoff. Pass batch file as argv[1]."""
import json, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

TOKEN = "ki1asfY3iIUnB3Zo7Zo3Rgn9FgVph8q8k7OMX6g2wZb2z2foAx"
SEEN_PATH = "/home/user/DailyRoutineAItoBoox/seen.json"
BASE_DELAY = 3.5        # seconds — stays under 20 req/min
RETRY_WAIT  = 65        # seconds to wait after a 429

def load_seen():
    try:
        return json.load(open(SEEN_PATH))
    except Exception:
        return []

def save_seen(records):
    records.sort(key=lambda x: x.get("shipped_at",""), reverse=True)
    with open(SEEN_PATH, "w") as f:
        json.dump(records, f, indent=2)

def source_tag(episode_url):
    if "latent.space" in episode_url:   return "Latent Space"
    if "aidailybrief" in episode_url:   return "AI Daily Brief"
    return "Everyday AI"

def post_one(entry):
    url = entry["url"]
    payload = json.dumps({
        "url": url,
        "title": entry.get("title",""),
        "tags": ["Podcast Mention", source_tag(entry.get("episode_url",""))],
        "location": "new",
        "category": "article",
        "saved_using": "AI Daily routine",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://readwise.io/api/v3/save/",
        data=payload,
        headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

def main(batch_path):
    entries = json.load(open(batch_path))
    records = load_seen()
    seen_urls = {r["url"] for r in records}

    todo = [e for e in entries if e["url"] not in seen_urls]
    total = len(todo)
    print(f"Pushing {total} URLs at ~{BASE_DELAY}s/call …", flush=True)

    success, fail, skip_429 = 0, 0, 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, entry in enumerate(todo):
        status = post_one(entry)
        if 200 <= status < 300:
            success += 1
            records.append({"url": entry["url"], "shipped_at": now_iso})
        elif status == 429:
            skip_429 += 1
            print(f"  429 at {i+1}/{total} — waiting {RETRY_WAIT}s …", flush=True)
            time.sleep(RETRY_WAIT)
            # retry once
            status2 = post_one(entry)
            if 200 <= status2 < 300:
                success += 1
                records.append({"url": entry["url"], "shipped_at": now_iso})
            else:
                fail += 1
                print(f"  retry failed [{status2}] {entry['url'][:70]}", file=sys.stderr, flush=True)
        else:
            fail += 1
            if fail <= 10:
                print(f"  FAIL [{status}] {entry['url'][:70]}", file=sys.stderr, flush=True)

        if (i+1) % 25 == 0:
            save_seen(records)
            print(f"  checkpoint {i+1}/{total} — {success} ok, {fail} fail, {skip_429} throttled", flush=True)

        time.sleep(BASE_DELAY)

    save_seen(records)
    print(f"Done: {success} success / {fail} fail / {skip_429} 429s (retried)", flush=True)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "remaining_urls.json")
