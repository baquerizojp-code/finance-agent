# Roadmap

Working document for polishing finance_agent before (and after) sharing it. Ordered by
priority; check items off as they land. Findings come from the initial code review
(2026-07-09), where the offline pipeline (reconcile → build_learning → categorize) was
smoke-tested and works.

## P0 — Real bugs (fix before sharing)

- [ ] **Rules-tab manual edits are wiped on every run.**
  README/AGENTS.md promise the user can teach rules by editing the `Rules` tab, but
  `write_to_sheet.py` → `sync_rules_to_sheet()` does `ws.clear()` and overwrites the tab
  from local `rules.json` (`scripts/sheets_sync.py:172`). `sync_rules_from_sheet()` exists
  but is never called.
  **Fix:** before overwriting, read the tab and merge sheet-side edits into `rules.json`
  (sheet wins on conflict for `manual` rules).

- [ ] **`rules.json` is committed but mutated at runtime.**
  Web-guess caching appends `auto` rules into the versioned `rules.json`, so every run
  dirties the working tree and `git pull` updates will conflict for users.
  **Fix:** rename the committed seed to `rules.seed.json`, gitignore `rules.json`, and have
  `setup.py` copy seed → `rules.json` when missing (same pattern as `config.example.json`).

## P0 — Maintainer setup (blocks the "share with friends" story)

- [ ] Create the Google OAuth **Desktop app** client in GCP (steps in `MAINTAINER.md`),
  commit it as `oauth_client.json`, and publish the consent screen to production.
- [x] Create the public GitHub repo and replace the `<owner>` placeholders in `README.md`.

## P1 — Robustness

- [ ] **Idempotency between write (step 7) and mark-processed (step 8).**
  If the agent dies after `write_to_sheet.py` but before `mark_processed.py`, a re-run
  duplicates every transaction row and the MonthlySummary row.
  **Fix:** `write_to_sheet.py` should warn/abort when rows with the same `archivo` already
  exist in Transactions.
- [ ] **MonthlySummary should upsert by period, not append.**
  Two statements for the same month (e.g. two cards), or a reprocess, produce duplicate
  `mes` rows that each SUMIFS the whole month. Replace the existing period row instead of
  appending a second one.

## P2 — Improvements

- [ ] Fuzzy match never fires for wildcard-wrapped patterns: `categorize.py:127` strips only
  trailing `*`/`?`; use `.strip("*?")` so `*NETFLIX*` compares as `NETFLIX`.
- [ ] `write_to_sheet.py` opens the spreadsheet 3 times (each helper builds its own client).
  Build one `gspread.Client` and pass it through.
- [ ] `find_pending.py` only globs lowercase `*.pdf`; make the match case-insensitive so
  `ESTADO.PDF` isn't silently skipped.
- [ ] Bump the documented Python requirement to 3.10+ (3.9 is EOL; google-auth warns on
  every run).
- [ ] Dead code: `email` in `scripts/auth.py:83` is computed and never used.

## Ideas / later

- [ ] Optional Excel/CSV output for users who don't want Google Sheets (README currently
  only promises Sheets).
- [ ] A tiny offline test suite (fixtures like the ones used in the review smoke test) run
  via CI, so contributions from friends don't break the pipeline.
