# Story 001-004: API Key Security Configuration

## Story Overview
Configure secure storage and access of Alpaca API credentials using environment variables and .env files, ensuring sensitive data is never committed to version control.

## Parent Epic
[Epic 001: Initial Setup and Environment Configuration](../epics/epic-001-initial-setup-and-environment.md)

## User Story
**As a** developer  
**I want to** securely configure my API credentials using environment variables  
**So that** my sensitive keys are protected and not exposed in the codebase

## Acceptance Criteria
- [ ] .env file created with API key placeholders
- [ ] .env file added to .gitignore
- [ ] .env.example file created for documentation
- [ ] Environment variables load correctly in Python
- [ ] API keys are never hardcoded in source files
- [ ] Verification script confirms credentials are accessible

## Technical Details

### Prerequisites
- Alpaca API keys generated (Story 001-001)
- python-dotenv package installed (Story 001-003)

### Environment Variables Required

| Variable Name | Description |
|---------------|-------------|
| APCA_API_KEY_ID | Alpaca API Key ID |
| APCA_API_SECRET_KEY | Alpaca API Secret Key |
| APCA_API_BASE_URL | API endpoint (paper or live) |

### Steps to Complete

#### 1. Create .env File
Create `.env` in project root with your actual credentials:
```env
# Alpaca API Configuration
# NEVER commit this file to version control!

APCA_API_KEY_ID=your_api_key_id_here
APCA_API_SECRET_KEY=your_api_secret_key_here
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

#### 2. Create .env.example File
Create `.env.example` as a template for other developers:
```env
# Alpaca API Configuration
# Copy this file to .env and fill in your credentials

APCA_API_KEY_ID=your_api_key_id_here
APCA_API_SECRET_KEY=your_api_secret_key_here
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

#### 3. Update .gitignore
Ensure `.gitignore` includes:
```gitignore
# Environment variables
.env
.env.local
.env.*.local

# Virtual environment
venv/
.venv/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
```

#### 4. Create Verification Script
Create `verify_env.py` to test configuration:
```python
"""Verify environment configuration."""
import os
from dotenv import load_dotenv

def verify_environment():
    """Check that all required environment variables are set."""
    load_dotenv()
    
    required_vars = [
        'APCA_API_KEY_ID',
        'APCA_API_SECRET_KEY',
        'APCA_API_BASE_URL'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        else:
            # Show only first/last few characters for security
            masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            print(f"✓ {var}: {masked}")
    
    if missing:
        print(f"\n✗ Missing variables: {', '.join(missing)}")
        return False
    
    print("\n✓ All environment variables configured!")
    return True

if __name__ == "__main__":
    verify_environment()
```

### Loading Environment Variables in Code
```python
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access variables
api_key = os.getenv('APCA_API_KEY_ID')
api_secret = os.getenv('APCA_API_SECRET_KEY')
base_url = os.getenv('APCA_API_BASE_URL')
```

## Definition of Done
- [ ] `.env` file exists with valid credentials (not committed)
- [ ] `.env.example` file exists as template (committed)
- [ ] `.gitignore` includes `.env` pattern
- [ ] `python verify_env.py` runs successfully
- [ ] No credentials are hardcoded anywhere in the project

## Story Points
**Estimate:** 1 point (configuration task)

## Dependencies
- Story 001-001: Alpaca Account Setup (API keys needed)
- Story 001-003: Core Dependencies Installation (python-dotenv needed)

## Security Checklist
- [ ] .env is in .gitignore
- [ ] No secrets in git history
- [ ] .env.example contains only placeholders
- [ ] Team members know to create their own .env
- [ ] CI/CD uses secure environment variable injection

## Notes
- alpaca-trade-api automatically reads APCA_* environment variables
- Consider using a secrets manager for production
- Rotate keys periodically for enhanced security
- Never log or print full API keys
