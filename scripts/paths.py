"""
paths.py — Repo-relative paths and config I/O.

Every other script derives its file locations from here, so the repo is fully
portable: clone it anywhere and the scripts still find config.json, rules.json,
credentials, and runtime state next to them. No absolute or user-specific paths.
"""

from __future__ import annotations

import json
from pathlib import Path

# scripts/ lives one level under the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = REPO_ROOT / "config.json"
RULES_PATH = REPO_ROOT / "rules.json"
PROCESSED_PATH = REPO_ROOT / "processed.json"

# Google OAuth: the shared desktop-app client (committed) and the per-user token
# cache (gitignored — created on first auth, holds the friend's own credentials).
OAUTH_CLIENT_PATH = REPO_ROOT / "oauth_client.json"
TOKEN_PATH = REPO_ROOT / "token.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def config_exists() -> bool:
    return CONFIG_PATH.exists()
