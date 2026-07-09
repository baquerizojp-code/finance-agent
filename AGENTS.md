# finance_agent — instructions for the coding agent

You are automating a **personal credit-card ledger**. The user drops PDF statements in a
folder; you extract the transactions, categorize them, and write them to a Google Sheet
the user owns. This is the canonical flow for **any** agent (Claude Code, Codex, etc.).
There is no split between people — it is one person's spending.

All commands run from the repo root. Use the project virtualenv:
`./.venv/bin/python scripts/<name>.py` (create it once — see "First-time setup").

---

## First-time setup (run once per user)

1. Create the venv and install deps:
   ```bash
   python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
   ```
2. Confirm `oauth_client.json` exists at the repo root. If not, the repo was shared
   without it — tell the user to get it from whoever shared the repo (see MAINTAINER.md).
3. Ask the user which folder they'll drop statement PDFs in, then run:
   ```bash
   ./.venv/bin/python scripts/setup.py --statements-folder "<folder>" --sheet-name "<name>"
   ```
   This opens a browser (the user authorizes with **their own** Google account), creates
   the Sheet in their Drive, and writes `config.json`. Show them the printed Sheet URL.

---

## Processing statements (the monthly run)

### Step 1 — Find unprocessed PDFs
```bash
./.venv/bin/python scripts/find_pending.py
```
Prints a JSON list of PDFs not yet processed. If empty, tell the user there's nothing new.
Process multiple PDFs oldest-first.

### Step 2 — For each pending PDF, extract transactions yourself
**Read the PDF** and produce a normalized extraction file at the repo root named
`tmp_extraction_<period>.json` with this exact schema:
```json
{
  "period": "YYYY-MM",
  "declared_total": 1234.56,
  "transactions": [
    {"date": "YYYY-MM-DD", "merchant": "AS PRINTED", "amount": 12.30, "txn_type": "cargo"}
  ]
}
```
Rules for extraction:
- `period` = the statement's billing month (YYYY-MM).
- `txn_type` is one of: `cargo` (a purchase/charge), `pago` (a payment toward the card),
  `credito` (a refund/credit). When unsure, use `cargo`.
- `amount` is always a positive number.
- `merchant` = the description as printed (don't clean it up; rules handle variants).
- `declared_total` = the statement figure that covers **exactly the set of lines you typed
  as `cargo`** — reconciliation sums your `cargo` amounts and compares them to this number,
  so the two must describe the same universe of charges. Start from the statement's "total
  new charges / total consumos for the period" (NOT the new balance, which includes prior
  balance). **Interest / finance charges:** if the statement lists them separately and your
  "consumos" total excludes them, but you record them as `cargo` (e.g. category `fees`),
  then add those charges into `declared_total` so it still matches your `cargo` lines. When
  in doubt, make `declared_total` = the exact sum of everything you marked `cargo`.
- Include every line, including payments and credits.

### Step 3 — Reconcile (do NOT skip)
```bash
./.venv/bin/python scripts/reconcile.py tmp_extraction_<period>.json
```
If it exits non-zero (mismatch), your extraction dropped or duplicated rows, or you picked
the wrong `declared_total`. Fix the extraction and re-run. Only continue once it reconciles
(or the user explicitly tells you to proceed anyway).

### Step 4 — Build the category-learning index
```bash
./.venv/bin/python scripts/build_learning.py --output tmp_learned.json
```

### Step 5 — Categorize
```bash
./.venv/bin/python scripts/categorize.py tmp_extraction_<period>.json \
    --learned tmp_learned.json --source-file "<pdf filename>" \
    --output tmp_categorized_<period>.json
```
Category is auto-filled from history → rules → `other`. Rows left `other` are new merchants.

### Step 6 — Web-guess the `other` merchants (no questions)
Open `tmp_categorized_<period>.json`. For each entry with `"category": "other"` and
`"needs_review": true`, infer the business type (web search if useful) and set `category`
to the best fit from the list in `config.json` (`categories`). Set `needs_review` to false.
Do this yourself, non-interactively — do not ask the user. Skip `pago`/`credito` rows.

### Step 7 — Write to the Sheet
```bash
./.venv/bin/python scripts/write_to_sheet.py tmp_categorized_<period>.json
```
Appends the rows, appends a MonthlySummary row (live per-category formulas), and caches the
web-guesses as reusable rules.

### Step 8 — Mark processed
```bash
./.venv/bin/python scripts/mark_processed.py "<pdf path>" <period>
```

### Step 9 — Report
Tell the user: the period processed, the month's total spending, and the top categories.
If any merchants stayed `other`, tell them they can fix the `categoria` directly in the
Sheet — the MonthlySummary recomputes automatically and the next run learns the correction.

Delete the `tmp_*.json` scratch files when done.

---

## Notes
- **Never** commit `token.json`, `config.json`, or any PDF (all gitignored).
- The Sheet is the source of truth. Category learning comes from the `Transactions` history
  and the user's edits, plus the `Rules` tab (editable by hand).
- If auth fails, re-run `scripts/setup.py` to re-authorize.
- The `categories` list in `config.json` defines the MonthlySummary columns and is fixed at
  setup. If the user wants to change it later, edit `categories` **and** re-bootstrap the
  MonthlySummary tab (delete it and re-run setup), otherwise the header and the per-row
  category columns will drift out of alignment.
