"""Tests for credential rotation and permission validation (issues #58, #59)."""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from pt_credentials import (
    CredentialMetadata,
    CredentialRotationScheduler,
    PermissionAuditResult,
    PermissionValidator,
    SecureCredentialManager,
    get_credentials,
    validate_credentials_on_startup,
)


class TestCredentialMetadata(unittest.TestCase):

    def test_new_sets_rotation_due_future(self):
        meta = CredentialMetadata.new(90)
        self.assertFalse(meta.is_rotation_due())
        self.assertGreater(meta.days_until_rotation(), 0)

    def test_overdue_when_past_due(self):
        meta = CredentialMetadata(
            created_at=time.time() - 200 * 86400,
            last_rotated_at=time.time() - 200 * 86400,
            rotation_due_at=time.time() - 1,
        )
        self.assertTrue(meta.is_rotation_due())
        self.assertEqual(meta.days_until_rotation(), 0)

    def test_roundtrip_dict(self):
        meta = CredentialMetadata.new(30)
        meta2 = CredentialMetadata.from_dict(meta.to_dict())
        self.assertAlmostEqual(meta.created_at, meta2.created_at, places=3)
        self.assertEqual(meta.rotation_interval_days, meta2.rotation_interval_days)


class TestSecureCredentialManager(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SecureCredentialManager(self.tmpdir)

    def test_encrypt_decrypt_roundtrip(self):
        self.assertTrue(self.mgr.encrypt_credentials("KEY123", "SECRET456"))
        creds = self.mgr.decrypt_credentials()
        self.assertIsNotNone(creds)
        self.assertEqual(creds[0], "KEY123")
        self.assertEqual(creds[1], "SECRET456")

    def test_has_encrypted_after_save(self):
        self.assertFalse(self.mgr.has_encrypted_credentials())
        self.mgr.encrypt_credentials("K", "S")
        self.assertTrue(self.mgr.has_encrypted_credentials())

    def test_metadata_written_on_encrypt(self):
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=30)
        meta = self.mgr._load_metadata()
        self.assertIsNotNone(meta)
        self.assertEqual(meta.rotation_interval_days, 30)

    def test_rotation_status_no_metadata(self):
        status = self.mgr.get_rotation_status()
        self.assertFalse(status["has_metadata"])

    def test_rotation_status_with_metadata(self):
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=90)
        status = self.mgr.get_rotation_status()
        self.assertTrue(status["has_metadata"])
        self.assertFalse(status["rotation_due"])
        self.assertGreater(status["days_until_rotation"], 0)

    def test_rotate_credentials(self):
        self.mgr.encrypt_credentials("OLD_KEY", "OLD_SECRET")
        result = self.mgr.rotate_credentials("NEW_KEY", "NEW_SECRET")
        self.assertTrue(result)
        creds = self.mgr.decrypt_credentials()
        self.assertEqual(creds[0], "NEW_KEY")
        self.assertEqual(creds[1], "NEW_SECRET")
        # Backups cleaned up
        self.assertFalse(os.path.exists(self.mgr.encrypted_key_file + ".bak"))

    def test_no_rotation_warning_when_fresh(self):
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=90)
        self.assertIsNone(self.mgr.check_rotation_warning())

    def test_rotation_warning_when_overdue(self):
        # Force overdue metadata
        meta = CredentialMetadata(
            created_at=time.time() - 100 * 86400,
            last_rotated_at=time.time() - 100 * 86400,
            rotation_due_at=time.time() - 1,
        )
        self.mgr._save_metadata(meta)
        warning = self.mgr.check_rotation_warning()
        self.assertIsNotNone(warning)
        self.assertIn("OVERDUE", warning)

    def test_rotation_warning_when_near_due(self):
        meta = CredentialMetadata(
            created_at=time.time(),
            last_rotated_at=time.time(),
            rotation_due_at=time.time() + 3 * 86400,  # 3 days
        )
        self.mgr._save_metadata(meta)
        warning = self.mgr.check_rotation_warning()
        self.assertIsNotNone(warning)
        self.assertIn("day", warning)

    def test_migrate_from_plaintext(self):
        # Create plaintext files
        with open(os.path.join(self.tmpdir, "r_key.txt"), "w") as f:
            f.write("PLAIN_KEY\n")
        with open(os.path.join(self.tmpdir, "r_secret.txt"), "w") as f:
            f.write("PLAIN_SECRET\n")
        result = self.mgr.migrate_from_plaintext()
        self.assertTrue(result)
        # Plaintext deleted
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "r_key.txt")))
        # Decrypt works
        creds = self.mgr.decrypt_credentials()
        self.assertEqual(creds[0], "PLAIN_KEY")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestPermissionValidator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.validator = PermissionValidator(self.tmpdir)

    def test_no_fetcher_returns_failed_audit(self):
        result = self.validator.validate(None)
        self.assertFalse(result.audit_passed)
        self.assertFalse(result.has_required)

    def test_all_permissions_granted(self):
        def fetcher():
            return ["read_account", "read_positions", "buy", "sell"]
        result = self.validator.validate(fetcher, require_trading=True)
        self.assertTrue(result.audit_passed)
        self.assertTrue(result.has_required)
        self.assertTrue(result.has_trading)

    def test_missing_required_permissions(self):
        def fetcher():
            return ["read_account"]  # missing read_positions
        result = self.validator.validate(fetcher, require_trading=False)
        self.assertFalse(result.audit_passed)
        self.assertIn("read_positions", result.missing_required)

    def test_missing_trading_permissions(self):
        def fetcher():
            return ["read_account", "read_positions"]  # no buy/sell
        result = self.validator.validate(fetcher, require_trading=True)
        self.assertFalse(result.audit_passed)
        self.assertFalse(result.has_trading)

    def test_fetcher_exception_handled(self):
        def fetcher():
            raise ConnectionError("API unreachable")
        result = self.validator.validate(fetcher)
        self.assertFalse(result.audit_passed)
        self.assertIn("failed", result.message.lower())

    def test_audit_log_written(self):
        self.validator.validate(None)
        log_path = os.path.join(self.tmpdir, PermissionValidator.AUDIT_LOG_FILE)
        self.assertTrue(os.path.exists(log_path))
        with open(log_path) as f:
            entry = json.loads(f.readline())
        self.assertIn("audit_passed", entry)

    def test_audit_history_returned(self):
        self.validator.validate(None)
        history = self.validator.get_audit_history()
        self.assertGreater(len(history), 0)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestCredentialRotationScheduler(unittest.TestCase):

    def test_start_stop(self):
        cb = MagicMock()
        sched = CredentialRotationScheduler(
            cb, check_interval_hours=0.001, base_dir=tempfile.mkdtemp()
        )
        sched.start()
        self.assertTrue(sched._thread.is_alive())
        sched.stop()
        self.assertFalse(sched._thread.is_alive())

    def test_no_callback_without_metadata(self):
        cb = MagicMock()
        tmpdir = tempfile.mkdtemp()
        sched = CredentialRotationScheduler(
            cb, check_interval_hours=24, base_dir=tmpdir
        )
        result = sched.check_now()
        self.assertIsNone(result)
        cb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
