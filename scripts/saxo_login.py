"""
Saxo OpenAPI OAuth Login Script
Performs one-time interactive login to obtain access and refresh tokens.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth.saxo_oauth import interactive_login


def format_timestamp(timestamp: int) -> str:
    """Format Unix timestamp as readable datetime."""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def main():
    """Run interactive OAuth login flow."""
    print("=" * 60)
    print("Saxo OpenAPI OAuth Login")
    print("=" * 60)
    print()
    print("This script will:")
    print("  1. Open your browser for Saxo authentication")
    print("  2. Capture the authorization code")
    print("  3. Exchange it for access and refresh tokens")
    print("  4. Save tokens to .secrets/saxo_tokens.json")
    print()
    print("Make sure your .env file contains:")
    print("  - SAXO_AUTH_BASE")
    print("  - SAXO_APP_KEY")
    print("  - SAXO_APP_SECRET")
    print("  - SAXO_REDIRECT_URI")
    print()
    input("Press Enter to continue...")
    print()
    
    try:
        tokens = interactive_login()
        
        print()
        print("=" * 60)
        print("✓ Login Successful!")
        print("=" * 60)
        print()
        print("Token Information:")
        print(f"  Access Token Expires:  {format_timestamp(tokens['access_token_expires_at'])}")
        print(f"  Refresh Token Expires: {format_timestamp(tokens['refresh_token_expires_at'])}")
        print()
        print("Tokens saved to: .secrets/saxo_tokens.json")
        print()
        print("Next steps:")
        print("  1. Remove or comment out SAXO_ACCESS_TOKEN in .env")
        print("  2. Run: python test_connection.py")
        print()
        print("Your bot will now automatically refresh tokens as needed!")
        print("=" * 60)
        
        return 0
    
    except KeyError as e:
        print()
        print("=" * 60)
        print("✗ Error: Missing Environment Variable")
        print("=" * 60)
        print(f"\nMissing: {e}")
        print("\nPlease update your .env file with:")
        print("  SAXO_AUTH_BASE=https://sim.logonvalidation.net")
        print("  SAXO_APP_KEY=your_app_key")
        print("  SAXO_APP_SECRET=your_app_secret")
        print("  SAXO_REDIRECT_URI=http://localhost:8765/callback")
        print()
        return 1
    
    except RuntimeError as e:
        print()
        print("=" * 60)
        print("✗ OAuth Error")
        print("=" * 60)
        print(f"\n{e}")
        print()
        return 1
    
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ Unexpected Error")
        print("=" * 60)
        print(f"\n{e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
