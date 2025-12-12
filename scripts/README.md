# Scripts Directory

Utility scripts for the AI Trader bot.

## Available Scripts

### `saxo_login.py`

**Purpose:** Perform one-time OAuth login to obtain access and refresh tokens.

**Usage:**
```powershell
python scripts/saxo_login.py
```

**What it does:**
1. Opens browser for Saxo authentication
2. Captures authorization code via local HTTP server
3. Exchanges code for access and refresh tokens
4. Saves tokens to `.secrets/saxo_tokens.json`

**Prerequisites:**
- `.env` file configured with OAuth credentials:
  - `SAXO_APP_KEY`
  - `SAXO_APP_SECRET`
  - `SAXO_REDIRECT_URI`
  - `SAXO_AUTH_BASE`

**When to run:**
- First time setting up OAuth
- When refresh token expires (~30 days)
- After revoking and re-granting app access

**Output:**
- Creates `.secrets/saxo_tokens.json` with OAuth tokens
- Displays token expiry information

See `docs/OAUTH_SETUP_GUIDE.md` for detailed setup instructions.
