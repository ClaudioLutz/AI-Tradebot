# Saxo Bank OAuth Setup Guide

This guide explains how to configure OAuth authentication for your trading bot to run indefinitely without manual token regeneration.

## Table of Contents

1. [Why OAuth?](#why-oauth)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Testing Your Setup](#testing-your-setup)
5. [How It Works](#how-it-works)
6. [Troubleshooting](#troubleshooting)

---

## Why OAuth?

### Manual Token vs. OAuth

**Manual Token Mode (24h expiry):**
- ✅ Quick to set up for testing
- ❌ Expires after 24 hours
- ❌ Requires daily manual regeneration
- ❌ Bot stops working when token expires

**OAuth Mode (automatic refresh):**
- ✅ Tokens refresh automatically
- ✅ Bot runs indefinitely
- ✅ No manual intervention needed
- ❌ Requires initial setup

**Access tokens are intentionally short-lived (typically 20 minutes) for security.** OAuth solves this by using a refresh token to automatically obtain new access tokens.

---

## Prerequisites

Before starting, ensure you have:

1. ✅ Saxo Developer Portal account
2. ✅ App registered on Developer Portal
3. ✅ App Key (Client ID) and App Secret
4. ✅ Python environment with required packages

---

## Step-by-Step Setup

### Step 1: Get OAuth Credentials from Saxo Developer Portal

1. **Login** to [Saxo Developer Portal](https://developer.saxobank.com)
2. **Navigate** to your application
3. **Copy** the following credentials:
   - **App Key** (also called Client ID)
   - **App Secret** (also called Client Secret)

### Step 2: Configure Redirect URI

1. In the Developer Portal, configure your app's **Redirect URI**:
   ```
   http://localhost:8765/callback
   ```
   
2. This allows the OAuth flow to redirect back to your local machine.

### Step 3: Update Your `.env` File

Open your `.env` file and configure OAuth credentials:

```bash
# Environment
SAXO_ENV=SIM
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_AUTH_BASE=https://sim.logonvalidation.net

# OAuth Configuration (for automatic token refresh)
SAXO_APP_KEY=your_app_key_here
SAXO_APP_SECRET=your_app_secret_here
SAXO_REDIRECT_URI=http://localhost:8765/callback

# Remove or comment out the manual token:
# SAXO_ACCESS_TOKEN=
```

**Important Notes:**
- For **SIM** environment: Use `https://sim.logonvalidation.net`
- For **LIVE** environment: Use `https://live.logonvalidation.net`
- Never commit actual credentials to version control

### Step 4: Run Interactive Login

Run the OAuth login script:

```powershell
python scripts/saxo_login.py
```

**What happens:**
1. Script starts a local HTTP server on port 8765
2. Opens your browser to Saxo authentication page
3. You login with your Saxo credentials
4. Saxo redirects back to `http://localhost:8765/callback`
5. Script captures the authorization code
6. Exchanges code for access and refresh tokens
7. Saves tokens to `.secrets/saxo_tokens.json`

**Expected Output:**
```
============================================================
Saxo OpenAPI OAuth Login
============================================================

This script will:
  1. Open your browser for Saxo authentication
  2. Capture the authorization code
  3. Exchange it for access and refresh tokens
  4. Save tokens to .secrets/saxo_tokens.json

Press Enter to continue...

Opening browser for Saxo authentication...

============================================================
✓ Login Successful!
============================================================

Token Information:
  Access Token Expires:  2025-12-12 23:30:00
  Refresh Token Expires: 2026-01-11 23:10:00

Tokens saved to: .secrets/saxo_tokens.json

Next steps:
  1. Remove or comment out SAXO_ACCESS_TOKEN in .env
  2. Run: python test_connection.py

Your bot will now automatically refresh tokens as needed!
============================================================
```

---

## Testing Your Setup

### 1. Verify Environment Configuration

```powershell
python verify_env.py
```

**Expected Output:**
```
==================================================
Environment Variable Verification
==================================================

Base Required Variables:
  ✓ SAXO_ENV: SIM
  ✓ SAXO_REST_BASE: https://gateway.saxobank.com/sim/openapi

Authentication Mode:
  - SAXO_ACCESS_TOKEN: not set

  Checking OAuth configuration:
    ✓ SAXO_AUTH_BASE: https://sim.logonvalidation.net
    ✓ SAXO_APP_KEY: 12345678...
    ✓ SAXO_APP_SECRET: ********************
    ✓ SAXO_REDIRECT_URI: http://localhost:8765/callback
  ✓ OAuth tokens found (.secrets/saxo_tokens.json)
  Mode: OAuth (automatic token refresh)

==================================================
✓ ALL REQUIRED VARIABLES SET

Your environment is configured correctly!
```

### 2. Test API Connection

```powershell
python test_connection.py
```

**Expected Output:**
```
============================================================
Saxo OpenAPI Connection Test (SIM)
============================================================

1. Environment Configuration
------------------------------------------------------------
✓ SAXO_REST_BASE: https://gateway.saxobank.com/sim/openapi
✓ SAXO_APP_KEY: 12345678...
✓ SAXO_APP_SECRET: ********************
✓ SAXO_REDIRECT_URI: http://localhost:8765/callback
✓ OAuth tokens found
  Mode: OAuth (automatic refresh)
✓ SAXO_ENV: SIM
✓ SIM environment detected

2. Client Initialization
------------------------------------------------------------
✓ SaxoClient created successfully
✓ Environment: SIM

3. Client Information (/port/v1/clients/me)
------------------------------------------------------------
✓ Successfully retrieved client information
  Client Key: 12345678
  Name: Test Client
  Client ID: TestClient123

4. Account Information (/port/v1/accounts/me)
------------------------------------------------------------
✓ Successfully retrieved account information
✓ Found 1 account(s)

  Account 1:
    Account Key: AbCdEfGh123=
    Account ID: TestAccount
    Currency: USD
    Type: Normal

============================================================
✓ ALL TESTS PASSED - Saxo API Connection Successful!
============================================================
```

---

## How It Works

### Token Lifecycle

```
1. Initial Login (manual, one-time)
   └─> Authorization Code
       └─> Exchange for:
           ├─> Access Token (expires in ~20 minutes)
           └─> Refresh Token (expires in ~30 days)

2. Automatic Refresh (handled by bot)
   When Access Token expires:
   └─> Use Refresh Token
       └─> Get new:
           ├─> Access Token
           └─> Refresh Token (reset expiry)
```

### File Structure

```
.secrets/
└── saxo_tokens.json      # OAuth tokens (gitignored)
    ├── access_token
    ├── refresh_token
    ├── access_token_expires_at
    └── refresh_token_expires_at

auth/
├── __init__.py
└── saxo_oauth.py         # Token management logic

scripts/
└── saxo_login.py         # Interactive login script
```

### Token Storage

Tokens are stored in `.secrets/saxo_tokens.json`:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 1200,
  "refresh_token_expires_in": 2592000,
  "access_token_expires_at": 1702420800,
  "refresh_token_expires_at": 1705012800
}
```

**Security:**
- This directory is in `.gitignore`
- Never commit tokens to version control
- Tokens are environment-specific (SIM vs LIVE)

---

## Troubleshooting

### Problem: "OAuth tokens not found"

**Solution:**
Run the login script:
```powershell
python scripts/saxo_login.py
```

---

### Problem: "Refresh token expired or invalid"

**Cause:** Refresh token expires after ~30 days of inactivity.

**Solution:**
Run login script again:
```powershell
python scripts/saxo_login.py
```

---

### Problem: Browser doesn't open

**Solution:**
Manually visit the URL shown in terminal and complete authentication.

---

### Problem: "Missing: SAXO_APP_KEY"

**Solution:**
Update your `.env` file with OAuth credentials:
```bash
SAXO_APP_KEY=your_app_key
SAXO_APP_SECRET=your_app_secret
SAXO_REDIRECT_URI=http://localhost:8765/callback
```

---

### Problem: Port 8765 already in use

**Solution:**
Change the port in your `.env`:
```bash
SAXO_REDIRECT_URI=http://localhost:9999/callback
```

And update the redirect URI in Saxo Developer Portal.

---

## Switching Between Manual and OAuth Modes

### To use Manual Token Mode:

1. Set `SAXO_ACCESS_TOKEN` in `.env`
2. Comment out or remove OAuth variables
3. The bot will use the manual token

### To use OAuth Mode:

1. Remove or comment out `SAXO_ACCESS_TOKEN` in `.env`
2. Set OAuth variables (APP_KEY, APP_SECRET, REDIRECT_URI)
3. Run `python scripts/saxo_login.py`
4. The bot will automatically refresh tokens

---

## Best Practices

1. **Always use OAuth for production/long-running bots**
2. **Use manual tokens only for quick testing**
3. **Keep `.secrets/` directory in `.gitignore`**
4. **Never commit actual credentials to version control**
5. **Re-login if refresh token expires (every ~30 days)**
6. **Monitor token expiry in logs**

---

## Next Steps

✅ OAuth is configured and working!

Now you can:
1. **Run your bot**: `python main.py`
2. **Develop with confidence**: Tokens refresh automatically
3. **Focus on strategy**: No more daily token regeneration

Your bot will now run indefinitely until you revoke access or the refresh token expires (~30 days of inactivity).

---

## Additional Resources

- [Saxo OpenAPI OAuth Documentation](https://developer.saxobank.com/openapi/learn/oauth-authorization-code-grant)
- [Token Management Best Practices](https://openapi.help.saxo/hc/en-us/articles/4417696479761)
- Project: `docs/SAXO_MIGRATION_GUIDE.md`
