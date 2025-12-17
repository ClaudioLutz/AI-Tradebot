# Story 007-001: Core Logging Infrastructure & Redaction

**Epic:** [Epic 007: Logging and Scheduling System](../../epics/epic-007-logging-and-scheduling.md)
**Status:** Not Started
**Effort:** 5 Story Points
**Priority:** High

## User Story
As a **developer and operator**, I want **a centralized, non-blocking logging configuration module with automatic redaction** so that I can **capture high-fidelity debug info without leaking sensitive secrets or slowing down trade execution**.

## Acceptance Criteria
- [ ] `logging_config.py` module created.
- [ ] `setup_logging()` function initializes Console and File handlers.
- [ ] Mandatory **Non-blocking logging** implemented using `QueueHandler` and `QueueListener`.
- [ ] Log rotation configured (default: daily, 30-day retention).
- [ ] Custom `ContextFilter` implemented to inject `run_id`, `cycle_id` (defaulting to 'N/A' if missing).
- [ ] `mask_sensitive()` utility implemented and applied to all log messages.
- [ ] Redaction logic strictly hides: tokens, keys, secrets, authorization headers.
- [ ] Log format follows the grep-friendly key=value standard.
- [ ] Unit tests verify that secrets are masked and rotation logic is valid.

## Technical Details

### 1. `logging_config.py` Structure

The module should act as the single entry point for logging setup.

```python
import logging
import logging.handlers
import sys
import os
from queue import Queue

# ... imports for ContextFilter and Redaction ...

def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    retention_days: int = 30
):
    """
    Initializes the logging system with non-blocking handlers.

    1. Creates log_dir if not exists.
    2. Sets up a TimedRotatingFileHandler (midnight rotation).
    3. Sets up a StreamHandler (Console).
    4. Wraps both in a QueueListener/QueueHandler for non-blocking I/O.
    5. Applies a custom Formatter with redaction.
    """
    # implementation details...
```

### 2. Redaction & Formatting

We need a custom formatter that calls a redaction helper *before* formatting the message.

```python
import re

SENSITIVE_PATTERNS = [
    r'Access_Token=[\w\-\._]+',
    r'Refresh_Token=[\w\-\._]+',
    r'ClientKey=[\w\-\._]+',
    r'AccountKey=[\w\-\._]+',
    r'Authorization:\s*Bearer\s+[\w\-\._]+'
]

def mask_sensitive(text: str) -> str:
    """
    Replaces sensitive patterns in the text with '***'.
    Uses regex for tokens/keys.
    """
    # Logic to mask strict patterns
    # Also logic to mask generic key=value if key implies secret (e.g. "password=...")
    pass

class SafeFormatter(logging.Formatter):
    def format(self, record):
        # 1. Mask message
        record.msg = mask_sensitive(str(record.msg))

        # 2. Mask args if present
        if isinstance(record.args, dict):
            # recursive masking...
            pass

        return super().format(record)
```

### 3. Log Format

The formatter string should look like:
`%(asctime)s | %(levelname)-5s | %(name)s | %(message)s | run_id=%(run_id)s cycle_id=%(cycle_id)s`

Note: `run_id` and `cycle_id` must be injected via a `logging.Filter` attached to the handlers.

### 4. Non-Blocking Implementation

```python
    # Example snippet for setup_logging
    log_queue = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # Real handlers
    file_handler = logging.handlers.TimedRotatingFileHandler(...)
    console_handler = logging.StreamHandler(sys.stdout)

    # Listener
    listener = logging.handlers.QueueListener(
        log_queue,
        console_handler,
        file_handler,
        respect_handler_level=True
    )

    root = logging.getLogger()
    root.addHandler(queue_handler)
    root.setLevel(log_level)

    listener.start()
    return listener  # Return to main to stop() at shutdown
```

## Dependencies
- None. This is a foundational module.

## Testing Strategy
- **Unit Test**: `test_logging_redaction.py`
    - Create a logger with a memory handler.
    - Log a message containing `ClientKey=A1234567`.
    - Assert the stored record contains `ClientKey=***`.
- **Unit Test**: `test_logging_rotation.py`
    - mock `TimedRotatingFileHandler` to ensure retention args are passed correctly.
