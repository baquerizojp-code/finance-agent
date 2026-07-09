"""
mark_processed.py — Record a PDF as processed (MD5 + period) in processed.json.

Usage:
    python mark_processed.py <pdf_path> <period>
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from paths import PROCESSED_PATH


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python mark_processed.py <pdf_path> <period>")
        sys.exit(1)

    pdf_path, period = Path(sys.argv[1]), sys.argv[2]
    data = json.loads(PROCESSED_PATH.read_text()) if PROCESSED_PATH.exists() else {"processed": []}

    h = hashlib.md5(pdf_path.read_bytes()).hexdigest()
    if h in {e["hash"] for e in data["processed"]}:
        print(f"Already marked as processed: {pdf_path.name}")
        return

    data["processed"].append({
        "hash": h, "filename": pdf_path.name, "period": period,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    PROCESSED_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Marked {pdf_path.name} ({period}) as processed.")


if __name__ == "__main__":
    main()
