# Saxo Bank Migration Guide

## Overview
This guide documents the completed migration from Alpaca API to Saxo Bank OpenAPI (SIM environment). It provides setup verification, maintenance procedures, and troubleshooting.

## Migration Summary

### What Changed
- **API Provider:** Alpaca → Saxo Bank
- **Authentication:** API keys → Bearer tokens (24h)
- **Instrument ID:** Symbols → UICs + AssetTypes
- **Dependencies:** alpaca-trade-api → requests
- **Order Flow:** Direct → Precheck + Place

### What Stayed the Same
- Project structure (modular architecture)
- Development workflow
- Paper trading environment
- Core trading logic patterns

## Completed Stories

✅ All Epic 001.2 stories completed:
1. Saxo Developer Portal setup
2. Dependencies updated
3. Environment variables configured
4. Verification script updated
5. REST client implemented
6. Connection test updated
7. Market data module updated
8. Trade execution module updated
9. Configuration watchlist updated
10. Integration testing completed

## Daily Operations

### Token Refresh (Required Daily)
24h tokens expire and must be regenerated:

1. Visit https://developer.saxobank.com
2. Log in to Developer Portal
3. Navigate to token generation
4. Generate new 24h SIM token
5. Copy token
6. Update `.env` file:
   ```bash
   SAXO_ACCESS_TOKEN=your_new_token_here
   ```
7. Verify: `python verify_env.py`

**Set a daily reminder!** Token expires exactly 24 hours after generation.

### Verification Checklist
Run these before starting development:

```bash
# 1. Verify environment
python verify_env.py

# 2. Test connection
python test_connection.py

# 3. Run integration tests
python test_integration_saxo.py
```

All should pass before proceeding.

## Setup Instructions for New Users

### Step 1: Get Saxo Developer Portal Access
1. Go to https://developer.saxobank.com
2. Create account (if needed)
3. Generate 24-hour SIM token
4. Copy the token immediately

### Step 2: Update Environment Variables
1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env  # Windows
   # or
   cp .env.example .env    # Linux/Mac
   ```

2. Edit `.env` and add your token:
   ```
   SAXO_ACCESS_TOKEN=your_actual_token_here
   ```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Verify Setup
```bash
# Check environment variables
python verify_env.py

# Test API connection
python test_connection.py

# Run full integration tests
python test_integration_saxo.py
```

## Known Limitations

### SIM Environment Only
- Current implementation uses 24h tokens (SIM only)
- Cannot access live trading
- SIM data may not reflect real market exactly

### Token Management
- Tokens expire every 24 hours
- No automatic refresh (manual regeneration required)
- Development interrupted if token expires

### Pricing Data
- Price retrieval not yet implemented
- Placeholder function in market_data.py
- Will be added in future epic

### Order Types
- Currently supports Market orders
- Limit and Stop orders need additional parameters
- Will be enhanced in future stories

## Architecture

### Module Responsibilities

**config/settings.py**
- Watchlist configuration (UIC format)
- Trading parameters
- Risk management settings

**data/saxo_client.py**
- REST API communication
- Authentication handling
- Error management

**data/market_data.py**
- Instrument discovery
- UIC lookup
- Price data (placeholder)

**execution/trade_executor.py**
- Order precheck
- Order placement
- Account management

## Troubleshooting

### Authentication Errors

**Symptom:** 401/403 errors, "Authentication failed"

**Solutions:**
1. Check token hasn't expired:
   - Tokens last exactly 24 hours
   - Regenerate at developer portal
2. Verify token in .env:
   - No extra spaces
   - Complete token string copied
3. Test: `python test_connection.py`

### Import Errors

**Symptom:** "No module named 'data.saxo_client'"

**Solutions:**
1. Verify all files created:
   ```bash
   ls data/saxo_client.py
   ```
2. Check Python path
3. Ensure in correct directory

### Instrument Not Found

**Symptom:** "No instrument found for 'AAPL'"

**Solutions:**
1. Check asset type correct:
   - "Stock" for equities
   - "FxSpot" for forex
2. Try different keyword
3. Check spelling
4. Verify instrument available in SIM

### Order Precheck Fails

**Symptom:** Precheck returns error

**Common Causes:**
1. **Insufficient funds:** SIM account balance
2. **Market closed:** Check trading hours
3. **Invalid amount:** Too small/large
4. **Wrong instrument:** UIC or AssetType incorrect

**Solutions:**
- Check account balance
- Verify trading hours
- Adjust order size
- Confirm instrument details

## Testing

### Safe Tests (No Trading)
These tests don't place orders:
- `python verify_env.py`
- `python test_connection.py`
- `python test_integration_saxo.py`
- Order precheck functions

### Caution: Real Orders
These place actual orders (SIM environment):
- `trade_executor.place_order()` with `precheck_first=False`
- Any strategy that calls place_order

**Always precheck before placing orders!**

## Next Steps

### Immediate (Required for Trading)
1. Implement price retrieval (market_data.py)
2. Update strategy module for Saxo
3. Test with simple strategy
4. Monitor first trades carefully

### Near Term (Recommended)
1. Implement OAuth for persistent authentication
2. Add limit/stop order support
3. Position management functions
4. Historical data retrieval

### Long Term (Future Epics)
1. Live trading transition
2. Advanced order types
3. Risk management enhancements
4. Performance analytics
5. Multi-account support

## Common UICs for Testing

- **AAPL (Stock):** UIC 211
- **MSFT (Stock):** UIC 267
- **BTCUSD (FxSpot/FxCrypto):** UIC 21700189
- **ETHUSD (FxSpot/FxCrypto):** UIC 21750301
- **EURUSD (FxSpot):** UIC 21

Note: UICs may vary by account/region - always discover via API

## Resources

### Saxo Documentation
- [Developer Portal](https://developer.saxobank.com)
- [OpenAPI Reference](https://www.developer.saxo/openapi/referencedocs)
- [Trading API](https://www.developer.saxo/openapi/referencedocs/trade)
- [Portfolio API](https://www.developer.saxo/openapi/referencedocs/port)
- [OpenAPI Help](https://openapi.help.saxo/)

### Project Documentation
- Epic: `docs/epics/epic-001.2-saxo-bank-migration.md`
- Analysis: `docs/Alpaca-to-Saxo-analysis.md`
- Stories: `docs/stories/story-001-2-*.md`

## File Changes Summary

### Modified Files
- `.env.example` - Saxo variables
- `.env` - Actual credentials
- `requirements.txt` - New dependencies
- `verify_env.py` - Saxo validation
- `test_connection.py` - Saxo endpoints
- `config/settings.py` - Watchlist format
- `data/market_data.py` - UIC discovery
- `execution/trade_executor.py` - Saxo orders

### New Files
- `data/saxo_client.py` - REST client
- `test_integration_saxo.py` - Integration tests
- `docs/SAXO_MIGRATION_GUIDE.md` - This guide

### Unchanged Files
- Project structure (folders)
- `.gitignore`
- Test files (need updates in future)
- Strategy files (need updates in future)
- Main orchestration (needs updates in future)

## Success Metrics

✓ All integration tests pass  
✓ Can connect to Saxo API  
✓ Can discover instruments  
✓ Can precheck orders  
✓ No Alpaca dependencies remaining  
✓ Documentation complete  

## Conclusion

The Saxo Bank migration is complete for core infrastructure. The system can:
- Authenticate with Saxo OpenAPI
- Discover instruments by keyword
- Look up UICs and details
- Retrieve account information
- Precheck orders safely

**Next phase:** Implement trading strategies using the new infrastructure.

---

**For support or questions:**
- Review story documentation in `docs/stories/story-001-2-*.md`
- Check epic overview in `docs/epics/epic-001.2-saxo-bank-migration.md`
- Consult analysis document in `docs/Alpaca-to-Saxo-analysis.md`
