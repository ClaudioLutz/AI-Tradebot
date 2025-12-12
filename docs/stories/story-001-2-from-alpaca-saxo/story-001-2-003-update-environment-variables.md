# Story 001-2-003: Update Environment Variables Configuration

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the environment variable configuration to use Saxo Bank credentials instead of Alpaca so that the application can authenticate with the correct API.

## Description
Replace Alpaca-specific environment variables (`APCA_*`) with Saxo Bank environment variables (`SAXO_*`) in both `.env.example` template and the actual `.env` file. This maintains the secure credential management pattern established in Story 001-004.

## Prerequisites
- Story 001-2-001 completed (have 24h SIM token)
- Story 001-2-002 completed (dependencies updated)
- `.env.example` exists in project root

## Acceptance Criteria
- [ ] `.env.example` updated with Saxo variables
- [ ] `.env` file updated with actual Saxo credentials
- [ ] All Alpaca variables removed
- [ ] Proper comments and documentation included
- [ ] Token security maintained

## Technical Details

### Current Environment Variables (Alpaca)
```env
APCA_API_KEY_ID=your_alpaca_key_id
APCA_API_SECRET_KEY=your_alpaca_secret_key
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

### New Environment Variables (Saxo)
```env
# Saxo OpenAPI (SIM)
SAXO_ENV=SIM
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_AUTH_BASE=https://sim.logonvalidation.net
SAXO_ACCESS_TOKEN=your_24h_token_here

# Optional (for future OAuth implementation)
SAXO_APP_KEY=
SAXO_APP_SECRET=
SAXO_REDIRECT_URI=http://localhost/mytestapp
```

### Variable Explanations
- **SAXO_ENV:** Environment identifier (SIM or LIVE)
- **SAXO_REST_BASE:** Base URL for REST API calls
- **SAXO_AUTH_BASE:** Base URL for authentication
- **SAXO_ACCESS_TOKEN:** 24-hour bearer token from Developer Portal
- **SAXO_APP_KEY:** (Optional) OAuth app key for future use
- **SAXO_APP_SECRET:** (Optional) OAuth app secret for future use
- **SAXO_REDIRECT_URI:** (Optional) OAuth redirect URI for future use

## Implementation Steps

### 1. Update .env.example Template

Replace content with:

```env
# Saxo OpenAPI Configuration
# See docs/SAXO_SETUP_GUIDE.md for setup instructions

# Environment (SIM or LIVE)
SAXO_ENV=SIM

# API Base URLs
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_AUTH_BASE=https://sim.logonvalidation.net

# Authentication Token (24-hour token from Developer Portal)
# IMPORTANT: Regenerate daily from https://developer.saxobank.com
# Token expires after 24 hours
SAXO_ACCESS_TOKEN=your_24h_sim_token_here

# Optional: OAuth Credentials (for future production use)
# Leave empty for SIM development
SAXO_APP_KEY=
SAXO_APP_SECRET=
SAXO_REDIRECT_URI=http://localhost/mytestapp

# Security Notes:
# - Never commit actual tokens to version control
# - Token is SIM-only (cannot access live trading)
# - Regenerate token daily from Developer Portal
# - Keep token secure (treat as a password)
```

### 2. Update .env File

Create/update your actual `.env` file with the real token from Story 001-2-001:

```env
SAXO_ENV=SIM
SAXO_REST_BASE=https://gateway.saxobank.com/sim/openapi
SAXO_AUTH_BASE=https://sim.logonvalidation.net
SAXO_ACCESS_TOKEN=[paste_your_actual_token_here]
SAXO_APP_KEY=
SAXO_APP_SECRET=
SAXO_REDIRECT_URI=http://localhost/mytestapp
```

### 3. Verify .gitignore

Ensure `.env` is still excluded from git:

```gitignore
.env
```

This should already be configured from Story 001-004.

## Files to Modify
- `.env.example` - Update template with Saxo variables
- `.env` - Update with actual Saxo credentials

## Files to Verify (no changes needed)
- `.gitignore` - Should already exclude `.env`

## Verification Steps
- [ ] `.env.example` contains all Saxo variables
- [ ] `.env.example` has helpful comments
- [ ] `.env` file contains actual token
- [ ] `.env` is still in `.gitignore`
- [ ] No Alpaca variables remain in either file
- [ ] Token is properly masked in examples

## Testing
Run these commands to verify:

```bash
# Check .env.example exists and has Saxo variables
grep "SAXO_ACCESS_TOKEN" .env.example

# Check .env exists and has actual token (should show actual value)
grep "SAXO_ACCESS_TOKEN" .env

# Verify .env is ignored by git (should return .env)
git check-ignore .env

# Ensure no APCA variables remain
grep -i "APCA" .env.example .env 2>/dev/null
```

Expected:
- First two commands succeed
- Third command returns `.env`
- Fourth command returns nothing (no APCA variables)

## Documentation to Update
- Consider creating `docs/SAXO_SETUP_GUIDE.md` (future story)

## Security Checklist
- [ ] `.env` file not committed to git
- [ ] Token treated as sensitive credential
- [ ] Clear warnings about token expiration
- [ ] Examples use placeholder text, not real tokens
- [ ] Comments explain security considerations

## Time Estimate
**15 minutes** (update files + verify security)

## Dependencies
- Story 001-2-001 completed (have token to add)
- Story 001-2-002 completed (environment ready)

## Blocks
- Story 001-2-004 (verification script needs these variables)
- Story 001-2-005 (Saxo client reads these variables)
- Story 001-2-006 (connection test reads these variables)

## Notes
- Keep OAuth variables empty for now (future use)
- Token must be regenerated every 24 hours during development
- SIM URLs are hardcoded (won't change)
- Future epic will handle OAuth implementation

## Token Refresh Reminder
⏰ **Daily Task:**
1. Go to https://developer.saxobank.com
2. Generate new 24h SIM token
3. Update `SAXO_ACCESS_TOKEN` in `.env`
4. Note new expiration time

## Migration Checklist
- [ ] Backup current `.env` file (if needed)
- [ ] Remove all APCA variables
- [ ] Add all SAXO variables
- [ ] Paste actual 24h token
- [ ] Verify security (gitignore)
- [ ] Test loading with `python-dotenv`

## Simple Test
```python
from dotenv import load_dotenv
import os

load_dotenv()
print(f"SAXO_ENV: {os.getenv('SAXO_ENV')}")
print(f"SAXO_REST_BASE: {os.getenv('SAXO_REST_BASE')}")
print(f"Token present: {'Yes' if os.getenv('SAXO_ACCESS_TOKEN') else 'No'}")
```

Expected output:
```
SAXO_ENV: SIM
SAXO_REST_BASE: https://gateway.saxobank.com/sim/openapi
Token present: Yes
```

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 3)
- [Saxo Bank Environments](https://developer.saxobank.com/openapi/learn/environments)

## Success Criteria
✅ Story is complete when:
1. `.env.example` has Saxo template
2. `.env` has actual token
3. No Alpaca variables remain
4. Security verified (gitignore working)
5. Variables load correctly with python-dotenv
