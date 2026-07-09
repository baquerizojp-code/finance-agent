"""
sheets_sync.py — Read/write the personal-ledger Google Sheet via gspread (OAuth).

Solo-ledger schema (one person, no split):
  Transactions:   fecha | mes | comercio | monto | tipo | categoria | archivo
  MonthlySummary: mes | total_gastos | <one SUMIFS column per category> | procesado_en
  Rules:          merchant_pattern | category | notes | source | created_at | last_used

MonthlySummary financial columns are live SUMIFS formulas referencing Transactions, so
correcting a `categoria` in the sheet re-computes the monthly breakdown automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import gspread

from auth import get_client
from paths import load_config, save_config

logger = logging.getLogger(__name__)

# Tab names
TAB_TRANSACTIONS = "Transactions"
TAB_SUMMARY = "MonthlySummary"
TAB_RULES = "Rules"

TRANSACTIONS_HEADERS = ["fecha", "mes", "comercio", "monto", "tipo", "categoria", "archivo"]
# Column letters: A=fecha B=mes C=comercio D=monto E=tipo F=categoria G=archivo
RULES_HEADERS = ["merchant_pattern", "category", "notes", "source", "created_at", "last_used"]

# tipo vocabulary the agent emits when it parses a statement:
#   "cargo"   — a purchase / charge (counts as spending)
#   "pago"    — a payment toward the card (not spending)
#   "credito" — a refund / credit (not spending)
CHARGE_TIPO = "cargo"


def _summary_headers(config: dict) -> list[str]:
    """MonthlySummary header = mes, total_gastos, <categories...>, procesado_en."""
    return ["mes", "total_gastos", *config.get("categories", []), "procesado_en"]


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _setup_tab(ss: gspread.Spreadsheet, tab_name: str, headers: list[str]) -> gspread.Worksheet:
    """Get or create a tab and write frozen headers if empty."""
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=max(len(headers), 10))
        logger.info("Created tab '%s'", tab_name)

    if not ws.get_all_values():
        ws.append_row(headers, value_input_option="RAW")
        ss.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        }]})
        logger.info("Headers written to '%s'", tab_name)
    return ws


def bootstrap_sheet() -> str:
    """Create the ledger spreadsheet in the signed-in user's own Drive.

    Because we authorize with the user's own account (drive.file scope), the file is
    owned by them and no sharing/quota workaround is needed. Returns the sheet ID and
    persists it to config.json. Idempotent: reuses an existing valid sheet id.
    """
    client = get_client()
    config = load_config()

    existing_id = config.get("sheet", {}).get("id")
    if existing_id:
        try:
            ss = client.open_by_key(existing_id)
            logger.info("Sheet already exists: %s (%s)", ss.title, existing_id)
            return existing_id
        except gspread.SpreadsheetNotFound:
            logger.warning("Stored sheet id %s not found — creating a new one", existing_id)

    sheet_name = config.get("sheet", {}).get("name", "Finance Ledger")
    ss = client.create(sheet_name)
    logger.info("Created spreadsheet '%s' (id=%s)", sheet_name, ss.id)

    _setup_tab(ss, TAB_TRANSACTIONS, TRANSACTIONS_HEADERS)
    _setup_tab(ss, TAB_SUMMARY, _summary_headers(config))
    _setup_tab(ss, TAB_RULES, RULES_HEADERS)

    try:
        ss.del_worksheet(ss.worksheet("Sheet1"))
    except gspread.WorksheetNotFound:
        pass

    config.setdefault("sheet", {})["id"] = ss.id
    save_config(config)
    logger.info("Sheet id saved to config.json: %s", ss.id)
    return ss.id


# ---------------------------------------------------------------------------
# Open + read
# ---------------------------------------------------------------------------

def get_sheet(client: Optional[gspread.Client] = None) -> gspread.Spreadsheet:
    config = load_config()
    sheet_id = config.get("sheet", {}).get("id")
    if not sheet_id:
        raise ValueError("No sheet id in config.json — run `python scripts/setup.py` first.")
    return (client or get_client()).open_by_key(sheet_id)


def load_transactions_history(client: Optional[gspread.Client] = None) -> list[dict]:
    """Every existing Transactions row as a dict — the category-learning corpus."""
    ws = get_sheet(client).worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()
    logger.info("Loaded %d historical transactions", len(records))
    return records


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def append_transactions(rows: list[dict], period: str, client: Optional[gspread.Client] = None) -> int:
    """Append categorized transactions to the Transactions tab. Plain values (no
    per-row formulas): the live formulas live in MonthlySummary."""
    ws = get_sheet(client).worksheet(TAB_TRANSACTIONS)
    out = [
        [t["date"], period, t["merchant"], t["amount"], t.get("txn_type", CHARGE_TIPO),
         t["category"], t.get("source_file", "")]
        for t in rows
    ]
    if out:
        ws.append_rows(out, value_input_option="USER_ENTERED")
        logger.info("Appended %d transaction rows for %s", len(out), period)
    return len(out)


def append_monthly_summary(period: str, total_statement: Optional[float] = None,
                           client: Optional[gspread.Client] = None) -> None:
    """Append one MonthlySummary row. total_gastos and each category column are SUMIFS
    formulas over Transactions, so they self-update when categories are corrected."""
    config = load_config()
    categories = config.get("categories", [])
    ss = get_sheet(client)
    ws = ss.worksheet(TAB_SUMMARY)

    n = len(ws.get_all_values()) + 1  # row index of the new row
    total_formula = (
        f'=SUMIFS(Transactions!D:D,Transactions!B:B,A{n},'
        f'Transactions!E:E,"{CHARGE_TIPO}")'
    )
    cat_formulas = [
        f'=SUMIFS(Transactions!D:D,Transactions!B:B,A{n},Transactions!F:F,"{cat}")'
        for cat in categories
    ]
    row = [period, total_formula, *cat_formulas,
           datetime.now(timezone.utc).isoformat(timespec="seconds")]
    ws.append_row(row, value_input_option="USER_ENTERED")
    logger.info("Appended monthly summary for %s", period)


def sync_rules_to_sheet(rules: list[dict], client: Optional[gspread.Client] = None) -> None:
    """Overwrite the Rules tab from rules.json (keeps the header)."""
    ws = get_sheet(client).worksheet(TAB_RULES)
    ws.clear()
    ws.append_row(RULES_HEADERS, value_input_option="RAW")
    rows = [[r["merchant_pattern"], r["category"], r.get("notes", ""),
             r.get("source", "manual"), r.get("created_at", ""), r.get("last_used", "") or ""]
            for r in rules]
    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info("Synced %d rules to sheet", len(rows))


def sync_rules_from_sheet(client: Optional[gspread.Client] = None) -> list[dict]:
    """Read the Rules tab (to pick up manual edits made in the sheet)."""
    ws = get_sheet(client).worksheet(TAB_RULES)
    records = ws.get_all_records()
    logger.info("Read %d rules from sheet", len(records))
    return records
