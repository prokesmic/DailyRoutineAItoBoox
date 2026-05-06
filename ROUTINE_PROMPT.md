You are running the AI Reader pipeline. This routine fires three times a day; only ship items that are genuinely new since the last run.

1. `git pull --ff-only` so `seen.json` is current.
2. `pip install -r requirements.txt` (quietly).
3. `python fetch.py > candidates.json`. `fetch.py` already filters out URLs listed in `seen.json`. If it fails, stop and report. If it returns 0 items, reply "Nothing new this run." and stop — do NOT build or upload.
4. Read `profile.md` and `candidates.json`. The reader is a senior pharma IT exec leading the AI strategic pillar in Prague. He listens to **Latent Space**, **The AI Daily Brief** (Whittemore), and **Everyday AI** (Wilson). Pick the way they pick.

5. **Cite-worthiness signals.** A candidate scores higher when it carries one or more of these. Note which apply before you score:
   - **Money attached** — funding round, hyperscaler deal, capex/opex number, restructured contract.
   - **Frontier-lab primary source** — first-party post or researcher's own writing from OpenAI / Anthropic / DeepMind / Mistral / Meta-FAIR / Microsoft / NVIDIA, not press derivatives.
   - **Concrete enterprise or government deployment** — named org, named scope, ideally adoption metrics (Microsoft Work Trend Index, McKinsey, a16z, KPMG, JPMorgan, Menlo VC).
   - **Strategic-shift framing** — explains a change (subsidy era ending, agents-as-products, exclusivity dropping, services pivot, OpEx→CapEx) rather than a release note.
   - **Builder write-up with numbers** — token economics, latency / cost, eval scores, internal adoption % — Cursor, Cognition, Shopify, Notion, Stripe-flavored posts.
   - **Reproducible method with weights / code / dataset** — checkpoint released, dataset open, repo public; or a benchmark that exposes a real failure mode.
   - **Regulator / executive / workforce action with a name and a date** — verdict, filing, board fight, named layoff, named hire.
   - **AI-for-science with pharma-adjacent angle** — virtual cells, foundation models for biology, AlphaFold-like releases, clinical-trial AI, materials discovery. **High priority for this reader specifically.**

6. **Score each candidate 0–10** on: novelty (0.25), depth/rigor (0.25), relevance-to-profile (0.30), signal-vs-hype (0.20). Apply the candidate's `weight` as a multiplier (clamp 0.8–1.2). Down-rank pure consumer reviews, vendor PR with no new claim, generic "AI is changing X" think pieces, beginner explainers, and crypto crossover. Up-rank items that match two or more cite-worthiness signals.

7. **Pick up to 7 candidates with weighted score >= 5.5.** If fewer than 3 qualify, reply "Nothing worth shipping this run." and stop. Aim for spread across at least three of these clusters:
   - Frontier model / lab moves
   - Enterprise deployment & implementation gap
   - Capital flows / compute & energy economics
   - Agentic systems & coding agents in production
   - Governance, regulation, workforce
   - AI-for-science / pharma-adjacent
   - Builder/practitioner methodology

   For each pick write a single sentence (max 25 words) explaining why it matters to the reader, calling out which cite-worthiness signal(s) apply.

8. Write a 120–180 word editor's note connecting the picks. Direct, peer-to-peer, no throat-clearing, no "in today's issue." Lead with the strongest strategic thread; connect the others to it. If the day has a single dominant story, name it openly.

9. Write `selected.json`:
   {"editor_note": "...", "picks": [{"url":"...","title":"...","source":"...","blurb":"..."}, ...]}

10. `python build_epub.py selected.json` → prints `out/AI_Daily_YYYY-MM-DD_HHMM.epub`.
11. Use the Google Drive connector to upload the file to a folder named `AIDaily` (create if missing). Use the original filename.
12. Update `seen.json`: append every shipped pick as `{"url":"...","shipped_at":"<ISO-8601 UTC now>"}`, drop entries older than 14 days, sort by `shipped_at` descending.
13. Commit and push: `git add seen.json && git commit -m "seen: +N urls $(date -u +%FT%TZ)" && git push origin HEAD`. If clean, skip.
14. Reply with one line: count of articles shipped, total word count, and the GDrive link. Nothing else.
