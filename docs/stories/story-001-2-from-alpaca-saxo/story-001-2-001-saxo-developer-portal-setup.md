# Story 001-2-001: Saxo Developer Portal Setup & 24h Token Acquisition

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to set up access to the Saxo Bank Developer Portal and obtain a 24-hour SIM token so that I can authenticate API requests during development.

## Description
Register/access the Saxo Bank Developer Portal and generate a 24-hour access token for the SIM (simulation/paper) environment. This token will be used for all API authentication during development and testing.

## Prerequisites
- Active internet connection
- Web browser
- Email account for registration

## Acceptance Criteria
- [ ] Successfully access Saxo Bank Developer Portal
- [ ] Account created/verified on the portal
- [ ] 24-hour SIM access token generated
- [ ] Token expiration time noted
- [ ] Token ready to be added to `.env` file

## Technical Details

### Saxo Developer Portal
- **URL:** https://developer.saxobank.com
- **Environment:** SIM (Simulation)
- **Token Type:** 24-hour access token (SIM-only)

### Token Characteristics
- **Lifetime:** 24 hours
- **Environment:** SIM only (cannot be used for live trading)
- **Generation:** Manual via Developer Portal UI
- **Refresh:** Requires manual regeneration after expiration

### Important URLs
- **Developer Portal:** https://developer.saxobank.com
- **SIM REST Base:** https://gateway.saxobank.com/sim/openapi
- **SIM Auth Base:** https://sim.logonvalidation.net

## Steps to Complete

### 1. Access Developer Portal
1. Navigate to https://developer.saxobank.com
2. Create account or sign in
3. Complete any required verification steps

### 2. Generate 24h Token
1. Navigate to the token generation section
2. Select SIM environment
3. Generate a new 24-hour access token
4. **IMPORTANT:** Copy the token immediately (it may not be shown again)

### 3. Document Token Details
- Copy the full token string
- Note the expiration timestamp
- Keep token secure (treat as a password)

### 4. Prepare for Next Story
- Have token ready to add to `.env` file
- Note the token format (Bearer token)

## Verification Steps
- [ ] Can access Developer Portal dashboard
- [ ] Token is successfully generated
- [ ] Token string is copied and stored securely
- [ ] Expiration time is noted (24 hours from generation)

## Security Notes
⚠️ **IMPORTANT SECURITY CONSIDERATIONS:**
- Never commit tokens to version control
- Never share tokens publicly
- Tokens expire after 24 hours
- Generate fresh tokens as needed
- SIM tokens cannot access live trading (safe for development)

## Documentation to Update
- None (this is a manual setup step)

## Testing
Manual verification:
- Confirm you can see the token in the Developer Portal
- Confirm token is a long string (JWT format)
- Confirm expiration time shows ~24 hours

## Time Estimate
**30 minutes** (account setup + token generation)

## Dependencies
- None (first story in migration epic)

## Blocks
- Story 001-2-003 (needs token for `.env` configuration)
- Story 001-2-006 (needs token for connection test)

## Notes
- This is a manual, prerequisite step
- Token refresh will need to be repeated daily during development
- Future stories will implement OAuth for long-term automation
- Switzerland location: No restrictions for SIM access

## References
- [Saxo Bank Developer Portal - Environments](https://developer.saxobank.com/openapi/learn/environments)
- [Saxo Bank Developer Portal - Getting Started](https://developer.saxobank.com)
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 10)

## Success Criteria
✅ Story is complete when:
1. Developer Portal access is confirmed
2. 24-hour SIM token is generated
3. Token is copied and ready for use
4. Expiration time is documented
