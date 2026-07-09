# finance_agent

Turn your credit-card statement PDFs into a clean, categorized **Google Sheet** of your
spending — automatically, with your AI coding agent (Claude Code, Codex, or similar).

You drop your monthly statements (any bank) into a folder, tell your agent to process them,
and you get a Google Sheet with every transaction categorized and a month-by-month summary.
The agent reads the PDFs, so it isn't tied to any one bank's format.

## What you need

- [Claude Code](https://claude.com/claude-code) or another coding agent that can run shell
  commands and read PDFs.
- Python 3.9+.
- A Google account (the Sheet gets created in **your** Drive).

## Install

Tell your agent:

> Clone `https://github.com/baquerizojp-code/finance-agent`, then set it up for me.

Or do it by hand:

```bash
git clone https://github.com/baquerizojp-code/finance-agent
cd finance-agent
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python scripts/setup.py --statements-folder "/path/to/your/statements" --sheet-name "My Finance Ledger"
```

`setup.py` opens a browser once so you can authorize with your own Google account. It only
asks for permission to manage the single spreadsheet it creates (`drive.file` scope) —
nothing else in your Drive. Then it creates the Sheet and prints its link.

> **Claude Code users:** clone into `~/.claude/skills/finance-agent/` so it's available as
> the `/finance-agent` skill. Any other location works for other agents.

## Use

1. Drop your statement PDFs into the folder you chose during setup.
2. Tell your agent: **"procesa mis estados de cuenta"** (or "process my statements").
3. The agent extracts, categorizes, and writes them to your Sheet, then reports your monthly
   total and top spending categories.

Anything the agent isn't sure about lands in the `other` category — just fix the `categoria`
column in the Sheet. The monthly summary recomputes automatically and the next run learns
your correction.

## Your Google Sheet

| Tab | What's in it |
|---|---|
| `Transactions` | One row per transaction: date, month, merchant, amount, type, category, source file |
| `MonthlySummary` | One row per month: total spending + a live column per category |
| `Rules` | Merchant → category rules (edit by hand to teach it your favorites) |

## Privacy

Your statement PDFs, your `config.json`, and your Google credentials (`token.json`) stay on
**your** machine and are never committed (they're gitignored). The Sheet lives in your own
Google Drive.

## For maintainers

Hosting this for friends? See [`MAINTAINER.md`](./MAINTAINER.md) for the one-time Google
OAuth app setup.
