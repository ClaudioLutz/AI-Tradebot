# Story 001-002: Python Environment Setup

## Story Overview
Set up a Python virtual environment with Python 3.8+ to ensure isolated and reproducible development environment for the trading bot.

## Parent Epic
[Epic 001: Initial Setup and Environment Configuration](../epics/epic-001-initial-setup-and-environment.md)

## User Story
**As a** developer  
**I want to** set up an isolated Python virtual environment  
**So that** I can manage dependencies without conflicts and ensure reproducibility

## Acceptance Criteria
- [ ] Python 3.8 or higher is installed and accessible
- [ ] Virtual environment created in project directory
- [ ] Virtual environment can be activated successfully
- [ ] Python version verified within virtual environment
- [ ] pip is up-to-date in the virtual environment

## Technical Details

### Prerequisites
- Python 3.8+ installed on the system
- Access to command line/terminal

### Steps to Complete

#### 1. Verify Python Installation
```bash
python --version
# Should output Python 3.8.x or higher
```

#### 2. Create Virtual Environment
```bash
# Navigate to project directory
cd "c:\Codes\AI Trader"

# Create virtual environment
python -m venv venv
```

#### 3. Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

#### 4. Verify Activation
```bash
# Should show path to venv Python
which python  # Linux/Mac
where python  # Windows

# Verify Python version
python --version
```

#### 5. Upgrade pip
```bash
python -m pip install --upgrade pip
```

### Virtual Environment Structure
```
AI Trader/
└── venv/
    ├── Include/
    ├── Lib/
    │   └── site-packages/
    ├── Scripts/  (Windows) or bin/ (Linux/Mac)
    │   ├── activate
    │   ├── pip
    │   └── python
    └── pyvenv.cfg
```

## Definition of Done
- [ ] `python --version` shows 3.8+
- [ ] `venv` folder exists in project root
- [ ] Virtual environment activates without errors
- [ ] pip is upgraded to latest version
- [ ] `venv/` is added to `.gitignore`

## Story Points
**Estimate:** 1 point (simple setup task)

## Dependencies
- Python 3.8+ must be installed on the system

## Notes
- Always activate the virtual environment before installing packages
- The venv folder should not be committed to version control
- Consider using `python3` command on systems with multiple Python versions
- PowerShell may require execution policy change: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
