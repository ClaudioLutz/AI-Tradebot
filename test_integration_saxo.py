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
        if uic is None:
            print("✗ No UIC found for AAPL")
            return False
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
