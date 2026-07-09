---
name: finance-agent
description: >
  Turns credit-card statement PDFs into a categorized personal-spending Google Sheet.
  Use when the user says "procesa mis estados de cuenta", "process my statements",
  "categoriza mis gastos", "finance ledger", or drops bank statement PDFs to be tallied.
  Reads each PDF, categorizes transactions, and writes them to a Google Sheet the user owns.
---

# Finance Ledger

Personal credit-card ledger automation. The user drops statement PDFs in a folder; you
extract, categorize, and write the transactions to their own Google Sheet. One person's
spending — there is no split between people.

**The full, authoritative step-by-step flow is in `AGENTS.md` in this repo. Follow it.**
This file is the Claude Code entry point; the flow is identical for any agent.

## Quick reference

- **First run / not configured yet** (`config.json` missing): do the "First-time setup"
  in `AGENTS.md` — create the venv, install `requirements.txt`, confirm `oauth_client.json`
  exists, then run `scripts/setup.py` (opens a browser for the user to authorize with their
  own Google account and creates the Sheet).
- **Monthly run**: follow steps 1–9 in `AGENTS.md`:
  1. `find_pending.py` → unprocessed PDFs.
  2. **You read each PDF** and write `tmp_extraction_<period>.json` (schema in AGENTS.md;
     include `declared_total` = the statement's total new charges for the period).
  3. `reconcile.py` — do not skip; fix the extraction if it reports a mismatch.
  4. `build_learning.py` → `tmp_learned.json`.
  5. `categorize.py` → `tmp_categorized_<period>.json`.
  6. Web-guess the `other` merchants yourself (no questions); edit the JSON.
  7. `write_to_sheet.py`.
  8. `mark_processed.py`.
  9. Report the month's total + top categories; note any `other` rows for the user to fix.

Run scripts with `./.venv/bin/python scripts/<name>.py` from the repo root. Never commit
`token.json`, `config.json`, or PDFs.
