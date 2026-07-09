"""
find_pending.py — List PDF statements in the configured folder not yet processed.

Dedup is by MD5 against processed.json, so re-runs never double-count a statement.
Period detection is NOT done here (the agent reads each PDF and determines the period
when it extracts transactions), which keeps this bank-agnostic.

Usage:
    python find_pending.py
    # Prints a JSON list of {"path", "filename", "hash"} for each unprocessed PDF.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from paths import PROCESSED_PATH, load_config


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main() -> None:
    config = load_config()
    folder = Path(config["paths"]["statements_folder"]).expanduser()
    if not folder.is_dir():
        print(f"WARNING: statements folder not found: {folder}", file=sys.stderr)
        print("[]")
        return

    processed = json.loads(PROCESSED_PATH.read_text())["processed"] if PROCESSED_PATH.exists() else []
    processed_hashes = {e["hash"] for e in processed}

    pending = []
    for pdf in sorted(folder.glob("*.pdf")):
        h = _md5(pdf)
        if h in processed_hashes:
            continue
        pending.append({"path": str(pdf), "filename": pdf.name, "hash": h})

    print(json.dumps(pending, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
