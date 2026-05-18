"""
Credential storage audit tests - issue #52.
Verifies no direct plaintext file reads/writes to r_key.txt / r_secret.txt
exist outside of pt_credentials.py (the authorised migration module).
"""
import os
import unittest


APP_DIR = os.path.dirname(__file__)
ALLOWED_PLAINTEXT_MODULE = "pt_credentials.py"


def _get_python_files():
    return [
        f
        for f in os.listdir(APP_DIR)
        if f.endswith(".py")
        and f != ALLOWED_PLAINTEXT_MODULE
        and not f.startswith("test_")
    ]


def _scan_file(filepath):
    """
    Return list of (lineno, line) where the file directly opens
    r_key.txt or r_secret.txt for writing.
    """
    hits = []
    with open(filepath, "r", errors="ignore") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "r_key.txt" not in line and "r_secret.txt" not in line:
            continue
        # Check for open(..., "w") pattern on same or adjacent lines
        context = "".join(lines[max(0, i - 1) : i + 2])
        is_write = '"w"' in context or "'w'" in context
        is_atomic_write = "_atomic_write_text" in context and (
            "r_key" in context or "r_secret" in context
        )
        if is_write or is_atomic_write:
            hits.append((i + 1, line.strip()))
    return hits


def _scan_for_direct_reads(filepath):
    """Return (lineno, line) for direct open() reads of r_key/r_secret."""
    hits = []
    with open(filepath, "r", errors="ignore") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "r_key.txt" not in line and "r_secret.txt" not in line:
            continue
        if "open(" in line and ('"r"' in line or "'r'" in line or "encoding" in line):
            hits.append((i + 1, line.strip()))
    return hits


class TestCredentialAudit(unittest.TestCase):
    """Audit: no module outside pt_credentials.py writes plaintext credentials."""

    def test_no_direct_plaintext_writes(self):
        """
        No file except pt_credentials.py should write directly to
        r_key.txt or r_secret.txt.
        """
        violations = {}
        for fname in _get_python_files():
            fpath = os.path.join(APP_DIR, fname)
            hits = _scan_file(fpath)
            if hits:
                violations[fname] = hits

        if violations:
            details = "\n".join(
                f"  {fname}: " + "; ".join(f"line {lineno}" for lineno, _ in hits)
                for fname, hits in violations.items()
            )
            self.fail(
                f"Plaintext credential WRITES found outside pt_credentials.py:\n{details}"
            )

    def test_no_direct_plaintext_reads_outside_credentials_module(self):
        """
        No file except pt_credentials.py should read r_key.txt / r_secret.txt
        directly. All reads must go through get_credentials() or
        SecureCredentialManager.
        """
        violations = {}
        for fname in _get_python_files():
            fpath = os.path.join(APP_DIR, fname)
            hits = _scan_for_direct_reads(fpath)
            if hits:
                violations[fname] = hits

        if violations:
            details = "\n".join(
                f"  {fname}: " + "; ".join(f"line {lineno}" for lineno, _ in hits)
                for fname, hits in violations.items()
            )
            self.fail(
                f"Direct plaintext credential READS found outside pt_credentials.py:\n{details}"
            )

    def test_pt_credentials_provides_get_credentials(self):
        """pt_credentials.py must expose get_credentials() for all consumers."""
        from pt_credentials import get_credentials, SecureCredentialManager

        self.assertTrue(callable(get_credentials))
        self.assertTrue(callable(SecureCredentialManager))

    def test_get_credentials_returns_none_when_no_creds(self):
        """get_credentials() returns None gracefully when no credentials exist."""
        import tempfile

        tmpdir = tempfile.mkdtemp()
        # Monkey-patch so SecureCredentialManager uses tmp dir
        import pt_credentials as _m

        original_init = _m.SecureCredentialManager.__init__

        def patched_init(self, base_dir=None):
            original_init(self, tmpdir)

        _m.SecureCredentialManager.__init__ = patched_init
        try:
            result = _m.get_credentials()
            # No credentials in temp dir - should return None (not raise)
            self.assertIsNone(result)
        finally:
            _m.SecureCredentialManager.__init__ = original_init
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_pt_hub_uses_encrypt_credentials(self):
        """pt_hub.py must call encrypt_credentials, not write plaintext directly."""
        fpath = os.path.join(APP_DIR, "pt_hub.py")
        with open(fpath, "r", errors="ignore") as f:
            content = f.read()
        self.assertIn(
            "encrypt_credentials",
            content,
            "pt_hub.py must use SecureCredentialManager.encrypt_credentials()",
        )
        # Must NOT write r_key.txt directly
        self.assertNotIn(
            "_atomic_write_text(key_path, api_key)",
            content,
            "pt_hub.py must not write r_key.txt via _atomic_write_text directly",
        )

    def test_pt_hub_reads_via_secure_manager(self):
        """pt_hub.py must call decrypt_credentials, not open r_key.txt directly."""
        fpath = os.path.join(APP_DIR, "pt_hub.py")
        with open(fpath, "r", errors="ignore") as f:
            content = f.read()
        self.assertIn(
            "decrypt_credentials",
            content,
            "pt_hub.py must use SecureCredentialManager.decrypt_credentials()",
        )


if __name__ == "__main__":
    unittest.main()
