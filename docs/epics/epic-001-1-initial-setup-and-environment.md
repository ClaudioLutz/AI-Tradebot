# Epic 001-1: Initial Setup and Environment Configuration

**Status:** ⚠️ **LEGACY** - This epic describes the original Alpaca-based prototype. It has been superseded by [Epic 001-2: Saxo Bank Migration](./epic-001-2-saxo-bank-migration.md) for current implementations.

> **Note for New Developers:** If you're setting up the project for the first time, skip to Epic 001-2 for Saxo Bank integration. This epic is retained for historical reference only.

---

## Epic Overview (Historical - Alpaca-based)
Set up the foundational infrastructure for the trading bot including Alpaca account creation, API key configuration, Python environment setup, and project initialization. This epic ensures all prerequisites are in place before development begins.

**⚠️ This epic has been completed and is no longer the active development path.**

## Business Value
- Establishes secure API connectivity to Alpaca paper trading
- Creates a reproducible development environment
- Ensures proper security practices from the start
- Enables safe testing with paper trading mode

## Scope

### In Scope
- Alpaca account creation and API key generation
- Python virtual environment setup (Python 3.8+)
- Installation of core dependencies (alpaca-trade-api, pandas, schedule)
- API key security configuration (environment variables)
- Paper trading endpoint verification
- Project folder structure initialization
- Basic requirements.txt creation

### Out of Scope
- Live trading account setup
- Cloud deployment
- Advanced infrastructure (databases, message queues)
- Production-grade monitoring

## Technical Considerations
- Python 3.8+ required
- Use environment variables for API keys (APCA_API_KEY_ID, APCA_API_SECRET_KEY)
- Paper trading API endpoint: https://paper-api.alpaca.markets
- Virtual environment isolation to avoid dependency conflicts

## Dependencies
- None (this is the first epic)

## Success Criteria
- [ ] Alpaca paper trading account created with valid API keys
- [ ] Python virtual environment activated
- [ ] All required packages installed and listed in requirements.txt
- [ ] API credentials configured via environment variables
- [ ] Successful test connection to Alpaca paper trading API
- [ ] Project folder structure created matching specification
- [ ] README.md with setup instructions created

## Acceptance Criteria
1. User can successfully authenticate with Alpaca paper trading API
2. Environment variables are properly set and not hardcoded
3. All dependencies install without errors
4. Test script can fetch market clock status from Alpaca
5. Project structure matches documented layout

## Stories

This epic is broken down into the following stories:

| Story ID | Title | Points | Dependencies |
|----------|-------|--------|--------------|
| [001-001](../stories/story-001-001-alpaca-account-setup.md) | Alpaca Account Setup | 1 | None |
| [001-002](../stories/story-001-002-python-environment-setup.md) | Python Environment Setup | 1 | None |
| [001-003](../stories/story-001-003-core-dependencies-installation.md) | Core Dependencies Installation | 1 | 001-002 |
| [001-004](../stories/story-001-004-api-key-security-configuration.md) | API Key Security Configuration | 1 | 001-001, 001-003 |
| [001-005](../stories/story-001-005-project-structure-initialization.md) | Project Structure Initialization | 2 | 001-002 |
| [001-006](../stories/story-001-006-api-connection-verification.md) | API Connection Verification | 2 | 001-001 through 001-004 |
| [001-007](../stories/story-001-007-documentation-setup.md) | Documentation Setup | 2 | 001-005 |

**Total Story Points:** 10

### Story Dependency Graph

```
001-001 (Alpaca Account) ──────────────────┐
                                           ├──► 001-004 (Security Config) ──┐
001-002 (Python Env) ──► 001-003 (Deps) ──┘                                 │
         │                                                                   ├──► 001-006 (API Verification)
         └──► 001-005 (Project Structure) ──► 001-007 (Documentation) ◄─────┘
```

## Related Documents
- docs/Beginner-Friendly Trading Bot Project Structure (using Alpaca API).pdf
- requirements.txt (to be created)
- README.md (to be created)

## Notes
- Keep API keys private - never commit to version control
- Add .env file to .gitignore
- Document all setup steps in README for reproducibility
