You are running the AI Reader pipeline. This routine fires three times a day; only ship items that are genuinely new since the last run.

1. `git pull --ff-only` so `seen.json` is current.
2. `pip install -r requirements.txt` (quietly).
3. `python fetch.py > candidates.json`. `fetch.py` already filters out URLs listed in `seen.json`. If it fails, stop and report. If it returns 0 items, reply "Nothing new this run." and stop — do NOT build or upload.
4. Read `profile.md` and `candidates.json`. Score each candidate 0–10 on: novelty, depth, relevance to profile, signal-vs-hype. Compute weighted average (0.3/0.3/0.3/0.1). Apply the candidate's `weight` as a small multiplier (clamp 0.8–1.2). Be ruthless — most AI content is hype or PR.
5. Pick up to 5 with weighted score >= 6.0. If fewer than 3 qualify, reply "Nothing worth shipping this run." and stop. For each pick, write a single sentence (max 25 words) explaining why it matters to the reader.
6. Write a 100–150 word editor's note connecting the picks. Direct, peer-to-peer, no throat-clearing, no "in today's issue."
7. Write `selected.json`:
   {"editor_note": "...", "picks": [{"url":"...","title":"...","source":"...","blurb":"..."}, ...]}
8. `python build_epub.py selected.json` → prints the output path like `out/AI_Daily_YYYY-MM-DD_HHMM.epub`.
9. Use the Google Drive connector to upload the file to a folder named `AIDaily` (create if missing). Use the original filename.
10. Update `seen.json`: append every shipped pick as `{"url":"...","shipped_at":"<ISO-8601 UTC now>"}`, then drop entries older than 14 days. Sort by `shipped_at` descending.
11. Commit and push: `git add seen.json && git commit -m "seen: +N urls $(date -u +%FT%TZ)" && git push origin HEAD`. If the working tree is clean (nothing shipped), skip the commit.
12. Reply with one line: count of articles shipped, total word count, and the GDrive link. Nothing else.
