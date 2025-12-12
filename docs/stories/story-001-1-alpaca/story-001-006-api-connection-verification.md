# Story 001-006: API Connection Verification

## Story Overview
Create and execute a test script to verify successful connection to the Alpaca paper trading API, confirming that authentication and basic API calls work correctly.

## Parent Epic
[Epic 001: Initial Setup and Environment Configuration](../epics/epic-001-initial-setup-and-environment.md)

## User Story
**As a** developer  
**I want to** verify that I can successfully connect to the Alpaca API  
**So that** I can confirm my setup is complete and ready for development

## Acceptance Criteria
- [ ] Test script successfully authenticates with Alpaca
- [ ] Market clock status can be retrieved
- [ ] Account information can be fetched
- [ ] Paper trading mode is confirmed (not live)
- [ ] Script provides clear success/failure output
- [ ] Error handling for common connection issues

## Technical Details

### Prerequisites
- Alpaca account created (Story 001-001)
- Python environment set up (Story 001-002)
- Dependencies installed (Story 001-003)
- API credentials configured (Story 001-004)

### API Endpoints to Test

| Endpoint | Purpose |
|----------|---------|
| GET /v2/clock | Market clock status |
| GET /v2/account | Account information |
| GET /v2/positions | Current positions |

### Test Script: test_connection.py

```python
"""
Alpaca API Connection Test Script

This script verifies that the Alpaca API connection is properly configured
and working. It tests authentication, market clock, and account access.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

def test_connection():
    """Test connection to Alpaca API."""
    
    print("=" * 50)
    print("Alpaca API Connection Test")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load environment variables
    load_dotenv()
    
    # Check environment variables
    api_key = os.getenv('APCA_API_KEY_ID')
    api_secret = os.getenv('APCA_API_SECRET_KEY')
    base_url = os.getenv('APCA_API_BASE_URL')
    
    if not all([api_key, api_secret, base_url]):
        print("✗ ERROR: Missing environment variables!")
        print("  Ensure APCA_API_KEY_ID, APCA_API_SECRET_KEY, and APCA_API_BASE_URL are set")
        return False
    
    print(f"✓ Environment variables loaded")
    print(f"  Base URL: {base_url}")
    print()
    
    # Verify paper trading mode
    if 'paper' not in base_url.lower():
        print("⚠ WARNING: Base URL does not appear to be paper trading!")
        print("  Ensure you're using: https://paper-api.alpaca.markets")
        response = input("  Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborting test.")
            return False
    else:
        print("✓ Paper trading mode confirmed")
    print()
    
    try:
        import alpaca_trade_api as tradeapi
        
        # Initialize API client
        api = tradeapi.REST(
            key_id=api_key,
            secret_key=api_secret,
            base_url=base_url,
            api_version='v2'
        )
        
        # Test 1: Get Market Clock
        print("Testing Market Clock...")
        clock = api.get_clock()
        print(f"✓ Market Clock Retrieved")
        print(f"  Market Open: {clock.is_open}")
        print(f"  Next Open: {clock.next_open}")
        print(f"  Next Close: {clock.next_close}")
        print()
        
        # Test 2: Get Account Information
        print("Testing Account Access...")
        account = api.get_account()
        print(f"✓ Account Information Retrieved")
        print(f"  Account ID: {account.id[:8]}...")
        print(f"  Account Status: {account.status}")
        print(f"  Buying Power: ${float(account.buying_power):,.2f}")
        print(f"  Cash: ${float(account.cash):,.2f}")
        print(f"  Portfolio Value: ${float(account.portfolio_value):,.2f}")
        print()
        
        # Test 3: Get Positions (may be empty)
        print("Testing Positions Access...")
        positions = api.list_positions()
        print(f"✓ Positions Retrieved")
        print(f"  Current Positions: {len(positions)}")
        print()
        
        # All tests passed
        print("=" * 50)
        print("✓ ALL TESTS PASSED - API Connection Successful!")
        print("=" * 50)
        return True
        
    except tradeapi.rest.APIError as e:
        print(f"✗ API Error: {e}")
        if "forbidden" in str(e).lower():
            print("  Check your API keys are correct")
        return False
    except Exception as e:
        print(f"✗ Connection Error: {e}")
        print("  Check your internet connection and API credentials")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
```

### Steps to Complete

#### 1. Create Test Script
Save the script as `test_connection.py` in the project root.

#### 2. Run the Test
```bash
# Activate virtual environment first
.\venv\Scripts\Activate.ps1  # Windows

# Run test script
python test_connection.py
```

#### 3. Expected Output (Success)
```
==================================================
Alpaca API Connection Test
==================================================
Time: 2024-01-15 10:30:00

✓ Environment variables loaded
  Base URL: https://paper-api.alpaca.markets

✓ Paper trading mode confirmed

Testing Market Clock...
✓ Market Clock Retrieved
  Market Open: True
  Next Open: 2024-01-16 09:30:00-05:00
  Next Close: 2024-01-15 16:00:00-05:00

Testing Account Access...
✓ Account Information Retrieved
  Account ID: abc12345...
  Account Status: ACTIVE
  Buying Power: $100,000.00
  Cash: $100,000.00
  Portfolio Value: $100,000.00

Testing Positions Access...
✓ Positions Retrieved
  Current Positions: 0

==================================================
✓ ALL TESTS PASSED - API Connection Successful!
==================================================
```

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| "forbidden" | Invalid API keys | Regenerate keys in Alpaca dashboard |
| "Connection refused" | Network issue | Check internet connection |
| "Module not found" | Missing package | Run `pip install alpaca-trade-api` |
| "Missing environment variables" | .env not loaded | Check .env file exists and is correct |

## Definition of Done
- [ ] `test_connection.py` script created
- [ ] Script runs without import errors
- [ ] Market clock test passes
- [ ] Account information test passes
- [ ] Positions access test passes
- [ ] Paper trading mode is verified
- [ ] Clear success message displayed

## Story Points
**Estimate:** 2 points (involves API interaction and error handling)

## Dependencies
- Story 001-001: Alpaca Account Setup
- Story 001-002: Python Environment Setup
- Story 001-003: Core Dependencies Installation
- Story 001-004: API Key Security Configuration

## Notes
- This test must pass before proceeding to development
- Run this test whenever API credentials change
- Market clock status depends on current time/day
- Paper trading accounts start with $100,000 virtual funds
