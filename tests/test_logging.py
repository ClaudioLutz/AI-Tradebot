import unittest
import logging
import os
import shutil
import time
from logging_config import mask_sensitive, ContextFilter, setup_logging, SafeFormatter

class TestLoggingRedaction(unittest.TestCase):

    def test_mask_sensitive_token(self):
        text = "Access_Token=abc123456789xyz"
        masked = mask_sensitive(text)
        self.assertEqual(masked, "Access_Token=abc***yz")

    def test_mask_sensitive_short_token(self):
        text = "ClientKey=12345"
        masked = mask_sensitive(text)
        self.assertEqual(masked, "ClientKey=***")

    def test_mask_sensitive_multiple(self):
        text = "ClientKey=1234567890 Access_Token=secretvalue"
        masked = mask_sensitive(text)
        self.assertIn("ClientKey=123***90", masked)
        self.assertIn("Access_Token=sec***ue", masked)

    def test_mask_no_sensitive_data(self):
        text = "Order placed successfully"
        masked = mask_sensitive(text)
        self.assertEqual(masked, text)

    def test_context_filter_defaults(self):
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "msg", (), None)
        f = ContextFilter()
        f.filter(record)
        self.assertEqual(record.run_id, 'N/A')
        self.assertEqual(record.cycle_id, 'N/A')

    def test_context_filter_existing(self):
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "msg", (), None)
        record.run_id = "test_run"
        record.cycle_id = "test_cycle"
        f = ContextFilter()
        f.filter(record)
        self.assertEqual(record.run_id, "test_run")
        self.assertEqual(record.cycle_id, "test_cycle")

    def test_safe_formatter(self):
        formatter = SafeFormatter("%(message)s")
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "ClientKey=1234567890", (), None)
        formatted = formatter.format(record)
        self.assertEqual(formatted, "ClientKey=123***90")

        # Verify original record message is preserved (not modified in place permanently for other handlers)
        self.assertEqual(record.msg, "ClientKey=1234567890")

class TestLoggingSetup(unittest.TestCase):
    def setUp(self):
        self.log_dir = "test_logs"
        if os.path.exists(self.log_dir):
            shutil.rmtree(self.log_dir)

    def tearDown(self):
        if os.path.exists(self.log_dir):
            shutil.rmtree(self.log_dir)

    def test_setup_logging_creates_file(self):
        listener = setup_logging(log_dir=self.log_dir, log_level="DEBUG")
        try:
            logger = logging.getLogger("test_logger")
            logger.info("Test log message")

            # Wait for queue to drain
            time.sleep(0.1)

            self.assertTrue(os.path.exists(os.path.join(self.log_dir, "bot.log")))

            with open(os.path.join(self.log_dir, "bot.log"), "r") as f:
                content = f.read()
                self.assertIn("Test log message", content)
                self.assertIn("run_id=N/A", content)
        finally:
            listener.stop()

if __name__ == '__main__':
    unittest.main()
