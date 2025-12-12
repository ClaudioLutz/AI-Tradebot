# Story 001-2-002: Update Dependencies (Remove Alpaca, Add Saxo Requirements)

## Epic
Epic 001.2: Saxo Bank Migration and Integration

## User Story
As a developer, I want to update the project dependencies to replace Alpaca-specific packages with Saxo-compatible libraries so that the system can communicate with the Saxo OpenAPI.

## Description
Remove the `alpaca-trade-api` package and add `requests` library for direct REST API calls to Saxo Bank. Maintain other essential dependencies like `pandas`, `schedule`, and `python-dotenv`.

## Prerequisites
- Python environment active
- `requirements.txt` exists in project root

## Acceptance Criteria
- [ ] `alpaca-trade-api` removed from `requirements.txt`
- [ ] `requests` library added to `requirements.txt`
- [ ] All dependencies installed successfully
- [ ] No Alpaca-specific packages remain
- [ ] Existing core dependencies preserved (pandas, schedule, python-dotenv)

## Technical Details

### Current Dependencies (Alpaca-based)
```txt
alpaca-trade-api
pandas
schedule
python-dotenv
```

### New Dependencies (Saxo-compatible)
```txt
pandas
schedule
python-dotenv
requests
```

### Changes Summary
- **Remove:** `alpaca-trade-api` (Alpaca SDK)
- **Add:** `requests` (HTTP library for REST API calls)
- **Keep:** `pandas`, `schedule`, `python-dotenv` (still needed)

## Implementation Steps

### 1. Update requirements.txt
Remove Alpaca package and add requests:

```txt
pandas
schedule
python-dotenv
requests
```

### 2. Uninstall Alpaca Package
```bash
pip uninstall alpaca-trade-api -y
```

### 3. Install Updated Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Installation
```bash
pip list | grep requests
pip list | grep pandas
pip list | grep schedule
pip list | grep python-dotenv
```

### 5. Confirm No Alpaca Packages
```bash
pip list | grep alpaca
```
Should return no results.

## Files to Modify
- `requirements.txt` - Update package list

## Verification Steps
- [ ] `requirements.txt` updated correctly
- [ ] `pip uninstall alpaca-trade-api` completes successfully
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `requests` library is installed
- [ ] `pip list | grep alpaca` returns nothing
- [ ] Other core packages still present

## Testing
Run these commands to verify:
```bash
# Check requests is installed
python -c "import requests; print(f'requests version: {requests.__version__}')"

# Check pandas is installed
python -c "import pandas; print(f'pandas version: {pandas.__version__}')"

# Check schedule is installed
python -c "import schedule; print(f'schedule version: {schedule.__version__}')"

# Check python-dotenv is installed
python -c "import dotenv; print(f'python-dotenv version: {dotenv.__version__}')"

# Confirm alpaca-trade-api is NOT installed (should fail)
python -c "import alpaca_trade_api" 2>&1 | grep "No module named"
```

Expected: First 4 commands succeed, last command shows "No module named 'alpaca_trade_api'"

## Documentation to Update
- None (requirements.txt is self-documenting)

## Time Estimate
**15 minutes** (update file + reinstall dependencies)

## Dependencies
- Story 001-2-001 completed (have environment ready)

## Blocks
- Story 001-2-005 (Saxo client needs `requests` library)
- Story 001-2-006 (connection test needs `requests` library)

## Notes
- `requests` is a stable, widely-used HTTP library
- Future consideration: Add `websockets` for streaming data
- Keep version numbers flexible initially (can pin later)
- No changes to Python version requirement

## Optional Future Enhancements
Consider adding later:
- `websockets` - For Saxo streaming API
- `pytest` - For better testing framework
- `pytest-mock` - For mocking API calls in tests

## Rollback Plan
If issues occur:
```bash
# Reinstall Alpaca
pip install alpaca-trade-api

# Restore original requirements.txt from git
git checkout requirements.txt
pip install -r requirements.txt
```

## References
- [Requests Library Documentation](https://requests.readthedocs.io/)
- Analysis Document: `docs/Alpaca-to-Saxo-analysis.md` (Section 2)

## Success Criteria
✅ Story is complete when:
1. `requirements.txt` has correct dependencies
2. `alpaca-trade-api` is uninstalled
3. `requests` is installed
4. All verification tests pass
5. No import errors for new dependencies
