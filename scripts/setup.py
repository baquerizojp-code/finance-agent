"""
setup.py — One-time onboarding for a new user.

Does three things:
  1. Writes config.json (from config.example.json) with the user's statements folder.
  2. Runs the Google OAuth browser flow (authorizes with the user's own account).
  3. Creates the ledger spreadsheet in the user's Drive and saves its id to config.json.

Usage:
    python setup.py --statements-folder "/path/to/pdfs" [--sheet-name "My Ledger"]

Re-running is safe: it reuses an existing sheet id and only re-authorizes if needed.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from auth import get_credentials
from paths import CONFIG_PATH, REPO_ROOT, load_config, save_config
from sheets_sync import bootstrap_sheet

EXAMPLE_CONFIG = REPO_ROOT / "config.example.json"


def _ensure_config(statements_folder: str | None, sheet_name: str | None) -> dict:
    if CONFIG_PATH.exists():
        config = load_config()
    else:
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))

    if statements_folder:
        config.setdefault("paths", {})["statements_folder"] = statements_folder
    if sheet_name:
        config.setdefault("sheet", {})["name"] = sheet_name

    save_config(config)
    return config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Set up finance_agent for a new user.")
    ap.add_argument("--statements-folder", default=None,
                    help="Folder where you drop your credit-card statement PDFs.")
    ap.add_argument("--sheet-name", default=None, help="Name for your Google Sheet.")
    args = ap.parse_args()

    config = _ensure_config(args.statements_folder, args.sheet_name)

    folder = config.get("paths", {}).get("statements_folder")
    if not folder:
        raise SystemExit("Falta la carpeta de estados. Corre con --statements-folder \"...\".")
    Path(folder).expanduser().mkdir(parents=True, exist_ok=True)

    print("→ Autorizando con Google (se abrirá el navegador)...")
    get_credentials(interactive=True)

    print("→ Creando el Google Sheet...")
    sheet_id = bootstrap_sheet()

    print("\n✓ Setup completo.")
    print(f"  Sheet:     https://docs.google.com/spreadsheets/d/{sheet_id}")
    print(f"  PDFs en:   {folder}")
    print("  Deja tus estados de cuenta en esa carpeta y pídele al agente que los procese.")


if __name__ == "__main__":
    main()
