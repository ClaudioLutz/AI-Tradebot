"""
Logging context adapter for AI-Tradebot.
This module provides a ContextAdapter to inject run_id and cycle_id into logs,
and utility methods for common logging patterns.
"""

import logging
from typing import Dict, Any, Optional

class TradingContextAdapter(logging.LoggerAdapter):
    """
    Adapter to inject run_id and cycle_id into log records.
    Usage:
        logger = TradingContextAdapter(logging.getLogger(__name__), {'run_id': '...', 'cycle_id': '...'})
        logger.info("message")
    """
    def process(self, msg, kwargs):
        # Merge extra context (run_id, cycle_id) into log record
        # The 'extra' dict in kwargs is passed to the Logger.log method
        # and eventually to the LogRecord.

        # We want to ensure run_id and cycle_id are top-level attributes on the LogRecord
        # so that our ContextFilter (which defaults them to N/A) sees them if they are passed.
        # However, standard logging only pulls from 'extra' to set attributes on LogRecord.

        extra = kwargs.get('extra', {})
        if self.extra:
            extra.update(self.extra)

        kwargs['extra'] = extra
        return msg, kwargs

    def with_context(self, **new_context):
        """
        Returns a new adapter with updated context.
        """
        current_context = self.extra.copy() if self.extra else {}
        current_context.update(new_context)
        return TradingContextAdapter(self.logger, current_context)

    def log_event(self, event_name: str, **fields):
        """
        Log a structured event.
        Message is the event name. Fields are appended as key=value.
        """
        kv_pairs = [f"{k}={v}" for k, v in fields.items()]
        msg = f"{event_name} {' '.join(kv_pairs)}".strip()
        self.info(msg)
