"""
reconcile.py — Sanity-check the agent's extraction against the statement's own total.

Because parsing is done by the agent (no fixed bank format to lean on), this is the
one guard against silently dropped or duplicated rows: the sum of extracted charges
must match the statement's declared period-charges total, within a tolerance.

The agent must put the statement's own "total of new charges/consumos for the period"
(NOT the new balance, which includes prior balance) into `declared_total`.

Input: the extraction JSON (period, declared_total, transactions[{amount, txn_type}]).
Exit code 0 if it reconciles, 1 otherwise (so the caller notices a mismatch).

Usage:
    python reconcile.py <extraction_json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paths import load_config
from sheets_sync import CHARGE_TIPO


def reconcile(extraction: dict, tolerance: float) -> dict:
    charges = sum(
        float(t["amount"]) for t in extraction.get("transactions", [])
        if str(t.get("txn_type", "cargo")).lower() == CHARGE_TIPO
    )
    declared = extraction.get("declared_total")

    if declared is None:
        return {"ok": False, "sum_charges": round(charges, 2), "declared_total": None,
                "diff": None, "tolerance": tolerance,
                "message": "Falta declared_total en la extracción — no se puede reconciliar. "
                           "Extrae el total de consumos del periodo del estado y reintenta."}

    diff = round(charges - float(declared), 2)
    ok = abs(diff) <= tolerance
    msg = (f"OK: consumos extraídos ${charges:.2f} ≈ total declarado ${float(declared):.2f} "
           f"(dif ${diff:+.2f})") if ok else (
           f"MISMATCH: consumos extraídos ${charges:.2f} vs total declarado "
           f"${float(declared):.2f} (dif ${diff:+.2f}, tolerancia ${tolerance:.2f}). "
           "Revisa la extracción antes de escribir al Sheet.")
    return {"ok": ok, "sum_charges": round(charges, 2), "declared_total": round(float(declared), 2),
            "diff": diff, "tolerance": tolerance, "message": msg}


def main() -> None:
    ap = argparse.ArgumentParser(description="Reconcile extraction vs declared total.")
    ap.add_argument("extraction_json", type=Path)
    args = ap.parse_args()

    tolerance = load_config().get("thresholds", {}).get("reconcile_tolerance", 0.50)
    extraction = json.loads(args.extraction_json.read_text(encoding="utf-8"))
    result = reconcile(extraction, tolerance)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
