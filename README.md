# AI Daily Reader

Daily-cadence Claude Code routine that:

1. Pulls fresh AI articles from a curated RSS + Hacker News set (see `feeds.yaml`).
2. Filters URLs already shipped (`seen.json`).
3. Scores candidates against the reader profile (`profile.md`) using cite-worthiness signals modelled on Latent Space, The AI Daily Brief, and Everyday AI.
4. Picks up to 7 articles with a weighted score ≥ 5.5.
5. Composes an editor's note connecting the picks.
6. Saves an HTML brief + each picked article to Readwise Reader's inbox via the Save API.
7. Commits `seen.json` and the archived brief HTML back to this branch.

## Routine secrets

- `READWISE_TOKEN` — from https://readwise.io/access_token

## Cadence

Three times daily (Prague local time): 06:00, 13:00, 20:00. Lookback per run is 14 hours; `seen.json` prevents duplicates within a 14-day window.

## Files

- `feeds.yaml` — RSS sources + HN config
- `profile.md` — reader profile
- `fetch.py` — pulls candidates, filters against `seen.json`
- `build_epub.py` — (legacy, unused since switching to Readwise Reader; kept for archival)
- `ROUTINE_PROMPT.md` — the prompt the routine executes
- `seen.json` — rolling 14-day URL ledger, committed back each successful run
- `briefs/` — archived HTML briefs, one per run
