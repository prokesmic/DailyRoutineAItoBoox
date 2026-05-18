You are running the AI Reader pipeline. This routine fires once per day; ship items that are new since the last run. Target output volume: 15–30 items per day (picks + citations + 1 brief).

Pipeline output: posts a curated daily brief, the picked articles, and citations extracted from podcast/blog picks, to Readwise Reader's "Inbox" via the Save API. Authentication uses the Readwise token below.

READWISE_TOKEN = <PASTE-YOUR-READWISE-TOKEN-HERE>

CITATION_SOURCES = ["Ethan Mollick", "Andrej Karpathy", "The AI Daily Brief", "Everyday AI", "Latent Space", "Zvi Mowshowitz", "Pragmatic Engineer"]

0. **Cleanup expired Reader items.** List Reader docs via GET https://readwise.io/api/v3/list/ (paginate with pageCursor; auth header `Authorization: Token <READWISE_TOKEN>`). For each doc that has "AI Daily" in its tags AND created_at older than 14 days, DELETE https://readwise.io/api/v3/delete/<id>/. Sleep 350ms between deletes. Log "Cleaned N expired items" to stderr and continue — do not stop on individual delete failures.

1. `git pull --ff-only` so `seen.json` is current.
2. `pip install -r requirements.txt` (quietly).
3. `python fetch.py > candidates.json`. `fetch.py` already filters URLs listed in `seen.json`. If it fails, stop and report. If it returns 0 items, reply "Nothing new this run." and stop — do NOT post anything.

4. Read `profile.md` and `candidates.json`. The reader is a senior pharma IT exec leading the AI strategic pillar in Prague. He listens to **Latent Space**, **The AI Daily Brief** (Whittemore), **Everyday AI** (Wilson), and reads **Ethan Mollick**, **Andrej Karpathy**, **Zvi Mowshowitz**, **Pragmatic Engineer**, **Stratechery**. Pick the way they pick.

5. **Cite-worthiness signals.** A candidate scores higher when it carries one or more of these:
   - **Money attached** — funding round, hyperscaler deal, capex/opex number, restructured contract.
   - **Frontier-lab primary source** — first-party post or researcher's own writing from OpenAI / Anthropic / DeepMind / Mistral / Meta-FAIR / Microsoft / NVIDIA, not press derivatives.
   - **Concrete enterprise or government deployment** — named org, named scope, ideally adoption metrics.
   - **Strategic-shift framing** — explains a change rather than a release note.
   - **Builder write-up with numbers** — token economics, latency / cost, eval scores, internal adoption %.
   - **Reproducible method with weights / code / dataset**, or a benchmark exposing a real failure mode.
   - **Regulator / executive / workforce action with a name and a date**.
   - **AI-for-science with pharma-adjacent angle** — virtual cells, foundation models for biology, AlphaFold-like releases, clinical-trial AI. **High priority.**
   - **Author from CITATION_SOURCES** — Mollick, Karpathy, Daily AI Brief, Everyday AI, Latent Space, Zvi, Pragmatic Engineer. +0.5 implicit bonus because their cited content seeds further saves.
   - **Executive / management thinking** — named CEO/CTO/founder writing or being interviewed on AI strategy, operating model, org design (e.g. Dorsey at Block, exec memos, board fights, leadership transitions).
   - **Viral-thread coverage** — second-hand reporting on consequential X/Twitter threads, research-team announcements, or open-source releases that broke during the window.

6. **Score each candidate 0–10** on: novelty (0.25), depth/rigor (0.25), relevance-to-profile (0.30), signal-vs-hype (0.20). Apply the candidate's `weight` as a multiplier (clamp 0.8–1.2). Down-rank consumer reviews, vendor PR with no new claim, generic "AI is changing X" pieces, beginner explainers, crypto crossover.

7. **Pick up to 12 candidates with weighted score ≥ 5.0.** If fewer than 5 qualify, pick all that qualify (no spread requirement at low volumes). At higher volumes, aim for spread across topic clusters: frontier model moves, enterprise deployment, capital flows/compute, agentic systems, governance/workforce, AI-for-science, builder methodology, executive/management thinking. For each pick write a single sentence (max 25 words) explaining why it matters.

8. Write a **120–200 word editor's note** connecting the picks. Direct, peer-to-peer, no throat-clearing. Lead with the strongest strategic thread. If there are clear groupings, note them briefly (e.g., "three pieces on the subsidy-era reset; two on enterprise deployment; one builder deep-dive.").

9. **Compose the brief HTML** — self-contained page:
   <html><head><meta charset="utf-8"><title>AI Daily — {timestamp}</title>
   <style>body{font-family:Georgia,serif;line-height:1.55;max-width:680px;margin:2em auto;padding:0 1em}
   h1{font-size:1.6em} h3{margin:1.5em 0 .2em;font-size:1.1em}
   .meta{color:#666;font-size:.9em;font-style:italic}
   .blurb{color:#333;margin:.3em 0 .5em}
   .editor{border-left:3px solid #888;padding:.4em 0 .4em 1em;margin:1.2em 0}
   a{color:#000}</style></head><body>
   <h1>AI Daily — {Day, D Month YYYY HH:MM} (Prague)</h1>
   <div class="editor">{editor's note, paragraphs wrapped in <p>}</div><hr/>
   {For each pick:}<h3>{i}. {title}</h3><div class="meta">{source}{if pick.source in CITATION_SOURCES: " · citations to follow"}</div><p class="blurb">{blurb}</p><p><a href="{url}">Read source →</a></p>
   </body></html>
   Use Europe/Prague time. Slug: `BRIEF_SLUG=AI_Daily_$(TZ=Europe/Prague date +%Y-%m-%d_%H%M)`.

10. Save brief locally: `mkdir -p briefs && write HTML to briefs/${BRIEF_SLUG}.html`.

11. **Save the brief to Readwise Reader** — POST https://readwise.io/api/v3/save/ with header `Authorization: Token <READWISE_TOKEN>` and JSON body:
    {"url":"https://raw.githubusercontent.com/prokesmic/DailyRoutineAItoBoox/claude/create-ai-daily-reader-gylCx/briefs/<BRIEF_SLUG>.html","html":"<the brief HTML>","title":"AI Daily — <Day, D Month YYYY HH:MM>","tags":["AI Daily","Brief"],"location":"new","category":"article","should_clean_html":false,"saved_using":"AI Daily routine"}
    Expect HTTP 200/201. If error, report and stop — do not continue.

12. **Save each picked article.** For each pick, POST https://readwise.io/api/v3/save/ with body:
    {"url":"<pick.url>","title":"<pick.title>","summary":"<pick.blurb>","tags":["AI Daily","<pick.source>"],"location":"new","category":"article","saved_using":"AI Daily routine"}
    Sleep 200ms between calls. Track 2xx responses.

13. **Extract and save citations** — for each successfully-saved pick whose source is in CITATION_SOURCES:
    a. WebFetch the pick's URL to get the article body.
    b. Identify the **2–4 most substantive externally-cited items** (arXiv links, GitHub repos with research/academic orientation, named research papers or blog posts the author references substantively, exec memos or interviews quoted). **Skip**: social-media links (twitter/x.com, threads, mastodon, linkedin profile pages), the source site's own related-content links, navigation, footnote ornaments, image embeds, podcast platform links, sponsor/affiliate links.
    c. For each cited URL not already in seen.json, POST to https://readwise.io/api/v3/save/ with body:
       {"url":"<cited URL>","title":"<short descriptive title if inferrable, else hostname + path tail>","summary":"Cited in '<pick.title>' by <pick.source>","tags":["AI Daily","Cited from <pick.source>"],"location":"new","category":"article","saved_using":"AI Daily routine"}
       Sleep 200ms between calls.
    d. Track cited URLs that returned 2xx.

14. **Update seen.json** — append each successfully-saved URL (picks and citations) as {"url":"...","shipped_at":"<ISO-8601 UTC now>"}. Drop entries older than 14 days. Sort by shipped_at descending.

15. **Commit and push** — `git add seen.json briefs/ && git commit -m "ship: +N urls $(date -u +%FT%TZ)" && git push origin HEAD`. If clean, skip.

16. **Reply with exactly one line**: `Sent {N picks} articles + {M citations} citations + 1 brief to Readwise Reader. Cleaned {K} expired items.` Nothing else.
