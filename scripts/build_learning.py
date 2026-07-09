"""
build_learning.py — Per-merchant CATEGORY index from the Transactions tab.

The Transactions tab is the training corpus: every row carries a merchant plus the
category the user either accepted or corrected in the sheet. For each merchant this
records how many times it appears and its most-recent category (by fecha). categorize.py
consumes the index to auto-fill categories without asking or re-searching the web.

Usage:
    python build_learning.py [--output <json>] [--history <json>]
      --history  JSON list of Transactions rows (offline tests). Reads the Sheet if omitted.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Categories that carry no learning signal (payments, refunds, or "not yet classified").
_NON_SIGNAL = {"", "other", "pago", "credito", "payment", "refund"}


def normalize_merchant(name: str) -> str:
    """Uppercase + collapse whitespace. Conservative on purpose: vendor-string variants
    are merged by wildcard rules, not here, to avoid false merges."""
    return re.sub(r"\s+", " ", str(name).strip()).upper()


def build_index(rows: list[dict]) -> dict[str, dict]:
    """{normalized_merchant: {count, latest_category, latest_date}} from Transactions."""
    by_merchant: dict[str, list[dict]] = {}
    for i, row in enumerate(rows):
        category = str(row.get("categoria", "")).strip()
        if category.lower() in _NON_SIGNAL:
            continue
        merchant = normalize_merchant(row.get("comercio", ""))
        if not merchant:
            continue
        by_merchant.setdefault(merchant, []).append({
            "date": str(row.get("fecha", "")).strip(),
            "category": category,
            "order": i,
        })

    index: dict[str, dict] = {}
    for merchant, entries in by_merchant.items():
        entries.sort(key=lambda e: (e["date"], e["order"]))
        latest = entries[-1]
        index[merchant] = {
            "count": len(entries),
            "latest_category": latest["category"],
            "latest_date": latest["date"],
        }
    return index


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build merchant category index from history.")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--history", type=Path, default=None)
    args = ap.parse_args()

    if args.history:
        rows = json.loads(args.history.read_text(encoding="utf-8"))
    else:
        from sheets_sync import load_transactions_history
        rows = load_transactions_history()

    index = build_index(rows)
    print(f"Merchants in corpus: {len(index)}")

    if args.output:
        args.output.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Learning index saved to: {args.output}")


if __name__ == "__main__":
    main()
