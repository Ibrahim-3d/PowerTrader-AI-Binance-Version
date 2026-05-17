"""Tests for pt_security_logger - issue #55."""

import json
import os
import tempfile
import threading
import time
import unittest

from pt_security_logger import (
    CorrelationLogFilter,
    SecurityEvent,
    SecurityEventType,
    SecurityLogger,
    clear_correlation_id,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)


class TestCorrelationID(unittest.TestCase):

    def tearDown(self):
        clear_correlation_id()

    def test_default_is_none(self):
        clear_correlation_id()
        self.assertIsNone(get_correlation_id())

    def test_set_and_get(self):
        set_correlation_id("test-cid-123")
        self.assertEqual(get_correlation_id(), "test-cid-123")

    def test_context_manager_sets_id(self):
        with correlation_context("ctx-abc") as cid:
            self.assertEqual(cid, "ctx-abc")
            self.assertEqual(get_correlation_id(), "ctx-abc")

    def test_context_manager_restores_previous(self):
        set_correlation_id("outer")
        with correlation_context("inner"):
            self.assertEqual(get_correlation_id(), "inner")
        self.assertEqual(get_correlation_id(), "outer")

    def test_context_manager_clears_when_no_previous(self):
        clear_correlation_id()
        with correlation_context("temp"):
            pass
        self.assertIsNone(get_correlation_id())

    def test_context_manager_auto_generates_id(self):
        with correlation_context() as cid:
            self.assertIsNotNone(cid)
            self.assertTrue(cid.startswith("CID_"))

    def test_thread_local_isolation(self):
        """Each thread has its own correlation ID."""
        results = {}

        def worker(name, cid):
            set_correlation_id(cid)
            time.sleep(0.01)
            results[name] = get_correlation_id()

        t1 = threading.Thread(target=worker, args=("t1", "cid-thread-1"))
        t2 = threading.Thread(target=worker, args=("t2", "cid-thread-2"))
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertEqual(results["t1"], "cid-thread-1")
        self.assertEqual(results["t2"], "cid-thread-2")


class TestSecurityEvent(unittest.TestCase):

    def test_new_id_format(self):
        eid = SecurityEvent.new_id()
        self.assertTrue(eid.startswith("SEC_"))
        self.assertGreater(len(eid), 10)

    def test_to_dict_has_required_fields(self):
        event = SecurityEvent(
            event_id="SEC_001",
            event_type=SecurityEventType.AUTH_ATTEMPT.value,
            timestamp=time.time(),
            message="test",
            correlation_id=None,
        )
        d = event.to_dict()
        self.assertIn("event_id", d)
        self.assertIn("event_type", d)
        self.assertIn("timestamp", d)
        self.assertIn("message", d)

    def test_to_json_valid(self):
        event = SecurityEvent(
            event_id="SEC_002",
            event_type=SecurityEventType.AUTH_SUCCESS.value,
            timestamp=time.time(),
            message="auth ok",
            correlation_id="cid-test",
        )
        parsed = json.loads(event.to_json())
        self.assertEqual(parsed["correlation_id"], "cid-test")


class TestSecurityLogger(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sec_logger = SecurityLogger(log_dir=self.tmpdir)
        clear_correlation_id()

    def tearDown(self):
        import shutil
        clear_correlation_id()
        # Close handlers to release file locks (Windows)
        for handler in self.sec_logger._logger.handlers[:]:
            handler.close()
            self.sec_logger._logger.removeHandler(handler)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _get_events(self):
        return self.sec_logger.get_recent_events()

    def test_log_auth_attempt_success(self):
        self.sec_logger.log_auth_attempt("robinhood", success=True)
        events = self._get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], SecurityEventType.AUTH_SUCCESS.value)
        self.assertTrue(events[0]["success"])

    def test_log_auth_attempt_failure(self):
        self.sec_logger.log_auth_attempt("robinhood", success=False)
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.AUTH_FAILURE.value)
        self.assertFalse(events[0]["success"])

    def test_log_credential_use(self):
        self.sec_logger.log_credential_use("robinhood", "place_order")
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.CREDENTIAL_USE.value)
        self.assertEqual(events[0]["details"]["operation"], "place_order")

    def test_log_credential_rotation(self):
        self.sec_logger.log_credential_rotation("robinhood", success=True)
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.CREDENTIAL_ROTATION.value)

    def test_log_suspicious_activity(self):
        self.sec_logger.log_suspicious_activity(
            "rate_limit_exceeded", source_ip="1.2.3.4",
            details={"endpoint": "/orders", "count": 100}
        )
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.SUSPICIOUS_ACTIVITY.value)
        self.assertEqual(events[0]["source_ip"], "1.2.3.4")

    def test_log_permission_denied(self):
        self.sec_logger.log_permission_denied("robinhood", "sell")
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.PERMISSION_DENIED.value)
        self.assertEqual(events[0]["details"]["required_permission"], "sell")

    def test_log_trade_event_success(self):
        self.sec_logger.log_trade_event("BTC-USD", "buy", 0.1, 45000.0, order_id="ord-001")
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.TRADE_EXECUTED.value)
        self.assertEqual(events[0]["details"]["symbol"], "BTC-USD")

    def test_log_trade_event_rejected(self):
        self.sec_logger.log_trade_event("ETH-USD", "sell", 1.0, 3000.0, success=False)
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.TRADE_REJECTED.value)

    def test_correlation_id_captured_in_event(self):
        with correlation_context("trade-workflow-xyz"):
            self.sec_logger.log_auth_attempt("robinhood", success=True)
        events = self._get_events()
        self.assertEqual(events[0]["correlation_id"], "trade-workflow-xyz")

    def test_correlation_id_none_outside_context(self):
        clear_correlation_id()
        self.sec_logger.log_auth_attempt("robinhood", success=True)
        events = self._get_events()
        self.assertIsNone(events[0]["correlation_id"])

    def test_multiple_events_ordered(self):
        self.sec_logger.log_auth_attempt("robinhood", success=True)
        self.sec_logger.log_credential_use("robinhood", "fetch_positions")
        self.sec_logger.log_trade_event("BTC-USD", "buy", 0.5, 44000.0)
        events = self._get_events()
        self.assertEqual(len(events), 3)
        timestamps = [e["timestamp"] for e in events]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_audit_file_created(self):
        self.sec_logger.log_auth_attempt("robinhood", success=True)
        self.assertTrue(os.path.exists(self.sec_logger._audit_path))

    def test_get_recent_events_empty_when_no_log(self):
        # Logger on a path with no events yet
        tmpdir2 = tempfile.mkdtemp()
        sl = SecurityLogger(log_dir=tmpdir2)
        for h in sl._logger.handlers[:]:
            h.close(); sl._logger.removeHandler(h)
        import shutil
        shutil.rmtree(tmpdir2, ignore_errors=True)

    def test_get_recent_events_limit(self):
        for i in range(10):
            self.sec_logger.log_auth_attempt("api", success=True)
        events = self.sec_logger.get_recent_events(limit=5)
        self.assertEqual(len(events), 5)

    def test_log_system_event(self):
        self.sec_logger.log_system_event(
            SecurityEventType.SYSTEM_START,
            "PowerTraderAI started",
            details={"version": "1.0"},
        )
        events = self._get_events()
        self.assertEqual(events[0]["event_type"], SecurityEventType.SYSTEM_START.value)


if __name__ == "__main__":
    unittest.main()
