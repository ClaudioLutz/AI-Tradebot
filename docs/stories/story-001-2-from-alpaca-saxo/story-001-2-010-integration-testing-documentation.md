# Story 001-2-010: Integration Testing & Migration Documentation

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want comprehensive integration tests and migration documentation so that I can verify the complete Saxo Bank migration is working correctly and understand how to maintain it.

## Description
Create integration tests that verify all modules work together, update existing tests for Saxo compatibility, and create comprehensive migration documentation including setup guide, troubleshooting, and next steps.

## Prerequisites
- All Stories 001-2-001 through 001-2-009 completed
- All modules migrated to Saxo API
- Valid 24h SIM token available

## Acceptance Criteria
- [ ] Integration test script created
- [ ] End-to-end workflow tested
- [ ] Existing tests updated or documented for update
- [ ] Migration guide document created
- [ ] Troubleshooting guide included
- [ ] Known limitations documented
- [ ] Next steps outlined
- [ ] All tests pass successfully

## Technical Details

### Integration Test Scope
Test complete workflow:
1. Environment configuration
2. API connection
3. Instrument discovery
4. Account key retrieval
5. Order precheck
6. Module integration

### Documentation Scope
Create comprehensive guides:
1. Migration summary
2. Setup verification
3. Daily token refresh workflow
4. Common issues and solutions
5. API limitations
6. Future enhancements

## Implementation

### Part 1: Integration Test Script

Create `test_integration_saxo.py`:

```python
"""
Integration Test for Saxo Bank Migration
Tests complete workflow from configuration to order precheck.
"""
import sys
from datetime import datetime


def print_header(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_section(title):
    """Print subsection."""
    print(f"\n{title}")
    print("-" * 70)


def test_imports():
    """Test 1: Verify all modules can be imported."""
    print_section("Test 1: Module Imports")
    
    try:
        from config import settings
        print("✓ config.settings")
        
        from data.saxo_client import SaxoClient
        print("✓ data.saxo_client")
        
        from data import market_data
        print("✓ data.market_data")
        
        from execution import trade_executor
        print("✓ execution.trade_executor")
        
        print("\n✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return False


def test_configuration():
    """Test 2: Verify configuration is correct."""
    print_section("Test 2: Configuration")
    
    try:
        from config.settings import WATCHLIST, SAXO_ENV, SAXO_REST_BASE
        
        print(f"✓ SAXO_ENV: {SAXO_ENV}")
        print(f"✓ SAXO_REST_BASE: {SAXO_REST_BASE}")
        print(f"✓ WATCHLIST: {len(WATCHLIST)} instruments")
        
        # Validate watchlist format
        required_keys = ['name', 'asset_type']
        for i, entry in enumerate(WATCHLIST):
            missing = [key for key in required_keys if key not in entry]
            if missing:
                print(f"✗ Entry {i} missing keys: {missing}")
                return False
        
        print("✓ Watchlist format valid")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False


def test_api_connection():
    """Test 3: Verify API connection works."""
    print_section("Test 3: API Connection")
    
    try:
        from data.saxo_client import SaxoClient
        
        client = SaxoClient()
        print("✓ Client initialized")
        
        # Test clients/me endpoint
        response = client.get("/port/v1/clients/me")
        print(f"✓ Client info retrieved: {response.get('ClientKey', 'N/A')}")
        
        # Test accounts/me endpoint
        response = client.get("/port/v1/accounts/me")
        accounts = response.get("Data", []) if isinstance(response, dict) else response
        print(f"✓ Accounts retrieved: {len(accounts)} account(s)")
        
        return True
    except Exception as e:
        print(f"✗ API connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check token hasn't expired (24h limit)")
        print("  2. Regenerate token at https://developer.saxobank.com")
        print("  3. Update SAXO_ACCESS_TOKEN in .env")
        return False


def test_instrument_discovery():
    """Test 4: Verify instrument discovery works."""
    print_section("Test 4: Instrument Discovery")
    
    try:
        from data.market_data import find_instrument_uic, get_instrument_details
        
        # Test AAPL lookup
        uic = find_instrument_uic("AAPL", "Stock")
        print(f"✓ Found AAPL: UIC {uic}")
        
        # Get details
        details = get_instrument_details(uic, "Stock")
        print(f"✓ Details: {details.get('Symbol', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"✗ Instrument discovery failed: {e}")
        return False


def test_watchlist_discovery():
    """Test 5: Verify watchlist instrument discovery."""
    print_section("Test 5: Watchlist Discovery")
    
    try:
        from config.settings import WATCHLIST
        from data.market_data import discover_watchlist_instruments
        
        print(f"Discovering UICs for {len(WATCHLIST)} instruments...")
        results = discover_watchlist_instruments(WATCHLIST)
        
        found = sum(1 for r in results if r['status'] == 'found')
        errors = sum(1 for r in results if r['status'] == 'error')
        
        print(f"\nResults:")
        for item in results:
            if item['status'] == 'found':
                print(f"  ✓ {item['name']}: UIC {item['uic']}")
            else:
                print(f"  ✗ {item['name']}: {item['error']}")
        
        print(f"\nSummary: {found} found, {errors} errors")
        
        return errors == 0
    except Exception as e:
        print(f"✗ Watchlist discovery failed: {e}")
        return False


def test_account_operations():
    """Test 6: Verify account operations work."""
    print_section("Test 6: Account Operations")
    
    try:
        from execution.trade_executor import get_account_key, get_open_orders
        
        # Get account key
        account_key = get_account_key()
        print(f"✓ AccountKey: {account_key}")
        
        # Get open orders
        orders = get_open_orders()
        print(f"✓ Open orders: {len(orders)}")
        
        return True
    except Exception as e:
        print(f"✗ Account operations failed: {e}")
        return False


def test_order_precheck():
    """Test 7: Verify order precheck works (safe test)."""
    print_section("Test 7: Order Precheck (Safe - No Trade)")
    
    try:
        from execution.trade_executor import precheck_order
        
        # Precheck small order (AAPL, 1 share)
        print("Prechecking: Buy 1 share of AAPL (UIC 211)...")
        result = precheck_order(211, "Stock", "Buy", 1, "Market")
        
        print("✓ Precheck successful")
        if "Costs" in result:
            print(f"  Estimated costs available")
        
        print("\nNote: No actual order placed - precheck only")
        return True
    except Exception as e:
        print(f"✗ Order precheck failed: {e}")
        print("\nThis may fail if:")
        print("  - Insufficient buying power")
        print("  - Market closed")
        print("  - Invalid instrument")
        return False


def run_all_tests():
    """Run all integration tests."""
    print_header("Saxo Bank Migration - Integration Tests")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Environment: SIM (Simulation)")
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_configuration),
        ("API Connection", test_api_connection),
        ("Instrument Discovery", test_instrument_discovery),
        ("Watchlist Discovery", test_watchlist_discovery),
        ("Account Operations", test_account_operations),
        ("Order Precheck", test_order_precheck),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Migration Successful!")
        print("\nYour Saxo Bank integration is working correctly.")
        print("You can now proceed with implementing trading strategies.")
        return True
    else:
        print("\n⚠ SOME TESTS FAILED - Review errors above")
        print("\nCommon solutions:")
        print("  1. Check token expiration (regenerate if needed)")
        print("  2. Verify all previous stories completed")
        print("  3. Check .env configuration")
        print("  4. See docs/SAXO_MIGRATION_GUIDE.md")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

### Part 2: Migration Guide Document

Create `docs/SAXO_MIGRATION_GUIDE.md`:

```markdown
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

## Resources

### Saxo Documentation
- [Developer Portal](https://developer.saxobank.com)
- [OpenAPI Reference](https://www.developer.saxo/openapi/referencedocs)
- [Trading API](https://www.developer.saxo/openapi/referencedocs/trade)
- [Portfolio API](https://www.developer.saxo/openapi/referencedocs/port)

### Project Documentation
- Epic: `docs/epics/epic-001.2-saxo-bank-migration.md`
- Analysis: `docs/Alpaca-to-Saxo-analysis.md`
- Stories: `docs/stories/story-001-2-*.md`

### Support
- Saxo Support: https://openapi.help.saxo/
- Project Issues: Use GitHub issues (if applicable)

## Appendix: File Changes

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
- Test files (need updates)
- Strategy files (need updates)
- Main orchestration (needs updates)

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

Next phase: Implement trading strategies using the new infrastructure.
```

## Files to Create
- `test_integration_saxo.py` - Integration test script
- `docs/SAXO_MIGRATION_GUIDE.md` - Migration documentation

## Files to Update (Documentation)
- `README.md` - Update setup instructions for Saxo
- `SETUP_COMPLETE.md` - Note migration completed

## Verification Steps
- [ ] Integration test script created
- [ ] All tests pass
- [ ] Migration guide complete
- [ ] Troubleshooting section helpful
- [ ] Next steps clear
- [ ] Resources linked

## Testing

### Run Integration Tests
```bash
python test_integration_saxo.py
```

Expected: All 7 tests pass

### Verify Documentation
- Read through migration guide
- Follow setup verification steps
- Check all links work
- Ensure troubleshooting covers common issues

## Time Estimate
**2-3 hours** (integration tests + comprehensive documentation)

## Dependencies
- ALL previous stories (001-2-001 through 001-2-009) completed

## Blocks
- None (final story in epic)

## Success Criteria
✅ Story is complete when:
1. Integration test script created
2. All integration tests pass
3. Migration guide document complete
4. Troubleshooting guide included
5. Known limitations documented
6. Next steps outlined
7. All resources linked
8. Documentation reviewed and clear

## References
- Epic: `docs/epics/epic-001.2-saxo-bank-migration.md`
- Analysis: `docs/Alpaca-to-Saxo-analysis.md`
- All previous stories in Epic 001.2
