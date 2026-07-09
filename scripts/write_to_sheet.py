"""
write_to_sheet.py — Write categorized transactions to the ledger sheet.

Steps:
  1. Append all rows to Transactions.
  2. Append a MonthlySummary row (total + per-category SUMIFS formulas).
  3. Cache newly categorized merchants as 'auto' rules and sync rules.json → Rules tab.

Usage:
    python write_to_sheet.py <categorized_json>
    (categorized_json is the output of categorize.py: {"period", "categorized":[...]})
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from categorize import load_rules, save_rules, upsert_category_rules
from paths import RULES_PATH
from sheets_sync import (append_monthly_summary, append_transactions,
                         sync_rules_to_sheet)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Write categorized transactions to the sheet.")
    ap.add_argument("categorized_json", type=Path)
    args = ap.parse_args()

    payload = json.loads(args.categorized_json.read_text(encoding="utf-8"))
    period = payload["period"]
    rows = payload["categorized"]

    n = append_transactions(rows, period)
    append_monthly_summary(period)

    # Cache categories learned this run (web-guesses) so future runs skip the search.
    rules = load_rules(RULES_PATH)
    added = upsert_category_rules(rules, rows)
    if added:
        save_rules(rules, RULES_PATH)
    sync_rules_to_sheet([
        {"merchant_pattern": r.merchant_pattern, "category": r.category, "notes": r.notes,
         "source": r.source, "created_at": r.created_at, "last_used": r.last_used}
        for r in rules
    ])

    print(f"✓ {n} transacciones escritas para {period}. Reglas nuevas cacheadas: {added}.")


if __name__ == "__main__":
    main()
