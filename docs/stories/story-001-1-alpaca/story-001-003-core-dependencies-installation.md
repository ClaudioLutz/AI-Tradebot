# Story 001-003: Core Dependencies Installation

## Story Overview
Install all required Python packages for the trading bot and create a requirements.txt file for reproducible dependency management.

## Parent Epic
[Epic 001: Initial Setup and Environment Configuration](../epics/epic-001-initial-setup-and-environment.md)

## User Story
**As a** developer  
**I want to** install all required dependencies and document them  
**So that** the project can be easily set up by other developers

## Acceptance Criteria
- [ ] alpaca-trade-api package installed
- [ ] pandas package installed
- [ ] schedule package installed
- [ ] python-dotenv package installed (for environment variables)
- [ ] requirements.txt file created with pinned versions
- [ ] All packages install without errors

## Technical Details

### Prerequisites
- Virtual environment created and activated (Story 001-002)
- pip is up-to-date

### Core Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| alpaca-trade-api | Alpaca trading API client | Latest |
| pandas | Data manipulation and analysis | Latest |
| schedule | Job scheduling for automated tasks | Latest |
| python-dotenv | Load environment variables from .env | Latest |

### Steps to Complete

#### 1. Activate Virtual Environment
```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

#### 2. Install Core Packages
```bash
pip install alpaca-trade-api pandas schedule python-dotenv
```

#### 3. Generate requirements.txt
```bash
pip freeze > requirements.txt
```

#### 4. Verify Installation
```python
# Test imports in Python REPL
python -c "import alpaca_trade_api; import pandas; import schedule; from dotenv import load_dotenv; print('All packages imported successfully!')"
```

### Expected requirements.txt Content
```
alpaca-trade-api==X.X.X
pandas==X.X.X
schedule==X.X.X
python-dotenv==X.X.X
# Plus any transitive dependencies
```

### Package Descriptions

**alpaca-trade-api**
- Official Python client for Alpaca Trading API
- Provides REST and WebSocket interfaces
- Supports both paper and live trading

**pandas**
- Powerful data analysis library
- Used for handling market data, OHLCV data processing
- Essential for strategy calculations

**schedule**
- Simple job scheduling library
- Used for running trading logic at specified intervals
- Human-friendly syntax for scheduling tasks

**python-dotenv**
- Reads key-value pairs from .env file
- Sets them as environment variables
- Keeps sensitive data out of code

## Definition of Done
- [ ] All four core packages are installed
- [ ] `requirements.txt` exists in project root
- [ ] `pip freeze` shows all packages with versions
- [ ] Test imports succeed without errors
- [ ] No dependency conflicts reported

## Story Points
**Estimate:** 1 point (straightforward installation)

## Dependencies
- Story 001-002: Python Environment Setup (virtual environment must exist)

## Notes
- Consider pinning major versions for stability
- Run `pip install -r requirements.txt` to recreate environment
- Additional packages may be added in future epics (e.g., testing frameworks)
- Check for security vulnerabilities with `pip audit` (optional)
