# Story 001-2-006: Update API Connection Test

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the connection test script to verify Saxo Bank API access instead of Alpaca so that I can confirm my credentials and network connectivity are working.

## Description
Replace `test_connection.py` to test Saxo Bank OpenAPI endpoints instead of Alpaca. The test should verify authentication and call key Saxo endpoints like `/port/v1/clients/me` and `/port/v1/accounts/me`.

## Prerequisites
- Story 001-2-005 completed (Saxo client implemented)
- Story 001-2-003 completed (environment configured)
- Valid 24h SIM token in `.env`

## Acceptance Criteria
- [ ] `test_connection.py` updated for Saxo API
- [ ] Tests `/port/v1/clients/me` endpoint
- [ ] Tests `/port/v1/accounts/me` endpoint
- [ ] Displays account information
- [ ] Clear success/failure messages
- [ ] Proper exit codes (0=success, 1=failure)
- [ ] Helpful error messages for common issues

## Technical Details

### Current Implementation (Alpaca)
Tests:
- Alpaca clock endpoint
- Alpaca account endpoint
- Uses `alpaca_trade_api` SDK

### New Implementation (Saxo)
Should test:
- `/port/v1/clients/me` - Client information
- `/port/v1/accounts/me` - Account list
- Display account count
- Verify SIM environment

## Implementation

### Complete Updated test_connection.py

```python
"""
Saxo OpenAPI Connection Test
Verifies API credentials and network connectivity.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Import our Saxo client
from data.saxo_client import SaxoClient, SaxoAuthenticationError, SaxoAPIError


def print_header():
    """Print test header."""
    print("=" * 60)
    print("Saxo OpenAPI Connection Test (SIM)")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


def print_section(title):
    """Print section header."""
    print(f"\n{title}")
    print("-" * 60)


def test_environment():
    """Test environment configuration."""
    print_section("1. Environment Configuration")
    
    load_dotenv()
    
    base_url = os.getenv("SAXO_REST_BASE")
    token = os.getenv("SAXO_ACCESS_TOKEN")
    env = os.getenv("SAXO_ENV")
    
    if not base_url:
        print("✗ SAXO_REST_BASE not configured")
        return False
    print(f"✓ SAXO_REST_BASE: {base_url}")
    
    if not token:
        print("✗ SAXO_ACCESS_TOKEN not configured")
        return False
    print(f"✓ SAXO_ACCESS_TOKEN: {'*' * 20}...{token[-4:] if len(token) > 4 else '***'}")
    
    if env:
        print(f"✓ SAXO_ENV: {env}")
    
    # Verify SIM environment
    if "/sim/" not in base_url.lower():
        print("⚠ WARNING: SAXO_REST_BASE does not look like a SIM URL")
        print("  This test is designed for SIM environment")
    else:
        print("✓ SIM environment detected")
    
    return True


def test_client_creation():
    """Test Saxo client instantiation."""
    print_section("2. Client Initialization")
    
    try:
        client = SaxoClient()
        print("✓ SaxoClient created successfully")
        print(f"✓ Environment: {'SIM' if client.is_sim_environment() else 'LIVE'}")
        return client
    except SaxoAuthenticationError as e:
        print(f"✗ Authentication error: {e}")
        return None
    except Exception as e:
        print(f"✗ Client creation failed: {e}")
        return None


def test_client_endpoint(client):
    """Test /port/v1/clients/me endpoint."""
    print_section("3. Client Information (/port/v1/clients/me)")
    
    try:
        response = client.get("/port/v1/clients/me")
        print("✓ Successfully retrieved client information")
        
        # Display key information
        if "ClientKey" in response:
            print(f"  Client Key: {response['ClientKey']}")
        if "Name" in response:
            print(f"  Name: {response['Name']}")
        if "ClientId" in response:
            print(f"  Client ID: {response['ClientId']}")
        
        return True
    except SaxoAuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        print("\n  Possible causes:")
        print("  - Token has expired (24-hour limit)")
        print("  - Token is invalid")
        print("  - Generate new token at https://developer.saxobank.com")
        return False
    except SaxoAPIError as e:
        print(f"✗ API error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_accounts_endpoint(client):
    """Test /port/v1/accounts/me endpoint."""
    print_section("4. Account Information (/port/v1/accounts/me)")
    
    try:
        response = client.get("/port/v1/accounts/me")
        print("✓ Successfully retrieved account information")
        
        # Extract accounts from response
        accounts = []
        if isinstance(response, dict):
            accounts = response.get("Data", [])
        elif isinstance(response, list):
            accounts = response
        
        print(f"✓ Found {len(accounts)} account(s)")
        
        # Display account details
        for i, account in enumerate(accounts, 1):
            print(f"\n  Account {i}:")
            if "AccountKey" in account:
                print(f"    Account Key: {account['AccountKey']}")
            if "AccountId" in account:
                print(f"    Account ID: {account['AccountId']}")
            if "Currency" in account:
                print(f"    Currency: {account['Currency']}")
            if "AccountType" in account:
                print(f"    Type: {account['AccountType']}")
        
        return len(accounts) > 0
    except SaxoAuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        return False
    except SaxoAPIError as e:
        print(f"✗ API error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def print_summary(all_passed):
    """Print test summary."""
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED - Saxo API Connection Successful!")
        print("\nYour environment is ready for development.")
        print("You can now proceed with implementation stories.")
    else:
        print("✗ SOME TESTS FAILED - Please Review Errors Above")
        print("\nCommon solutions:")
        print("  1. Regenerate 24h token at https://developer.saxobank.com")
        print("  2. Update .env with new token")
        print("  3. Run: python verify_env.py")
        print("  4. Retry: python test_connection.py")
    print("=" * 60)


def main():
    """Run all connection tests."""
    print_header()
    
    # Track test results
    tests_passed = []
    
    # Test 1: Environment
    tests_passed.append(test_environment())
    if not tests_passed[-1]:
        print_summary(False)
        return False
    
    # Test 2: Client creation
    client = test_client_creation()
    tests_passed.append(client is not None)
    if not tests_passed[-1]:
        print_summary(False)
        return False
    
    # Test 3: Client info endpoint
    tests_passed.append(test_client_endpoint(client))
    
    # Test 4: Accounts endpoint
    tests_passed.append(test_accounts_endpoint(client))
    
    # Summary
    all_passed = all(tests_passed)
    print_summary(all_passed)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

## Files to Modify
- `test_connection.py` - Replace entire file

## Verification Steps
- [ ] File updated successfully
- [ ] No syntax errors
- [ ] Imports work correctly
- [ ] Script runs without crashes
- [ ] Tests expected endpoints
- [ ] Clear output messages
- [ ] Correct exit codes

## Testing

### Test 1: Successful Connection (with valid token)
```bash
python test_connection.py
```
Expected output:
- Environment checks pass
- Client created successfully
- Client info retrieved
- Accounts retrieved
- "ALL TESTS PASSED" message
- Exit code 0

### Test 2: Missing Credentials
```bash
# Temporarily rename .env
mv .env .env.backup
python test_connection.py
mv .env.backup .env
```
Expected:
- Environment check fails
- Clear error about missing variables
- Exit code 1

### Test 3: Expired Token
```bash
# Use expired or invalid token in .env
# Should see authentication error with helpful message
```
Expected:
- Authentication error
- Message about token expiration
- Link to regenerate token
- Exit code 1

### Test 4: Exit Code Verification
```bash
python test_connection.py
echo Exit code: $?  # Linux/Mac
# or
echo Exit code: $LASTEXITCODE  # Windows PowerShell
```
Expected: Exit code 0 on success, 1 on failure

## Documentation to Update
- README.md (optional - update connection test instructions)

## Output Example

```
============================================================
Saxo OpenAPI Connection Test (SIM)
============================================================
Time: 2025-12-12 22:00:00

1. Environment Configuration
------------------------------------------------------------
✓ SAXO_REST_BASE: https://gateway.saxobank.com/sim/openapi
✓ SAXO_ACCESS_TOKEN: ********************abcd
✓ SAXO_ENV: SIM
✓ SIM environment detected

2. Client Initialization
------------------------------------------------------------
✓ SaxoClient created successfully
✓ Environment: SIM

3. Client Information (/port/v1/clients/me)
------------------------------------------------------------
✓ Successfully retrieved client information
  Client Key: ABC123
  Name: Test Client
  Client ID: 12345

4. Account Information (/port/v1/accounts/me)
------------------------------------------------------------
✓ Successfully retrieved account information
✓ Found 1 account(s)

  Account 1:
    Account Key: XYZ789
    Account ID: SIM-ACC-001
    Currency: USD
    Type: Normal

============================================================
✓ ALL TESTS PASSED - Saxo API Connection Successful!

Your environment is ready for development.
You can now proceed with implementation stories.
============================================================
```

## Time Estimate
**30 minutes** (update script + test thoroughly)

## Dependencies
- Story 001-2-005 completed (Saxo client available)
- Story 001-2-003 completed (environment configured)
- Valid 24h token

## Blocks
- None (other modules can proceed independently)

## Common Issues and Solutions

### Issue: Import error for saxo_client
**Solution:** Ensure Story 001-2-005 is complete

### Issue: Authentication failed
**Solution:** 
1. Check token in .env
2. Regenerate 24h token from Developer Portal
3. Update SAXO_ACCESS_TOKEN in .env

### Issue: Wrong environment warning
**Solution:** Verify SAXO_REST_BASE has "/sim/" in URL

## Token Refresh Workflow
When test fails with authentication error:
1. Go to https://developer.saxobank.com
2. Generate new 24-hour SIM token
3. Update `.env`: `SAXO_ACCESS_TOKEN=new_token_here`
4. Run: `python test_connection.py`

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 5)
- [Saxo Portfolio Service](https://www.developer.saxo/openapi/referencedocs/port/)
- Original Story: `docs/stories/story-001-006-api-connection-verification.md`

## Success Criteria
✅ Story is complete when:
1. `test_connection.py` updated for Saxo
2. All Alpaca code removed
3. Tests run successfully with valid token
4. Clear error messages for common issues
5. Proper exit codes (0/1)
6. Helpful output formatting
7. Account information displayed correctly
