# Story 001-2-004: Update Environment Verification Script

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the environment verification script to check for Saxo Bank credentials instead of Alpaca so that I can ensure all required configuration is present before running the application.

## Description
Modify `verify_env.py` to validate Saxo Bank environment variables instead of Alpaca variables. Maintain the existing security pattern that masks sensitive credential values in output.

## Prerequisites
- Story 001-2-003 completed (.env updated with Saxo variables)
- `verify_env.py` exists in project root

## Acceptance Criteria
- [ ] Script checks for all required Saxo variables
- [ ] Script does not check for Alpaca variables
- [ ] Token masking functionality preserved
- [ ] Clear error messages for missing variables
- [ ] Success message when all variables present
- [ ] Script runs without errors

## Technical Details

### Current Implementation (Alpaca)
Checks for:
- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `APCA_API_BASE_URL`

### New Implementation (Saxo)
Should check for:
- `SAXO_ENV`
- `SAXO_REST_BASE`
- `SAXO_ACCESS_TOKEN`

Optional variables (don't require, but validate if present):
- `SAXO_AUTH_BASE`
- `SAXO_APP_KEY`
- `SAXO_APP_SECRET`
- `SAXO_REDIRECT_URI`

## Implementation Steps

### 1. Read Current verify_env.py
```bash
cat verify_env.py
```

### 2. Update Required Variables List

Replace the `required_vars` list:

```python
required_vars = [
    "SAXO_ENV",
    "SAXO_REST_BASE",
    "SAXO_ACCESS_TOKEN",
]
```

### 3. Maintain Masking Logic

Keep the existing masking pattern (masks all but last 4 characters):
```python
def mask_value(value, show_last=4):
    if not value or len(value) <= show_last:
        return "***"
    return "*" * (len(value) - show_last) + value[-show_last:]
```

### 4. Update Output Messages

Update any Alpaca-specific messages to reference Saxo:
- "Saxo OpenAPI credentials" instead of "Alpaca credentials"
- Reference to Developer Portal instead of Alpaca dashboard

### 5. Add Environment Validation

Add a check for `SAXO_ENV` value:
```python
saxo_env = os.getenv("SAXO_ENV")
if saxo_env and saxo_env not in ["SIM", "LIVE"]:
    print(f"⚠ Warning: SAXO_ENV should be 'SIM' or 'LIVE', got '{saxo_env}'")
```

### 6. Add SIM URL Validation

Add a warning if using SIM token with non-SIM URL:
```python
rest_base = os.getenv("SAXO_REST_BASE")
if rest_base and "/sim/" not in rest_base.lower():
    print("⚠ Warning: SAXO_REST_BASE does not appear to be a SIM URL")
```

## Complete Updated Script

```python
import os
from dotenv import load_dotenv

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
    
    required_vars = [
        "SAXO_ENV",
        "SAXO_REST_BASE",
        "SAXO_ACCESS_TOKEN",
    ]
    
    optional_vars = [
        "SAXO_AUTH_BASE",
        "SAXO_APP_KEY",
        "SAXO_APP_SECRET",
        "SAXO_REDIRECT_URI",
    ]
    
    missing_vars = []
    
    # Check required variables
    print("\nRequired Variables:")
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = mask_value(value)
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  ✗ {var}: NOT SET")
            missing_vars.append(var)
    
    # Check optional variables
    print("\nOptional Variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            masked = mask_value(value)
            print(f"  ✓ {var}: {masked}")
        else:
            print(f"  - {var}: not set (optional)")
    
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
    if missing_vars:
        print("✗ VERIFICATION FAILED")
        print(f"\nMissing required variables: {', '.join(missing_vars)}")
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
```

## Files to Modify
- `verify_env.py` - Update verification logic

## Verification Steps
- [ ] Script runs without syntax errors
- [ ] Script checks for Saxo variables
- [ ] Script does not check for Alpaca variables
- [ ] Missing variable detection works
- [ ] Token masking works correctly
- [ ] Environment validation works

## Testing

### Test 1: With All Variables Set
```bash
python verify_env.py
```
Expected: All checks pass, success message displayed

### Test 2: With Missing Token (temporarily rename)
```bash
# In .env, comment out SAXO_ACCESS_TOKEN
python verify_env.py
```
Expected: Reports SAXO_ACCESS_TOKEN as missing, exits with error

### Test 3: Masking Verification
Token should show as `****...last4chars`

### Test 4: Exit Code Verification
```bash
python verify_env.py
echo $?  # or $LASTEXITCODE on Windows
```
Expected: 0 if all variables present, 1 if missing variables

## Documentation to Update
- None (script is self-documenting)

## Time Estimate
**20 minutes** (update script + test thoroughly)

## Dependencies
- Story 001-2-003 completed (Saxo variables in .env)

## Blocks
- Story 001-2-005 (client implementation)
- Story 001-2-006 (connection test)

## Security Notes
- Masking pattern preserved from original
- Never logs full token values
- Clear distinction between required/optional variables

## Rollback Plan
```bash
# Restore from git
git checkout verify_env.py
```

## Common Issues and Solutions

### Issue: Script reports missing variables
**Solution:** Run Story 001-2-003 to update .env file

### Issue: Masking not working
**Solution:** Check mask_value function is correct

### Issue: Import errors
**Solution:** Ensure python-dotenv is installed (Story 001-2-002)

## References
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 4)
- Original Story: `docs/stories/story-001-004-api-key-security-configuration.md`

## Success Criteria
✅ Story is complete when:
1. Script updated with Saxo variables
2. All Alpaca references removed
3. Script runs successfully
4. Masking works correctly
5. Validation logic works
6. Exit codes correct (0=success, 1=failure)
