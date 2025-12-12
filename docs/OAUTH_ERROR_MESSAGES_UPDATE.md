# OAuth-Aware Error Messages - Implementation Summary

## Overview
Updated error messages throughout the codebase to differentiate between Manual Token mode and OAuth mode, reducing user confusion when authentication fails.

## Changes Made

### 1. test_connection.py
**Location:** `print_summary()` function

**Change:** The summary section now detects which authentication mode is being used and provides mode-specific guidance.

**Before:**
- Always suggested regenerating 24h token, even when using OAuth
- No differentiation between authentication modes

**After:**
- Detects authentication mode by checking if `SAXO_ACCESS_TOKEN` is set (and non-empty)
- **OAuth Mode:** Suggests running `python scripts/saxo_login.py`
- **Manual Token Mode:** Suggests regenerating token at developer portal
- Also includes alternative mode instructions

**Example Output (OAuth Mode):**
```
Common solutions:
  OAuth Mode:
  1. Run: python scripts/saxo_login.py
  2. Complete browser authentication flow
  3. Retry: python test_connection.py

  Alternative (Manual Token Mode):
  1. Get 24h token at https://developer.saxobank.com
  2. Set SAXO_ACCESS_TOKEN in .env
```

### 2. data/saxo_client.py
**Location:** `_handle_http_error()` method

**Change:** Authentication error messages (HTTP 401/403) now branch based on which mode is active.

**Before:**
```python
raise SaxoAuthenticationError(
    f"Authentication failed (HTTP {status_code}): {error_msg}. "
    "Check your SAXO_ACCESS_TOKEN. Token may be expired (24h limit)."
)
```

**After:**
```python
# Check which authentication mode is being used
token = os.getenv("SAXO_ACCESS_TOKEN")
using_manual_token = token is not None and token.strip() != ""

if using_manual_token:
    auth_help = (
        "Token may be expired (24h limit). "
        "Generate a new token at https://developer.saxobank.com and update SAXO_ACCESS_TOKEN in .env"
    )
else:
    auth_help = (
        "OAuth token may be invalid or expired. "
        "Try running: python scripts/saxo_login.py"
    )

raise SaxoAuthenticationError(
    f"Authentication failed (HTTP {status_code}): {error_msg}. {auth_help}"
)
```

## Technical Details

### Empty String Handling
The logic correctly handles the case where `SAXO_ACCESS_TOKEN=""` in .env:
```python
token = os.getenv("SAXO_ACCESS_TOKEN")
using_manual_token = token is not None and token.strip() != ""
```

This ensures that an empty or whitespace-only token is treated as "OAuth mode" rather than "Manual Token mode".

### Mode Detection Logic
- **Manual Token Mode:** `SAXO_ACCESS_TOKEN` is set to a non-empty value
- **OAuth Mode:** `SAXO_ACCESS_TOKEN` is not set, empty, or contains only whitespace

## Benefits

1. **Reduced Confusion:** Users no longer see misleading "24h token expired" messages when using OAuth
2. **Clear Next Steps:** Error messages provide actionable guidance specific to the auth mode
3. **Consistent Experience:** Both test_connection.py and saxo_client.py use the same logic
4. **Better UX:** New users understand which authentication flow they're using

## Testing

Verified with:
```powershell
python test_connection.py
```

Output correctly shows OAuth-specific guidance when OAuth credentials are configured but token file is missing.

## Files Modified

1. `test_connection.py` - Updated `print_summary()` function
2. `data/saxo_client.py` - Updated `_handle_http_error()` method

## Additional Fix: saxo_login.py Import Issue

### Problem
Running `python scripts/saxo_login.py` directly from the command line resulted in:
```
ModuleNotFoundError: No module named 'auth'
```

This occurred because Python wasn't including the project root in its module search path when running scripts from the `scripts/` subdirectory.

### Solution
Added path manipulation to `scripts/saxo_login.py` to include the project root:

```python
import sys
from pathlib import Path

# Add parent directory to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from auth.saxo_oauth import interactive_login
```

### Testing
Verified the script now runs without import errors:
```powershell
python scripts/saxo_login.py
```

## Backward Compatibility

✅ Fully backward compatible - existing functionality unchanged, only error messages improved.
