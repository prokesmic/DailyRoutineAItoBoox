You are running the AI Reader pipeline. This routine fires three times a day; only ship items that are genuinely new since the last run.

Pipeline output: posts a curated daily brief and the picked articles to Readwise Reader's "Inbox" via the Save API. Authentication uses the Readwise token stored as `READWISE_TOKEN` (routine secret).

---

## Steps

1. `git pull --ff-only` so `seen.json` is current.
2. `pip install -r requirements.txt` (quietly). If it fails, fall back to installing feedparser, httpx, PyYAML individually via a venv at `/tmp/aipipe_venv`.
3. `python fetch.py > candidates.json`. `fetch.py`:
   - Pulls from all RSS feeds with a 72-hour look-back window.
   - For each podcast listed under `podcast_shownotes` in `feeds.yaml`, fetches up to 5 recent episode pages, extracts every outbound article link, resolves page titles via HTTP, and adds them as individual candidates tagged `(cited)`. This surfaces papers, blog posts, and analyses mentioned in Latent Space, The AI Daily Brief, Everyday AI, How I AI, and any other podcast added to the config.
   - Pulls qualifying Hacker News stories with a 24-hour look-back.
   - Filters out every URL already in `seen.json`.
   - If `fetch.py` exits non-zero, stop and report the error.
   - If it returns 0 items, reply "Nothing new this run." and stop — do NOT post anything.

4. Read `profile.md` and `candidates.json`. The reader is a senior pharma IT exec leading the AI strategic pillar in Prague. He listens to **Latent Space**, **The AI Daily Brief** (Whittemore), and **Everyday AI** (Wilson). Pick the way they pick.

---

## Scoring

### 5. Cite-worthiness signals
A candidate scores higher when it carries one or more of these:

- **Money attached** — funding round, hyperscaler deal, capex/opex number, restructured contract.
- **Frontier-lab primary source** — first-party post or researcher's own writing from OpenAI / Anthropic / DeepMind / Mistral / Meta-FAIR / Microsoft / NVIDIA, not press derivatives.
- **Concrete enterprise or government deployment** — named org, named scope, ideally adoption metrics.
- **Strategic-shift framing** — explains a change (subsidy era ending, agents-as-products, services pivot, OpEx→CapEx) rather than a release note.
- **Builder write-up with numbers** — token economics, latency / cost, eval scores, internal adoption %.
- **Reproducible method with weights / code / dataset** — checkpoint released, dataset open, repo public; or a benchmark exposing a real failure mode.
- **Regulator / executive / workforce action with a name and a date** — verdict, filing, named layoff, named hire.
- **AI-for-science with pharma-adjacent angle** — virtual cells, foundation models for biology, AlphaFold-like releases, clinical-trial AI, materials discovery. **Highest priority for this reader.**
- **Cited by 2+ podcast sources** — if the same URL appears across multiple `(cited)` candidates from different podcasts, treat this as a strong signal of community consensus; apply a 0.15 bonus to the final weighted score.

### 6. Weighted score
Score each candidate 0–10 on four dimensions, then multiply by the candidate's `weight` (clamped to 0.8–1.2):

| Dimension | Weight |
|---|---|
| Novelty | 0.25 |
| Depth / rigor | 0.25 |
| Relevance to profile | 0.30 |
| Signal vs. hype | 0.20 |

**Down-rank:** consumer reviews, vendor PR with no new claim, generic "AI is changing X" pieces, beginner explainers, crypto crossover.
**Up-rank:** two or more cite-worthiness signals; cited by multiple podcasts; authored by Ethan Mollick, Andrej Karpathy, or other high-signal individuals in feeds.

### 7. Selection
Pick **up to 7 candidates with weighted score ≥ 5.5**. If fewer than 3 qualify, reply "Nothing worth shipping this run." and stop.

Aim for spread across at least three clusters:

- Frontier model / lab moves
- Enterprise deployment & implementation gap
- Capital flows / compute & energy economics
- Agentic systems & coding agents in production
- Governance, regulation, workforce
- AI-for-science / pharma-adjacent
- Builder / practitioner methodology

For each pick write a single sentence (max 25 words) explaining why it matters to this reader.

---

## Brief

### 8. Editor's note
Write a 120–180 word editor's note connecting the picks. Direct, peer-to-peer, no throat-clearing, no "in today's issue." Lead with the strongest strategic thread; connect the others to it. If the day has one dominant story, name it openly.

### 9. Compose the brief HTML
Build a single self-contained HTML page:

```html
<html><head><meta charset="utf-8"><title>AI Daily — {Day, D Month YYYY HH:MM Prague}</title>
<style>body{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}
h1{font-size:1.6em} h3{margin:1.5em 0 .2em;font-size:1.1em}
.meta{color:#666;font-size:.9em;font-style:italic}
.blurb{color:#333;margin:.3em 0 .5em}
.editor{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0;color:#222}
a{color:#000}</style></head>
<body>
<h1>AI Daily — {Day, D Month YYYY HH:MM} (Prague)</h1>
<div class="editor">{editor's note, paragraphs in <p>}</div>
<hr/>
{For each pick:}
  <h3>{i}. {title}</h3>
  <div class="meta">{source}</div>
  <p class="blurb">{blurb}</p>
  <p><a href="{url}">Read source →</a></p>
</body></html>
```

Use Europe/Prague time. Compute: `BRIEF_SLUG=AI_Daily_$(TZ=Europe/Prague date +%Y-%m-%d_%H%M)`.

---

## Delivery

### 10. Save brief locally
`mkdir -p briefs && <write HTML to briefs/${BRIEF_SLUG}.html>`

### 11. Save the brief to Readwise Reader
POST `https://readwise.io/api/v3/save/` with header `Authorization: Token $READWISE_TOKEN` and JSON body:
```json
{
  "url": "https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/create-ai-daily-reader-gylCx/briefs/<BRIEF_SLUG>.html",
  "html": "<the brief HTML>",
  "title": "AI Daily — <Day, D Month YYYY HH:MM>",
  "author": "AI Daily routine",
  "tags": ["AI Daily", "Brief"],
  "location": "new",
  "category": "article",
  "should_clean_html": false,
  "saved_using": "AI Daily routine"
}
```
Expect HTTP 200 or 201. If error, report and stop — do NOT continue to step 12.

### 12. Save each picked article
For each pick, POST `https://readwise.io/api/v3/save/` with body:
```json
{
  "url": "<pick.url>",
  "title": "<pick.title>",
  "summary": "<pick.blurb>",
  "tags": ["AI Daily", "<pick.source>"],
  "location": "new",
  "category": "article",
  "saved_using": "AI Daily routine"
}
```
Sleep 200 ms between calls. Track 2xx responses; only those URLs go into `seen.json`. Log non-2xx to stderr and continue.

### 13. Update seen.json
Append each successfully-posted URL as `{"url":"...","shipped_at":"<ISO-8601 UTC>"}`. Drop entries older than 14 days. Sort by `shipped_at` descending.

### 14. Commit and push
```
git add seen.json briefs/ && git commit -m "ship: +N urls $(date -u +%FT%TZ)" && git push origin HEAD
```
If working tree is clean, skip.

### 15. Reply
Exactly one line: `Sent {N} articles + 1 brief to Readwise Reader.` Nothing else.
