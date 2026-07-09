"""
categorize.py — Assign a category to each extracted transaction.

Input is the agent's extraction JSON (see AGENTS.md):
    {"period": "YYYY-MM", "declared_total": 0.0,
     "transactions": [{"date","merchant","amount","txn_type"}, ...]}

Category is decided aggressively (merchant-stable):
    learned history (any count, most recent) → rule match (rules.json, incl. wildcards)
    → "other" (flagged so the agent web-guesses it, then caches the result).
Payments/credits pass through as their tipo with no category lookup.

Usage:
    python categorize.py <extraction_json> [--rules rules.json] [--learned <json>]
        [--source-file NAME] [--output <json>]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from paths import RULES_PATH, load_config

logger = logging.getLogger(__name__)

# tipo values that are not spending and never get a merchant category.
PASSTHROUGH_TIPOS = {"pago", "credito"}


@dataclass
class Rule:
    """A category rule. `source` is 'manual' (hand-authored / edited in the Rules tab)
    or 'auto' (cached by the agent from a web-guess)."""
    merchant_pattern: str
    category: str
    notes: str = ""
    source: str = "manual"
    created_at: str = ""
    last_used: Optional[str] = None
    _regex: Optional[re.Pattern] = field(default=None, repr=False, compare=False)

    def compile(self) -> None:
        escaped = re.escape(self.merchant_pattern).replace(r"\*", ".*").replace(r"\?", ".")
        self._regex = re.compile(f"^{escaped}$", re.IGNORECASE)

    def matches(self, merchant: str) -> bool:
        if self._regex is None:
            self.compile()
        return bool(self._regex.match(merchant.strip()))


@dataclass
class CategorizedTransaction:
    date: str
    merchant: str
    amount: float
    txn_type: str
    source_file: str
    category: str
    confidence: str            # learned | rule | fuzzy | auto | none
    matched_pattern: Optional[str]
    needs_review: bool
    review_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Rules I/O
# ---------------------------------------------------------------------------

def load_rules(path: Path) -> list[Rule]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = []
    for r in data.get("rules", []):
        rule = Rule(
            merchant_pattern=r["merchant_pattern"],
            category=r.get("category", "other"),
            notes=r.get("notes", ""),
            source=r.get("source", "manual"),
            created_at=r.get("created_at", ""),
            last_used=r.get("last_used"),
        )
        rule.compile()
        rules.append(rule)
    logger.info("Loaded %d rules from %s", len(rules), path.name)
    return rules


def save_rules(rules: list[Rule], path: Path) -> None:
    data = {"rules": [
        {"merchant_pattern": r.merchant_pattern, "category": r.category, "notes": r.notes,
         "source": r.source, "created_at": r.created_at, "last_used": r.last_used}
        for r in rules
    ]}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved %d rules to %s", len(rules), path.name)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _fuzzy_distance(a: str, b: str) -> int:
    from rapidfuzz.distance import Levenshtein
    return Levenshtein.distance(a.lower(), b.lower())


def match_transaction(merchant: str, rules: list[Rule], fuzzy_max_dist: int = 3) -> tuple[Optional[Rule], str]:
    """Best matching rule → (rule, confidence in {rule, fuzzy, none})."""
    merchant_clean = merchant.strip()
    for rule in rules:
        if rule.matches(merchant_clean):
            return rule, "rule"

    best_rule: Optional[Rule] = None
    best_dist = fuzzy_max_dist + 1
    for rule in rules:
        base = rule.merchant_pattern.rstrip("*").rstrip("?").strip()
        if not base:
            continue
        dist = _fuzzy_distance(merchant_clean, base)
        if dist <= fuzzy_max_dist and dist < best_dist:
            best_dist, best_rule = dist, rule
    if best_rule is not None:
        return best_rule, "fuzzy"
    return None, "none"


def add_rule(rules: list[Rule], merchant_pattern: str, category: str,
             notes: str = "", source: str = "auto") -> Rule:
    rule = Rule(merchant_pattern=merchant_pattern, category=category, notes=notes,
                source=source, created_at=date.today().isoformat())
    rule.compile()
    rules.append(rule)
    logger.info("Added %s rule: '%s' → %s", source, merchant_pattern, category)
    return rule


def upsert_category_rules(rules: list[Rule], categorized: list[dict]) -> int:
    """Cache categories the agent set this run (web-guesses) so future runs skip the
    search. Adds an 'auto' rule for each known-category merchant not already covered.
    Manual rules/wildcards are never touched. Returns count added."""
    from build_learning import normalize_merchant
    added, seen = 0, set()
    for t in categorized:
        category = t.get("category", "other")
        merchant = normalize_merchant(t.get("merchant", ""))
        if not merchant or category in ("other", "pago", "credito") or merchant in seen:
            continue
        seen.add(merchant)
        if any(r.matches(merchant) for r in rules):
            continue
        add_rule(rules, merchant, category, notes="cached by agent", source="auto")
        added += 1
    return added


# ---------------------------------------------------------------------------
# Categorization pass
# ---------------------------------------------------------------------------

def categorize_transactions(extraction: dict, rules: list[Rule],
                            learned_index: Optional[dict] = None,
                            fuzzy_max_dist: int = 3,
                            source_file: str = "") -> list[CategorizedTransaction]:
    from build_learning import normalize_merchant
    learned_index = learned_index or {}
    out: list[CategorizedTransaction] = []

    for txn in extraction["transactions"]:
        merchant = txn["merchant"]
        txn_type = str(txn.get("txn_type", "cargo")).lower()
        src = txn.get("source_file") or source_file

        if txn_type in PASSTHROUGH_TIPOS:
            out.append(CategorizedTransaction(
                date=txn["date"], merchant=merchant, amount=txn["amount"], txn_type=txn_type,
                source_file=src, category=txn_type, confidence="auto",
                matched_pattern=None, needs_review=False, review_reason=""))
            continue

        learned = learned_index.get(normalize_merchant(merchant))
        rule, rule_conf = match_transaction(merchant, rules, fuzzy_max_dist)

        if learned is not None:
            category, confidence, matched = learned["latest_category"], "learned", f"learned:{learned['count']}"
        elif rule is not None:
            category, confidence, matched = rule.category, rule_conf, rule.merchant_pattern
        else:
            category, confidence, matched = "other", "none", None

        needs_review = category == "other"
        out.append(CategorizedTransaction(
            date=txn["date"], merchant=merchant, amount=txn["amount"], txn_type=txn_type,
            source_file=src, category=category, confidence=confidence, matched_pattern=matched,
            needs_review=needs_review,
            review_reason="Comercio nuevo — categoría a inferir" if needs_review else ""))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Categorize extracted transactions.")
    ap.add_argument("extraction_json", type=Path)
    ap.add_argument("--rules", type=Path, default=RULES_PATH)
    ap.add_argument("--learned", type=Path, default=None)
    ap.add_argument("--source-file", default="")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    config = load_config()
    fuzzy = config.get("thresholds", {}).get("fuzzy_match_max_distance", 3)

    extraction = json.loads(args.extraction_json.read_text(encoding="utf-8"))
    rules = load_rules(args.rules)
    learned = json.loads(args.learned.read_text(encoding="utf-8")) if args.learned else {}
    result = categorize_transactions(extraction, rules, learned, fuzzy_max_dist=fuzzy,
                                     source_file=args.source_file)

    to_guess = [t for t in result if t.needs_review]
    print(f"\nPeriodo: {extraction.get('period', '?')}")
    print(f"Transacciones: {len(result)}  |  categoría 'other' a inferir: {len(to_guess)}")
    for t in to_guess:
        print(f"  {t.date} | ${t.amount:8.2f} | {t.merchant[:40]}")

    payload = {"period": extraction.get("period", ""),
               "categorized": [t.to_dict() for t in result]}
    if args.output:
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON guardado en: {args.output}")


if __name__ == "__main__":
    main()
