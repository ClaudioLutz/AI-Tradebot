import os
from dotenv import load_dotenv
from auth.saxo_oauth import has_oauth_tokens

def mask_value(value, show_last=4):
    """Mask sensitive value, showing only last N characters."""
    if not value or len(value) <= show_last:
        return "***"
    return "*" * (len(value) - show_last) + value[-show_last:]

def verify_environment():
    """Verify all required Saxo OpenAPI environment variables are set."""
    print("=" * 50)
    print("Environment Variable Verification")
    print("=" * 50)
    
    load_dotenv()
    
    # Always required
    base_required = [
        "SAXO_ENV",
        "SAXO_REST_BASE",
    ]
    
    # OAuth variables
    oauth_vars = [
        "SAXO_AUTH_BASE",
        "SAXO_APP_KEY",
        "SAXO_APP_SECRET",
        "SAXO_REDIRECT_URI",
    ]
    
    missing_vars = []
    
    # Check base required variables
    print("\nBase Required Variables:")
    for var in base_required:
        value = os.getenv(var)
        if value:
            masked = mask_value(value)
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  ✗ {var}: NOT SET")
            missing_vars.append(var)
    
    # Check authentication mode
    print("\nAuthentication Mode:")
    manual_token = os.getenv("SAXO_ACCESS_TOKEN")
    
    if manual_token:
        # Manual token mode
        masked = mask_value(manual_token)
        print(f"  ✓ SAXO_ACCESS_TOKEN: {masked}")
        print("  Mode: Manual Token (expires in 24 hours)")
        auth_configured = True
    else:
        # Check OAuth mode
        print("  - SAXO_ACCESS_TOKEN: not set")
        print("\n  Checking OAuth configuration:")
        oauth_missing = []
        for var in oauth_vars:
            value = os.getenv(var)
            if value:
                masked = mask_value(value)
                print(f"    ✓ {var}: {masked}")
            else:
                print(f"    ✗ {var}: NOT SET")
                oauth_missing.append(var)
        
        if oauth_missing:
            print(f"\n  ✗ OAuth mode incomplete (missing: {', '.join(oauth_missing)})")
            auth_configured = False
        else:
            if has_oauth_tokens():
                print("  ✓ OAuth tokens found (.secrets/saxo_tokens.json)")
                print("  Mode: OAuth (automatic token refresh)")
                auth_configured = True
            else:
                print("  ⚠ OAuth configured but no tokens found")
                print("  Run: python scripts/saxo_login.py")
                auth_configured = True  # Config is valid, just needs login
    
    # Validate values
    print("\nValidation:")
    saxo_env = os.getenv("SAXO_ENV")
    if saxo_env:
        if saxo_env in ["SIM", "LIVE"]:
            print(f"  ✓ SAXO_ENV value '{saxo_env}' is valid")
        else:
            print(f"  ⚠ SAXO_ENV should be 'SIM' or 'LIVE', got '{saxo_env}'")
    
    rest_base = os.getenv("SAXO_REST_BASE")
    if rest_base and saxo_env == "SIM":
        if "/sim/" in rest_base.lower():
            print(f"  ✓ SAXO_REST_BASE matches SIM environment")
        else:
            print(f"  ⚠ SAXO_REST_BASE does not appear to be a SIM URL")
    
    # Final result
    print("\n" + "=" * 50)
    if missing_vars or not auth_configured:
        print("✗ VERIFICATION FAILED")
        if missing_vars:
            print(f"\nMissing required variables: {', '.join(missing_vars)}")
        if not auth_configured:
            print("\nAuthentication not properly configured.")
            print("You need either:")
            print("  - SAXO_ACCESS_TOKEN (manual 24h token), OR")
            print("  - SAXO_AUTH_BASE, SAXO_APP_KEY, SAXO_APP_SECRET, SAXO_REDIRECT_URI (OAuth)")
        print("\nPlease update your .env file with the missing variables.")
        print("See .env.example for template.")
        return False
    else:
        print("✓ ALL REQUIRED VARIABLES SET")
        print("\nYour environment is configured correctly!")
        return True

if __name__ == "__main__":
    import sys
    success = verify_environment()
    sys.exit(0 if success else 1)
