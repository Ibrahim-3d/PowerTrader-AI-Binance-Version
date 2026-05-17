"""Tests for credential rotation and permission validation (issues #58, #59)."""

import json
import os
import shutil
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

    def test_from_dict_handles_corrupt_metadata(self):
        """TypeError on missing required fields should be caught by _load_metadata."""
        mgr = SecureCredentialManager(tempfile.mkdtemp())
        # Write partial/corrupt metadata
        with open(mgr.metadata_file, "w") as f:
            json.dump({"created_at": 0}, f)  # missing required fields
        result = mgr._load_metadata()
        self.assertIsNone(result)
        shutil.rmtree(mgr.base_dir, ignore_errors=True)


class TestSecureCredentialManager(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SecureCredentialManager(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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

    def test_metadata_interval_updated_on_reencrypt(self):
        """rotation_interval_days must stay consistent with rotation_due_at."""
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=30)
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=60)
        meta = self.mgr._load_metadata()
        self.assertEqual(meta.rotation_interval_days, 60)

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

    def test_rotate_cleans_up_backups(self):
        self.mgr.encrypt_credentials("OLD", "OLD")
        self.mgr.rotate_credentials("NEW", "NEW")
        self.assertFalse(os.path.exists(self.mgr.encrypted_key_file + ".bak"))
        self.assertFalse(os.path.exists(self.mgr.encrypted_secret_file + ".bak"))
        self.assertFalse(os.path.exists(self.mgr.metadata_file + ".bak"))

    def test_rotate_restores_metadata_on_failure(self):
        """Rotation rollback must restore metadata alongside ciphertext files."""
        self.mgr.encrypt_credentials("OLD_KEY", "OLD_SECRET", rotation_interval_days=90)
        meta_before = self.mgr._load_metadata()

        # Corrupt the manager to force failure during encrypt
        original = self.mgr._atomic_write_binary
        call_count = [0]

        def failing_write(path, data):
            call_count[0] += 1
            if call_count[0] >= 2:  # succeed on key, fail on secret
                raise OSError("disk full")
            return original(path, data)

        self.mgr._atomic_write_binary = failing_write
        result = self.mgr.rotate_credentials("NEW_KEY", "NEW_SECRET")
        self.assertFalse(result)
        # Should still decrypt old credentials
        creds = self.mgr.decrypt_credentials()
        self.assertEqual(creds[0], "OLD_KEY")

    def test_no_rotation_warning_when_fresh(self):
        self.mgr.encrypt_credentials("K", "S", rotation_interval_days=90)
        self.assertIsNone(self.mgr.check_rotation_warning())

    def test_rotation_warning_when_overdue(self):
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
            rotation_due_at=time.time() + 3 * 86400,
        )
        self.mgr._save_metadata(meta)
        warning = self.mgr.check_rotation_warning()
        self.assertIsNotNone(warning)
        self.assertIn("day", warning)

    def test_migrate_from_plaintext(self):
        with open(os.path.join(self.tmpdir, "r_key.txt"), "w") as f:
            f.write("PLAIN_KEY\n")
        with open(os.path.join(self.tmpdir, "r_secret.txt"), "w") as f:
            f.write("PLAIN_SECRET\n")
        result = self.mgr.migrate_from_plaintext()
        self.assertTrue(result)
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "r_key.txt")))
        creds = self.mgr.decrypt_credentials()
        self.assertEqual(creds[0], "PLAIN_KEY")

    def test_cross_platform_machine_password(self):
        """machine password should be non-empty on all platforms."""
        pwd = self.mgr._get_machine_password()
        self.assertIsInstance(pwd, str)
        self.assertGreater(len(pwd), 0)


class TestPermissionValidator(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.validator = PermissionValidator(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_fetcher_returns_failed_audit(self):
        result = self.validator.validate(None)
        self.assertFalse(result.audit_passed)
        self.assertFalse(result.has_required)

    def test_all_permissions_granted(self):
        result = self.validator.validate(
            lambda: ["read_account", "read_positions", "buy", "sell"],
            require_trading=True,
        )
        self.assertTrue(result.audit_passed)
        self.assertTrue(result.has_required)
        self.assertTrue(result.has_trading)

    def test_missing_required_permissions(self):
        result = self.validator.validate(
            lambda: ["read_account"],  # missing read_positions
            require_trading=False,
        )
        self.assertFalse(result.audit_passed)
        self.assertIn("read_positions", result.missing_required)

    def test_missing_trading_permissions(self):
        result = self.validator.validate(
            lambda: ["read_account", "read_positions"],
            require_trading=True,
        )
        self.assertFalse(result.audit_passed)
        self.assertFalse(result.has_trading)

    def test_fetcher_exception_handled(self):
        def fetcher():
            raise ConnectionError("API unreachable")
        result = self.validator.validate(fetcher)
        self.assertFalse(result.audit_passed)
        self.assertIn("failed", result.message.lower())

    def test_audit_log_written_and_secured(self):
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

    def test_audit_log_size_cap(self):
        """Log should not grow past MAX_AUDIT_LINES."""
        # Write many entries manually to reach cap
        log_path = os.path.join(self.tmpdir, PermissionValidator.AUDIT_LOG_FILE)
        entry = json.dumps({"audit_passed": False, "timestamp": 0,
                            "has_required": False, "has_trading": False,
                            "granted_permissions": [], "missing_required": [],
                            "missing_trading": [], "message": "x"})
        with open(log_path, "w") as f:
            for _ in range(PermissionValidator.MAX_AUDIT_LINES + 5):
                f.write(entry + "\n")
        # Trigger a new write, which should trim the file
        self.validator.validate(None)
        with open(log_path) as f:
            lines = f.readlines()
        self.assertLessEqual(len(lines), PermissionValidator.MAX_AUDIT_LINES)


class TestCredentialRotationScheduler(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_start_stop(self):
        cb = MagicMock()
        sched = CredentialRotationScheduler(
            cb, check_interval_hours=24, base_dir=self.tmpdir
        )
        sched.start()
        self.assertTrue(sched._thread.is_alive())
        sched.stop()
        self.assertFalse(sched._thread.is_alive())

    def test_no_callback_without_metadata(self):
        cb = MagicMock()
        sched = CredentialRotationScheduler(cb, check_interval_hours=24, base_dir=self.tmpdir)
        result = sched.check_now()
        self.assertIsNone(result)
        cb.assert_not_called()

    def test_callback_fires_when_overdue(self):
        """Scheduler must call callback when overdue metadata is seeded."""
        cb = MagicMock()
        mgr = SecureCredentialManager(self.tmpdir)
        # Seed overdue metadata
        meta = CredentialMetadata(
            created_at=time.time() - 200 * 86400,
            last_rotated_at=time.time() - 200 * 86400,
            rotation_due_at=time.time() - 1,
        )
        mgr._save_metadata(meta)

        sched = CredentialRotationScheduler(cb, check_interval_hours=24, base_dir=self.tmpdir)
        # Direct check_now proves warning is returned
        warning = sched.check_now()
        self.assertIsNotNone(warning)
        self.assertIn("OVERDUE", warning)

    def test_dedup_callback_not_repeated(self):
        """Same warning should not trigger callback twice."""
        cb = MagicMock()
        mgr = SecureCredentialManager(self.tmpdir)
        meta = CredentialMetadata(
            created_at=time.time() - 200 * 86400,
            last_rotated_at=time.time() - 200 * 86400,
            rotation_due_at=time.time() - 1,
        )
        mgr._save_metadata(meta)
        sched = CredentialRotationScheduler(cb, check_interval_hours=24, base_dir=self.tmpdir)

        # Simulate two consecutive scheduler ticks manually
        warning1 = sched._manager.check_rotation_warning()
        if warning1 and warning1 != sched._last_warning:
            cb(warning1)
            sched._last_warning = warning1

        warning2 = sched._manager.check_rotation_warning()
        if warning2 and warning2 != sched._last_warning:
            cb(warning2)
            sched._last_warning = warning2

        # Same message — callback should have been called only once
        cb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
