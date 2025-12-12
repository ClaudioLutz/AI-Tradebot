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
from auth.saxo_oauth import has_oauth_tokens


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
    
    # Check authentication mode
    if token:
        # Manual token mode
        print(f"✓ SAXO_ACCESS_TOKEN: {'*' * 20}...{token[-4:] if len(token) > 4 else '***'}")
        print("  Mode: Manual Token (24h expiry)")
    else:
        # OAuth mode
        app_key = os.getenv("SAXO_APP_KEY")
        app_secret = os.getenv("SAXO_APP_SECRET")
        redirect_uri = os.getenv("SAXO_REDIRECT_URI")
        
        if not app_key or not app_secret or not redirect_uri:
            print("✗ Authentication not configured")
            print("  Missing: SAXO_ACCESS_TOKEN (manual mode)")
            print("       OR: SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI (OAuth mode)")
            return False
        
        print(f"✓ SAXO_APP_KEY: {app_key[:8]}...")
        print(f"✓ SAXO_APP_SECRET: {'*' * 20}")
        print(f"✓ SAXO_REDIRECT_URI: {redirect_uri}")
        
        if has_oauth_tokens():
            print("✓ OAuth tokens found")
            print("  Mode: OAuth (automatic refresh)")
        else:
            print("⚠ OAuth tokens not found")
            print("  Run: python scripts/saxo_login.py")
            return False
    
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
