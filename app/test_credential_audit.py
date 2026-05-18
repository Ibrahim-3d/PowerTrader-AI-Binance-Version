"""
Credential storage audit tests - issue #52.
Verifies no direct plaintext file reads/writes to r_key.txt / r_secret.txt
exist outside of pt_credentials.py (the authorised migration module).
"""
import ast
import os
import tempfile
import unittest

APP_DIR = os.path.dirname(__file__)

# Modules explicitly allowed to reference credential filenames
ALLOWLIST = {
    "pt_credentials.py",
}


def _get_python_files():
    """
    Walk APP_DIR recursively; exclude allowlisted and test_ files.
    Uses os.walk to cover any future subdirectories.
    """
    result = []
    for dirpath, _, filenames in os.walk(APP_DIR):
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            if fname in ALLOWLIST or fname.startswith("test_"):
                continue
            result.append(os.path.join(dirpath, fname))
    return result


def _ast_cred_opens(filepath, modes=None):
    """
    Parse file with AST and find open() calls whose first arg references
    r_key.txt or r_secret.txt. Returns list of (lineno, description).

    modes: set of mode strings to match (e.g. {"w"}).
           None = match any mode (including default read).
    """
    hits = []
    try:
        with open(filepath, "r", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError):
        return hits

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (
            isinstance(func, ast.Attribute) and func.attr == "open"
        )
        if not is_open or not node.args:
            continue

        first_arg = ast.unparse(node.args[0]) if hasattr(ast, "unparse") else ""
        if "r_key" not in first_arg and "r_secret" not in first_arg:
            continue

        # Collect explicit mode
        explicit_mode = None
        for arg in node.args[1:]:
            val = ast.unparse(arg) if hasattr(ast, "unparse") else ""
            explicit_mode = val.strip("\"'")
        for kw in node.keywords:
            if kw.arg == "mode":
                val = ast.unparse(kw.value) if hasattr(ast, "unparse") else ""
                explicit_mode = val.strip("\"'")

        # If modes filter given, only match those modes
        if modes is not None:
            if explicit_mode not in modes:
                continue

        hits.append((node.lineno, f"open({first_arg!r}, mode={explicit_mode!r})"))

    return hits


class TestCredentialAudit(unittest.TestCase):
    """Audit: no module outside pt_credentials.py writes plaintext credentials."""

    def test_no_direct_plaintext_writes(self):
        """
        No file except pt_credentials.py should open r_key.txt / r_secret.txt
        for writing. Detected via AST (not brittle string matching).
        """
        violations = {}
        for fpath in _get_python_files():
            hits = _ast_cred_opens(fpath, modes={"w", "wb", "a"})
            if hits:
                violations[os.path.basename(fpath)] = hits

        if violations:
            details = "\n".join(
                f"  {fname}: " + "; ".join(f"line {ln}" for ln, _ in hits)
                for fname, hits in violations.items()
            )
            self.fail(
                f"Plaintext credential WRITES outside pt_credentials.py:\n{details}"
            )

    def test_no_direct_plaintext_reads_outside_credentials_module(self):
        """
        No file except pt_credentials.py should open r_key.txt / r_secret.txt
        for reading. All reads must go through get_credentials() or
        SecureCredentialManager.
        """
        violations = {}
        for fpath in _get_python_files():
            hits = _ast_cred_opens(fpath, modes={"r", None})
            if hits:
                violations[os.path.basename(fpath)] = hits

        if violations:
            details = "\n".join(
                f"  {fname}: " + "; ".join(f"line {ln}" for ln, _ in hits)
                for fname, hits in violations.items()
            )
            self.fail(
                f"Direct plaintext credential READS outside pt_credentials.py:\n{details}"
            )

    def test_pt_credentials_public_api(self):
        """pt_credentials.py must expose required public methods."""
        from pt_credentials import SecureCredentialManager, get_credentials

        self.assertTrue(callable(get_credentials))
        for method in (
            "encrypt_credentials",
            "decrypt_credentials",
            "has_encrypted_credentials",
            "has_plaintext_credentials",
        ):
            self.assertTrue(
                hasattr(SecureCredentialManager, method),
                f"SecureCredentialManager missing: {method}",
            )

    def test_secure_credential_manager_roundtrip(self):
        """encrypt + decrypt roundtrip works with a temp directory."""
        from pt_credentials import SecureCredentialManager

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SecureCredentialManager(tmpdir)
            self.assertFalse(mgr.has_encrypted_credentials())
            ok = mgr.encrypt_credentials("test_api_key", "test_secret_b64")
            self.assertTrue(ok)
            self.assertTrue(mgr.has_encrypted_credentials())
            creds = mgr.decrypt_credentials()
            self.assertIsNotNone(creds)
            self.assertEqual(creds[0], "test_api_key")
            self.assertEqual(creds[1], "test_secret_b64")

    def test_get_credentials_returns_none_when_no_creds(self):
        """get_credentials() returns None when vault is empty."""
        from pt_credentials import SecureCredentialManager

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SecureCredentialManager(tmpdir)
            self.assertIsNone(mgr.decrypt_credentials())
            self.assertFalse(mgr.has_encrypted_credentials())

    def test_pt_hub_uses_encrypt_credentials(self):
        """
        pt_hub.py must call encrypt_credentials and must NOT write
        r_key.txt / r_secret.txt directly. Verified via AST.
        """
        fpath = os.path.join(APP_DIR, "pt_hub.py")
        with open(fpath, "r", errors="ignore") as f:
            content = f.read()
        self.assertIn("encrypt_credentials", content)

        write_hits = _ast_cred_opens(fpath, modes={"w", "wb"})
        self.assertEqual(
            write_hits,
            [],
            f"pt_hub.py has direct credential writes: {write_hits}",
        )

    def test_pt_hub_reads_via_secure_manager(self):
        """pt_hub.py must reference decrypt_credentials for reading."""
        fpath = os.path.join(APP_DIR, "pt_hub.py")
        with open(fpath, "r", errors="ignore") as f:
            content = f.read()
        self.assertIn("decrypt_credentials", content)


if __name__ == "__main__":
    unittest.main()
