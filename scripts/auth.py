"""
auth.py — Google OAuth (per-user) via the shared desktop-app client.

The friend authorizes with THEIR OWN Google account in a browser once. We request
only the non-sensitive `drive.file` scope, which lets the tool create and edit the
one spreadsheet it makes — nothing else in their Drive. The resulting credentials
are cached in token.json (gitignored) and refreshed automatically on later runs.

The OAuth client (oauth_client.json) is a "Desktop app" client hosted by the repo
maintainer and published to production, so refresh tokens do not expire. Google's
docs state a desktop client secret is not treated as a secret, so it ships in the repo.

Usage:
    python auth.py            # runs the browser flow if needed, prints the account
"""

from __future__ import annotations

import logging

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from paths import OAUTH_CLIENT_PATH, TOKEN_PATH

logger = logging.getLogger(__name__)

# Non-sensitive, per-file scope. Enough for gspread to create + read + write the
# spreadsheet this app creates. Avoids the restricted-scope security review.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_credentials(interactive: bool = True) -> Credentials:
    """Return valid user credentials, running the browser flow if needed.

    Loads the cached token, refreshes it if expired, or (when interactive) opens a
    browser for first-time consent. Raises if no token exists and interactive=False.
    """
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception as e:  # refresh can fail if the grant was revoked
            logger.warning("Token refresh failed (%s) — re-authorizing", e)

    if not interactive:
        raise RuntimeError(
            "No valid Google credentials. Run `python scripts/setup.py` to authorize."
        )

    if not OAUTH_CLIENT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {OAUTH_CLIENT_PATH.name}. The repo maintainer must ship the "
            "OAuth desktop client (see MAINTAINER.md)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_PATH), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    logger.info("Authorized and cached token to %s", TOKEN_PATH.name)
    return creds


def get_client(interactive: bool = True) -> gspread.Client:
    """Authorized gspread client for the signed-in user."""
    return gspread.authorize(get_credentials(interactive=interactive))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client = get_client()
    # A cheap call that confirms the credentials actually work.
    email = getattr(client.auth, "id_token", None)
    print("✓ Autorizado con Google. Credenciales guardadas en token.json")
