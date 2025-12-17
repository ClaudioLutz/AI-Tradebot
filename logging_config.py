"""
Logging configuration module for AI-Tradebot.
This module acts as the single entry point for logging setup, providing:
- Non-blocking logging using QueueHandler/QueueListener.
- Automatic redaction of sensitive data (secrets, tokens).
- Context injection (run_id, cycle_id).
- Daily rotation with 30-day retention.
"""

import logging
import logging.handlers
import sys
import os
import re
from queue import Queue
from typing import Optional, List, Dict, Any

# =============================================================================
# Redaction Logic
# =============================================================================

# Regex patterns for sensitive data
# Ordered to ensure specific patterns are checked before generic ones if they overlap,
# though here they are mostly distinct keys.
SENSITIVE_PATTERNS = [
    r'(Access_Token=)([\w\-\._\+\/=]+)',
    r'(Refresh_Token=)([\w\-\._\+\/=]+)',
    r'(ClientKey=)([\w\-\._\+\/=]+)',
    r'(AccountKey=)([\w\-\._\+\/=]+)',
    r'(Authorization:\s*Bearer\s+)([\w\-\._\+\/=]+)',
    r'(access_token=)([\w\-\._\+\/=]+)',
    r'(refresh_token=)([\w\-\._\+\/=]+)',
    r'(client_key=)([\w\-\._\+\/=]+)',
    r'(account_key=)([\w\-\._\+\/=]+)'
]

# We need to be careful not to re-mask already masked values if they contain ***
# But *** contains *, which is not in [\w\-\._] (unless _ includes it? No).
# \w matches [a-zA-Z0-9_].
# \- matches -.
# \. matches .
# So * is NOT matched.
# So "abc***yz" should NOT be matched by ([\w\-\._]+) IF the regex engine stops at *.

# However, my debug script showed:
# Matched matched again: Access_Token=abc
# Because "abc" IS matched by [\w\-\._]+.

# So the second pass (lowercase version) sees Access_Token=abc***yz.
# It matches "Access_Token=abc".
# "abc" is length 3.
# It replaces it with "***".
# So "Access_Token=******yz".

# Solution: Combine patterns or ensure we don't match partially masked values.
# Or better, just use one set of patterns with IGNORECASE and ensure uniqueness.

# Unique patterns (keys only), using IGNORECASE
UNIQUE_KEYS = [
    r'Access_Token=',
    r'Refresh_Token=',
    r'ClientKey=',
    r'AccountKey=',
    r'Authorization:\s*Bearer\s+',
    r'access_token=',
    r'refresh_token=',
    r'client_key=',
    r'account_key='
]

# But I want to match the Value too.
# If I use one giant regex, I can do it in one pass.
# Or just ensure I don't have duplicate/overlapping patterns that re-match.

# The issue is I have both "Access_Token=" and "access_token=" in the list.
# And I use re.IGNORECASE for EACH of them.
# So "Access_Token=" pattern matches "Access_Token=".
# AND "access_token=" pattern ALSO matches "Access_Token=".

# I should remove the lowercase duplicates if I'm using re.IGNORECASE.

SENSITIVE_KEYS = [
    'Access_Token',
    'Refresh_Token',
    'ClientKey',
    'AccountKey',
    'access_token',
    'refresh_token',
    'client_key',
    'account_key',
]

# Authorization header is special.

# Let's simplify the list to just unique logical keys, and rely on IGNORECASE.
# But wait, python regex keys are distinct.
# If I remove duplicates from the list, I solve the double masking.

FINAL_PATTERNS = [
    r'(Access_Token=)([\w\-\._]+)',
    r'(Refresh_Token=)([\w\-\._]+)',
    r'(ClientKey=)([\w\-\._]+)',
    r'(AccountKey=)([\w\-\._]+)',
    r'(Authorization:\s*Bearer\s+)([\w\-\._]+)',
    # The lowercase ones are redundant if IGNORECASE is used and the uppercase ones match.
    # But wait, "access_token=" (lowercase in string) might not match "Access_Token=" regex if case sensitive.
    # But I am using re.IGNORECASE.
    # So r'(Access_Token=)' with IGNORECASE matches "access_token=".

    # So I can remove the explicit lowercase patterns from the list.
    # But I need to make sure I cover all keys.
    # client_key and ClientKey are different strings (underscore vs no underscore).
    r'(client_key=)([\w\-\._]+)',
    r'(account_key=)([\w\-\._]+)',
    # access_token and Access_Token are same letters, just case.
    # refresh_token and Refresh_Token are same letters.
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FINAL_PATTERNS]

def mask_sensitive(text: str) -> str:
    """
    Replaces sensitive patterns in the text with masked versions.
    Keeps first 3 and last 2 characters where safe; otherwise full mask.
    """
    if not text:
        return text

    masked_text = text
    for pattern in COMPILED_PATTERNS:
        def replace_match(match):
            prefix = match.group(1)
            value = match.group(2)

            if len(value) > 8:
                masked_value = f"{value[:3]}***{value[-2:]}"
            else:
                masked_value = "***"

            return f"{prefix}{masked_value}"

        masked_text = pattern.sub(replace_match, masked_text)

    return masked_text


class SafeFormatter(logging.Formatter):
    """
    Custom Formatter that applies redaction to the message.
    """
    def format(self, record):
        # 1. Mask message
        original_msg = record.msg
        if isinstance(original_msg, str):
            record.msg = mask_sensitive(original_msg)

        # 2. Format as usual
        formatted_message = super().format(record)

        # Restore original message to avoid side effects if record is reused
        record.msg = original_msg

        return formatted_message


class ContextFilter(logging.Filter):
    """
    Filter to inject run_id and cycle_id into log records.
    Defaults to 'N/A' if not present.
    """
    def filter(self, record):
        if not hasattr(record, 'run_id'):
            record.run_id = 'N/A'
        if not hasattr(record, 'cycle_id'):
            record.cycle_id = 'N/A'
        return True


# =============================================================================
# Setup Function
# =============================================================================

def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    retention_days: int = 30
) -> logging.handlers.QueueListener:
    """
    Initializes the logging system with non-blocking handlers.

    Args:
        log_dir: Directory to store log files.
        log_level: Logging level (INFO, DEBUG, etc.).
        retention_days: Number of days to keep log files.

    Returns:
        QueueListener: The listener that must be stopped at shutdown.
    """
    # 1. Create log directory
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "bot.log")

    # 2. Define Formatters
    log_format = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s | run_id=%(run_id)s cycle_id=%(cycle_id)s"
    formatter = SafeFormatter(log_format)

    # 3. Create Handlers

    # File Handler (Daily rotation)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(ContextFilter())

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(ContextFilter())

    # 4. Setup Non-blocking Queue
    log_queue = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # 5. Setup Listener
    listener = logging.handlers.QueueListener(
        log_queue,
        console_handler,
        file_handler,
        respect_handler_level=True
    )

    # 6. Configure Root Logger
    root = logging.getLogger()

    # Set level based on argument
    level_num = getattr(logging, log_level.upper(), logging.INFO)
    root.setLevel(level_num)

    # Remove existing handlers to avoid duplicates
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    root.addHandler(queue_handler)

    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Start listener
    listener.start()

    return listener
