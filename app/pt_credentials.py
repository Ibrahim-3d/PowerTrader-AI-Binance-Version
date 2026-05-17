"""
Secure credential management for PowerTraderAI+.
Handles encryption/decryption, rotation scheduling, and API permission validation.
"""

import base64
import hashlib
import json
import logging
import os
import stat
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Set, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_ROTATION_DAYS = 90          # Rotate credentials every 90 days
ROTATION_WARNING_DAYS = 7           # Warn 7 days before expiry
REQUIRED_PERMISSIONS: Set[str] = {  # Minimum required API permissions
    "read_account",
    "read_positions",
}
TRADING_PERMISSIONS: Set[str] = {   # Needed for live trading
    "buy",
    "sell",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class CredentialMetadata:
    """Metadata stored alongside encrypted credentials."""
    created_at: float          # Unix timestamp
    last_rotated_at: float     # Unix timestamp
    rotation_due_at: float     # Unix timestamp
    rotation_interval_days: int = DEFAULT_ROTATION_DAYS

    def is_rotation_due(self) -> bool:
        return time.time() >= self.rotation_due_at

    def days_until_rotation(self) -> int:
        return max(0, int((self.rotation_due_at - time.time()) / 86400))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CredentialMetadata":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def new(cls, interval_days: int = DEFAULT_ROTATION_DAYS) -> "CredentialMetadata":
        now = time.time()
        return cls(
            created_at=now,
            last_rotated_at=now,
            rotation_due_at=now + interval_days * 86400,
            rotation_interval_days=interval_days,
        )


@dataclass
class PermissionAuditResult:
    """Result of an API permission validation check."""
    timestamp: float
    has_required: bool
    has_trading: bool
    granted_permissions: List[str]
    missing_required: List[str]
    missing_trading: List[str]
    audit_passed: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# SecureCredentialManager
# ---------------------------------------------------------------------------
class SecureCredentialManager:
    """Manages encrypted storage and rotation of API credentials."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.salt_file = os.path.join(self.base_dir, ".pt_salt")
        self.encrypted_key_file = os.path.join(self.base_dir, "r_key.enc")
        self.encrypted_secret_file = os.path.join(self.base_dir, "r_secret.enc")
        self.metadata_file = os.path.join(self.base_dir, ".pt_cred_meta")
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_or_create_salt(self) -> bytes:
        if os.path.exists(self.salt_file):
            with open(self.salt_file, "rb") as f:
                return f.read()
        salt = os.urandom(16)
        self._secure_write_binary(self.salt_file, salt)
        return salt

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _get_machine_password(self) -> str:
        machine_info = (
            f"{os.environ.get('COMPUTERNAME', '')}{os.environ.get('USERNAME', '')}"
        )
        return hashlib.sha256(machine_info.encode()).hexdigest()[:32]

    def _secure_write_text(self, filepath: str, content: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self._set_secure_permissions(filepath)

    def _secure_write_binary(self, filepath: str, content: bytes) -> None:
        with open(filepath, "wb") as f:
            f.write(content)
        self._set_secure_permissions(filepath)

    def _set_secure_permissions(self, filepath: str) -> None:
        try:
            os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, AttributeError):
            pass

    # ------------------------------------------------------------------
    # Metadata management
    # ------------------------------------------------------------------
    def _load_metadata(self) -> Optional[CredentialMetadata]:
        if not os.path.exists(self.metadata_file):
            return None
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return CredentialMetadata.from_dict(json.load(f))
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _save_metadata(self, meta: CredentialMetadata) -> None:
        self._secure_write_text(self.metadata_file, json.dumps(meta.to_dict(), indent=2))

    # ------------------------------------------------------------------
    # Core encrypt / decrypt
    # ------------------------------------------------------------------
    def encrypt_credentials(
        self,
        api_key: str,
        private_key_b64: str,
        rotation_interval_days: int = DEFAULT_ROTATION_DAYS,
    ) -> bool:
        """Encrypt and persist credentials, writing metadata."""
        with self._lock:
            try:
                salt = self._get_or_create_salt()
                key = self._derive_key(self._get_machine_password(), salt)
                cipher = Fernet(key)

                self._secure_write_binary(
                    self.encrypted_key_file,
                    cipher.encrypt(api_key.encode("utf-8")),
                )
                self._secure_write_binary(
                    self.encrypted_secret_file,
                    cipher.encrypt(private_key_b64.encode("utf-8")),
                )

                # Update metadata
                existing = self._load_metadata()
                if existing:
                    existing.last_rotated_at = time.time()
                    existing.rotation_due_at = (
                        time.time() + rotation_interval_days * 86400
                    )
                    meta = existing
                else:
                    meta = CredentialMetadata.new(rotation_interval_days)
                self._save_metadata(meta)

                logger.info("Credentials encrypted and saved successfully")
                return True
            except Exception as exc:
                logger.error("Failed to encrypt credentials: %s", exc)
                return False

    def decrypt_credentials(self) -> Optional[Tuple[str, str]]:
        """Decrypt and return (api_key, private_key_b64), or None on failure."""
        with self._lock:
            try:
                if not self.has_encrypted_credentials():
                    return None

                with open(self.salt_file, "rb") as f:
                    salt = f.read()
                key = self._derive_key(self._get_machine_password(), salt)
                cipher = Fernet(key)

                with open(self.encrypted_key_file, "rb") as f:
                    api_key = cipher.decrypt(f.read()).decode("utf-8").strip()
                with open(self.encrypted_secret_file, "rb") as f:
                    private_key = cipher.decrypt(f.read()).decode("utf-8").strip()

                return api_key, private_key
            except Exception as exc:
                logger.error("Failed to decrypt credentials: %s", exc)
                return None

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    def get_rotation_status(self) -> Dict:
        """Return rotation status: due, days remaining, last rotated."""
        meta = self._load_metadata()
        if not meta:
            return {
                "has_metadata": False,
                "rotation_due": False,
                "days_until_rotation": None,
                "last_rotated_at": None,
            }
        return {
            "has_metadata": True,
            "rotation_due": meta.is_rotation_due(),
            "days_until_rotation": meta.days_until_rotation(),
            "last_rotated_at": datetime.fromtimestamp(meta.last_rotated_at).isoformat(),
            "rotation_due_at": datetime.fromtimestamp(meta.rotation_due_at).isoformat(),
        }

    def rotate_credentials(
        self,
        new_api_key: str,
        new_private_key_b64: str,
        rotation_interval_days: int = DEFAULT_ROTATION_DAYS,
    ) -> bool:
        """
        Gracefully rotate credentials:
        1. Backup current encrypted files
        2. Encrypt and save new credentials
        3. Remove backup on success / restore on failure
        """
        with self._lock:
            backup_key = self.encrypted_key_file + ".bak"
            backup_secret = self.encrypted_secret_file + ".bak"
            backed_up = False

            try:
                # Step 1: backup current credentials
                if self.has_encrypted_credentials():
                    import shutil
                    shutil.copy2(self.encrypted_key_file, backup_key)
                    shutil.copy2(self.encrypted_secret_file, backup_secret)
                    backed_up = True

                # Step 2: encrypt new credentials
                success = self.encrypt_credentials(
                    new_api_key, new_private_key_b64, rotation_interval_days
                )

                if success:
                    # Step 3a: clean up backups
                    for f in (backup_key, backup_secret):
                        try:
                            os.remove(f)
                        except OSError:
                            pass
                    logger.info("Credentials rotated successfully")
                    return True

                # Step 3b: restore on failure
                raise RuntimeError("encrypt_credentials returned False")

            except Exception as exc:
                logger.error("Credential rotation failed: %s", exc)
                if backed_up:
                    try:
                        import shutil
                        shutil.copy2(backup_key, self.encrypted_key_file)
                        shutil.copy2(backup_secret, self.encrypted_secret_file)
                        logger.info("Rolled back to previous credentials")
                    except OSError as restore_exc:
                        logger.critical(
                            "CRITICAL: Failed to restore credentials after rotation failure: %s",
                            restore_exc,
                        )
                return False

    def check_rotation_warning(self) -> Optional[str]:
        """
        Return a warning string if rotation is due soon or overdue, else None.
        Call this on startup or periodically.
        """
        status = self.get_rotation_status()
        if not status["has_metadata"]:
            return None
        days = status["days_until_rotation"]
        if status["rotation_due"]:
            return (
                f"SECURITY WARNING: API credentials rotation is OVERDUE. "
                f"Last rotated: {status['last_rotated_at']}. Please rotate immediately."
            )
        if days is not None and days <= ROTATION_WARNING_DAYS:
            return (
                f"SECURITY NOTICE: API credentials rotation due in {days} day(s). "
                f"Due at: {status['rotation_due_at']}."
            )
        return None

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------
    def migrate_from_plaintext(self) -> bool:
        """Migrate existing plaintext r_key.txt / r_secret.txt to encrypted."""
        key_file = os.path.join(self.base_dir, "r_key.txt")
        secret_file = os.path.join(self.base_dir, "r_secret.txt")
        if not (os.path.exists(key_file) and os.path.exists(secret_file)):
            return False
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                api_key = f.read().strip()
            with open(secret_file, "r", encoding="utf-8") as f:
                private_key = f.read().strip()

            if self.encrypt_credentials(api_key, private_key):
                for path in (key_file, secret_file):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                logger.info("Migrated plaintext credentials to encrypted storage")
                return True
        except Exception as exc:
            logger.error("Plaintext migration failed: %s", exc)
        return False

    # ------------------------------------------------------------------
    # State checks
    # ------------------------------------------------------------------
    def has_encrypted_credentials(self) -> bool:
        return all(
            os.path.exists(p)
            for p in (self.encrypted_key_file, self.encrypted_secret_file, self.salt_file)
        )

    def has_plaintext_credentials(self) -> bool:
        return all(
            os.path.exists(os.path.join(self.base_dir, f))
            for f in ("r_key.txt", "r_secret.txt")
        )


# ---------------------------------------------------------------------------
# PermissionValidator
# ---------------------------------------------------------------------------
class PermissionValidator:
    """
    Validates API key permissions on startup against required permission sets.

    Integrates with exchange adapters that expose a `get_permissions()` method.
    Falls back to a mock check when no adapter is available (e.g. CI/CD).
    """

    AUDIT_LOG_FILE = "credential_audit.jsonl"

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self._audit_log = os.path.join(self.base_dir, self.AUDIT_LOG_FILE)

    def validate(
        self,
        permission_fetcher: Optional[Callable[[], List[str]]] = None,
        require_trading: bool = False,
    ) -> PermissionAuditResult:
        """
        Validate API permissions.

        Args:
            permission_fetcher: Callable that returns list of permission strings
                                from the live exchange API. If None, returns a
                                warning result (useful in offline/CI contexts).
            require_trading: If True, also checks for buy/sell permissions.

        Returns:
            PermissionAuditResult with full audit details.
        """
        now = time.time()

        if permission_fetcher is None:
            result = PermissionAuditResult(
                timestamp=now,
                has_required=False,
                has_trading=False,
                granted_permissions=[],
                missing_required=list(REQUIRED_PERMISSIONS),
                missing_trading=list(TRADING_PERMISSIONS) if require_trading else [],
                audit_passed=False,
                message=(
                    "No permission fetcher provided — unable to validate API permissions. "
                    "Provide a permission_fetcher callable to enable validation."
                ),
            )
            self._log_audit(result)
            return result

        try:
            granted = set(permission_fetcher())
        except Exception as exc:
            result = PermissionAuditResult(
                timestamp=now,
                has_required=False,
                has_trading=False,
                granted_permissions=[],
                missing_required=list(REQUIRED_PERMISSIONS),
                missing_trading=list(TRADING_PERMISSIONS) if require_trading else [],
                audit_passed=False,
                message=f"Permission fetch failed: {exc}",
            )
            self._log_audit(result)
            logger.error("API permission validation failed: %s", exc)
            return result

        missing_required = list(REQUIRED_PERMISSIONS - granted)
        missing_trading = list(TRADING_PERMISSIONS - granted) if require_trading else []
        has_required = len(missing_required) == 0
        has_trading = len(missing_trading) == 0
        audit_passed = has_required and (has_trading if require_trading else True)

        if audit_passed:
            message = "API permission validation passed."
        elif not has_required:
            message = (
                f"SECURITY ALERT: API key is missing required permissions: "
                f"{missing_required}. Trading is disabled."
            )
            logger.critical(message)
        else:
            message = (
                f"WARNING: API key is missing trading permissions: {missing_trading}. "
                f"Live trading will be unavailable."
            )
            logger.warning(message)

        result = PermissionAuditResult(
            timestamp=now,
            has_required=has_required,
            has_trading=has_trading,
            granted_permissions=sorted(granted),
            missing_required=missing_required,
            missing_trading=missing_trading,
            audit_passed=audit_passed,
            message=message,
        )
        self._log_audit(result)
        return result

    def _log_audit(self, result: PermissionAuditResult) -> None:
        """Append audit result to JSONL audit log."""
        try:
            with open(self._audit_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except OSError as exc:
            logger.warning("Could not write permission audit log: %s", exc)

    def get_audit_history(self, limit: int = 50) -> List[dict]:
        """Return last `limit` audit records."""
        if not os.path.exists(self._audit_log):
            return []
        try:
            with open(self._audit_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-limit:] if l.strip()]
        except (OSError, json.JSONDecodeError):
            return []


# ---------------------------------------------------------------------------
# CredentialRotationScheduler
# ---------------------------------------------------------------------------
class CredentialRotationScheduler:
    """
    Background scheduler that periodically checks if credentials need rotation
    and fires a notification callback when rotation is due.

    Usage:
        def on_rotation_needed(msg):
            show_gui_alert(msg)  # or email, log, etc.

        scheduler = CredentialRotationScheduler(on_rotation_needed)
        scheduler.start()   # Non-blocking, runs in daemon thread
        ...
        scheduler.stop()
    """

    def __init__(
        self,
        notification_callback: Callable[[str], None],
        check_interval_hours: float = 24.0,
        base_dir: str = None,
    ):
        self._callback = notification_callback
        self._interval = check_interval_hours * 3600
        self._manager = SecureCredentialManager(base_dir)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start scheduler in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="CredentialRotationScheduler", daemon=True
        )
        self._thread.start()
        logger.info("Credential rotation scheduler started (interval: %gh)", self._interval / 3600)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Credential rotation scheduler stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                warning = self._manager.check_rotation_warning()
                if warning:
                    logger.warning(warning)
                    self._callback(warning)
            except Exception as exc:
                logger.error("Rotation scheduler check failed: %s", exc)
            self._stop_event.wait(timeout=self._interval)

    def check_now(self) -> Optional[str]:
        """Immediate one-shot check (useful for startup). Returns warning or None."""
        return self._manager.check_rotation_warning()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_credentials() -> Optional[Tuple[str, str]]:
    """
    Get API credentials with priority:
    1. Encrypted vault
    2. Environment variables (CI/CD)
    3. Auto-migrate from plaintext (last resort)

    Returns (api_key, private_key_b64) or None.
    """
    manager = SecureCredentialManager()

    if manager.has_encrypted_credentials():
        return manager.decrypt_credentials()

    env_key = os.environ.get("POWERTRADER_ROBINHOOD_API_KEY")
    env_secret = os.environ.get("POWERTRADER_ROBINHOOD_PRIVATE_KEY")
    if env_key and env_secret:
        return env_key.strip(), env_secret.strip()

    if manager.has_plaintext_credentials():
        if manager.migrate_from_plaintext():
            return manager.decrypt_credentials()

    return None


def validate_credentials_on_startup(
    permission_fetcher: Optional[Callable[[], List[str]]] = None,
    require_trading: bool = True,
    notify_rotation: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """
    Convenience function for startup validation.
    Checks permissions AND rotation status.

    Args:
        permission_fetcher: Callable → list of permission strings from exchange
        require_trading: Whether to require buy/sell permissions
        notify_rotation: Callback for rotation warnings (e.g. GUI alert)

    Returns:
        (ok: bool, message: str)
    """
    manager = SecureCredentialManager()
    validator = PermissionValidator()
    messages = []

    # Rotation check
    warning = manager.check_rotation_warning()
    if warning:
        messages.append(warning)
        if notify_rotation:
            notify_rotation(warning)

    # Permission check
    audit = validator.validate(permission_fetcher, require_trading)
    messages.append(audit.message)

    all_ok = audit.audit_passed and not manager._load_metadata().__class__ is None
    return audit.audit_passed, " | ".join(messages)
