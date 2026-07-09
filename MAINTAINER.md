# Maintainer setup (one time)

You host **one** Google OAuth app for everyone who uses this repo. Friends never touch the
Google Cloud Console — they just authorize with their own account. This document is for you.

## Why a shared app

The tool authorizes each user with their own Google account and only requests the
non-sensitive `drive.file` scope (it can only manage the one spreadsheet it creates). A
single shared "Desktop app" OAuth client is enough: Google's docs state a desktop client
secret is **not** treated as a secret, so it's fine to commit `oauth_client.json` to the repo.

## Steps

1. **GCP project** — create one (or reuse) at <https://console.cloud.google.com>.
2. **Enable APIs** — enable **Google Sheets API** and **Google Drive API** for the project.
3. **OAuth consent screen**
   - User type: **External**.
   - Add scope: `https://www.googleapis.com/auth/drive.file` (non-sensitive).
   - **Publish the app to "In production."** This is important: apps left in "Testing"
     hand out refresh tokens that die after 7 days, which would break a monthly tool. In
     production, tokens don't expire. With only the non-sensitive `drive.file` scope you do
     **not** need Google's restricted-scope security review.
4. **Create credentials** — Credentials → Create credentials → OAuth client ID →
   application type **Desktop app**. Download the JSON.
5. **Add it to the repo** — save the downloaded file as `oauth_client.json` at the repo root
   (same shape as `oauth_client.example.json`). This file **is** committed.
6. **Push** the repo to GitHub. Recommended: your personal account, **public**, so friends
   can clone it freely. (It's a personal tool, not company IP.)

## Quota note

All users' Sheets/Drive API calls count against your project's quota. For a handful of
friends running this monthly, the default quotas are far more than enough.

## What is and isn't in the repo

- **Committed:** `oauth_client.json` (shared desktop client), all scripts, docs,
  `config.example.json`, the seed `rules.json`.
- **Never committed (gitignored):** each user's `token.json` (their credentials),
  `config.json` (their sheet id + folder), `processed.json`, and any `*.pdf`.

## If you ever need to rotate the client

Delete the OAuth client in the console, create a new Desktop client, replace
`oauth_client.json`, and push. Existing users will just re-authorize on their next run.
