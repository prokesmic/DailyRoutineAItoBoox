# AI Daily Reader

Claude Code routine that builds a curated daily AI brief and pushes it — plus the picked articles and their key citations — to Readwise Reader.

## Daily flow (single run, 15:00 Prague)

1. **Cleanup** — deletes Reader items tagged `AI Daily` older than 14 days.
2. **Fetch** — pulls candidates from 27 RSS feeds + Hacker News (24h lookback). `fetch.py` filters URLs already in `seen.json`.
3. **Score & pick** — Claude scores each candidate against 9 cite-worthiness signals (modelled on Latent Space, The AI Daily Brief, Everyday AI). Picks up to 7 with weighted score ≥ 5.5, spread across topic clusters.
4. **Editor's note** — 120–180 word peer-to-peer note connecting the picks.
5. **Brief** — self-contained HTML page with note + table of picks. Committed to `briefs/` for archival.
6. **Save to Readwise Reader** —
   - 1× brief at the top of inbox (`AI Daily — <date>`)
   - Up to 7 picked articles, each tagged `AI Daily` + source
7. **Extract citations** — for each pick from a citation-source feed (Mollick, Karpathy, Latent Space, AI Daily Brief, Everyday AI), Claude WebFetches the body and saves the 1–3 most substantive cited studies/papers/articles as separate Reader items, tagged `Cited from <source>`.
8. **Commit state** — `seen.json` (rolling 14-day URL ledger) and the brief HTML.
9. **Report** — one line: `Sent N articles + M citations + 1 brief to Readwise Reader.`

## Citation-source feeds

These five feeds get the citation-extraction treatment in step 7:
- Ethan Mollick — One Useful Thing
- Andrej Karpathy — karpathy.github.io
- The AI Daily Brief — Whittemore
- Everyday AI — Wilson
- Latent Space — swyx + Alessio

## Files

- `feeds.yaml` — 27 RSS sources + HN config
- `profile.md` — reader profile
- `fetch.py` — pulls candidates, filters against `seen.json`
- `ROUTINE_PROMPT.md` — the prompt the routine executes
- `seen.json` — rolling 14-day URL ledger, committed back each run
- `briefs/` — archived HTML briefs, one per run
- `build_epub.py` — legacy, unused since switching to Readwise

## Authentication

The Readwise API token is inlined in the routine prompt (the routines UI doesn't support secrets). Rotate via https://readwise.io/access_token whenever you want a clean slate.
