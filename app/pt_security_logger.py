"""
PowerTraderAI+ Security & Audit Logging
Extends pt_logging_system with:
- Correlation ID context (thread-local, propagated through request chains)
- Security event logging: API auth attempts, credential usage, suspicious activity
- Dedicated audit log (separate file, rotation, secure permissions)
- Structured JSON security events for SIEM integration

Usage:
    from pt_security_logger import security_logger, correlation_context

    # Propagate correlation ID through a trading workflow
    with correlation_context("trade-abc-123"):
        security_logger.log_auth_attempt("robinhood", success=True)
        security_logger.log_trade_event("BTC-USD", "buy", 0.1, 45000.0)

    # Standalone
    security_logger.log_suspicious_activity(
        "rate_limit_exceeded", source_ip="10.0.0.1", details={"endpoint": "/orders"}
    )
"""

import json
import logging
import logging.handlers
import os
import stat
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security event types
# ---------------------------------------------------------------------------
class SecurityEventType(Enum):
    AUTH_ATTEMPT = "auth_attempt"           # API key authentication attempt
    AUTH_SUCCESS = "auth_success"           # Successful authentication
    AUTH_FAILURE = "auth_failure"           # Failed authentication
    CREDENTIAL_USE = "credential_use"       # Credential accessed/used
    CREDENTIAL_ROTATION = "credential_rotation"  # Credential rotated
    SUSPICIOUS_ACTIVITY = "suspicious_activity"  # Anomalous behavior detected
    PERMISSION_DENIED = "permission_denied" # Insufficient API permissions
    RATE_LIMIT = "rate_limit"               # Rate limit hit
    TRADE_EXECUTED = "trade_executed"       # Order placed
    TRADE_REJECTED = "trade_rejected"       # Order rejected
    CONFIG_CHANGE = "config_change"         # Configuration modified
    SYSTEM_START = "system_start"           # Application started
    SYSTEM_STOP = "system_stop"             # Application stopped


@dataclass
class SecurityEvent:
    """Structured security event for audit trail."""
    event_id: str
    event_type: str
    timestamp: float
    message: str
    correlation_id: Optional[str]
    source: Optional[str] = None
    user_id: Optional[str] = None
    source_ip: Optional[str] = None
    success: Optional[bool] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @staticmethod
    def new_id() -> str:
        return f"SEC_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Correlation ID context (thread-local)
# ---------------------------------------------------------------------------
_correlation_local = threading.local()


def get_correlation_id() -> Optional[str]:
    """Return the current thread's correlation ID, or None if not set."""
    return getattr(_correlation_local, "correlation_id", None)


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current thread."""
    _correlation_local.correlation_id = cid


def clear_correlation_id() -> None:
    """Clear the correlation ID for the current thread."""
    _correlation_local.correlation_id = None


class correlation_context:
    """
    Context manager that sets a correlation ID for the current thread,
    then restores the previous value on exit.

    Usage:
        with correlation_context("trade-workflow-xyz"):
            process_order()  # all logs within will carry this correlation ID
    """

    def __init__(self, correlation_id: Optional[str] = None):
        self._cid = correlation_id or f"CID_{uuid.uuid4().hex[:12]}"
        self._previous: Optional[str] = None

    def __enter__(self) -> str:
        self._previous = get_correlation_id()
        set_correlation_id(self._cid)
        return self._cid

    def __exit__(self, *_) -> None:
        if self._previous is not None:
            set_correlation_id(self._previous)
        else:
            clear_correlation_id()


# ---------------------------------------------------------------------------
# CorrelationLogFilter — injects correlation_id into log records
# ---------------------------------------------------------------------------
class CorrelationLogFilter(logging.Filter):
    """
    Logging filter that injects the current thread's correlation ID
    into every LogRecord. Works with any handler/formatter.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or ""
        return True


# ---------------------------------------------------------------------------
# SecurityLogger
# ---------------------------------------------------------------------------
class SecurityLogger:
    """
    Application-wide security and audit logger.

    Writes structured JSON security events to a dedicated audit log file
    (separate from the main application log). The audit log uses a
    RotatingFileHandler with secure (owner-only) file permissions.
    """

    AUDIT_LOG_FILENAME = "security_audit.jsonl"
    MAX_BYTES = 10 * 1024 * 1024    # 10 MB per file
    BACKUP_COUNT = 10               # Keep 10 rotated files

    def __init__(self, log_dir: Optional[str] = None):
        self._log_dir = log_dir or os.path.dirname(os.path.abspath(__file__))
        self._audit_path = os.path.join(self._log_dir, self.AUDIT_LOG_FILENAME)
        self._lock = threading.Lock()
        self._handler: Optional[logging.handlers.RotatingFileHandler] = None
        self._logger = self._setup_audit_logger()

    def _setup_audit_logger(self) -> logging.Logger:
        """Configure dedicated audit logger with rotation and secure permissions."""
        import hashlib
        path_hash = hashlib.md5(self._audit_path.encode()).hexdigest()[:8]
        audit_logger = logging.getLogger(f"pt.security.audit.{path_hash}")
        audit_logger.setLevel(logging.DEBUG)
        audit_logger.propagate = False  # Don't propagate to root logger

        if not audit_logger.handlers:
            handler = logging.handlers.RotatingFileHandler(
                self._audit_path,
                maxBytes=self.MAX_BYTES,
                backupCount=self.BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))  # Raw JSON
            handler.addFilter(CorrelationLogFilter())
            audit_logger.addHandler(handler)
            self._handler = handler
            self._secure_audit_file()

        return audit_logger

    def _secure_audit_file(self) -> None:
        """Set owner-only permissions on audit log file."""
        try:
            if os.path.exists(self._audit_path):
                os.chmod(self._audit_path, stat.S_IRUSR | stat.S_IWUSR)
        except (OSError, AttributeError):
            pass

    def _emit(self, event: SecurityEvent) -> None:
        """Write security event to audit log (thread-safe)."""
        with self._lock:
            try:
                self._logger.info(event.to_json())
                self._secure_audit_file()
            except Exception as exc:
                logger.error("Failed to write security audit event: %s", exc)

    def _make_event(
        self,
        event_type: SecurityEventType,
        message: str,
        source: Optional[str] = None,
        success: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> SecurityEvent:
        return SecurityEvent(
            event_id=SecurityEvent.new_id(),
            event_type=event_type.value,
            timestamp=time.time(),
            message=message,
            correlation_id=get_correlation_id(),
            source=source,
            success=success,
            details=details,
            source_ip=source_ip,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------
    def log_auth_attempt(
        self,
        api_name: str,
        success: bool,
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an API authentication attempt (success or failure)."""
        event_type = SecurityEventType.AUTH_SUCCESS if success else SecurityEventType.AUTH_FAILURE
        msg = f"API auth {'succeeded' if success else 'FAILED'} for {api_name}"
        if not success:
            logger.warning("SECURITY: %s", msg)
        event = self._make_event(event_type, msg, source=api_name,
                                 success=success, details=details,
                                 source_ip=source_ip, user_id=user_id)
        self._emit(event)

    def log_credential_use(
        self,
        api_name: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log that credentials were accessed/used for an operation."""
        msg = f"Credential used: {api_name} for {operation}"
        event = self._make_event(
            SecurityEventType.CREDENTIAL_USE, msg,
            source=api_name, success=True,
            details={**(details or {}), "operation": operation},
        )
        self._emit(event)

    def log_credential_rotation(
        self,
        api_name: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a credential rotation event."""
        msg = f"Credential rotation {'succeeded' if success else 'FAILED'} for {api_name}"
        if not success:
            logger.critical("SECURITY: %s", msg)
        event = self._make_event(
            SecurityEventType.CREDENTIAL_ROTATION, msg,
            source=api_name, success=success, details=details,
        )
        self._emit(event)

    def log_suspicious_activity(
        self,
        activity_type: str,
        source_ip: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log detected suspicious activity."""
        msg = f"Suspicious activity detected: {activity_type}"
        logger.warning("SECURITY ALERT: %s", msg)
        event = self._make_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY, msg,
            source=activity_type, success=False,
            source_ip=source_ip, user_id=user_id, details=details,
        )
        self._emit(event)

    def log_permission_denied(
        self,
        api_name: str,
        required_permission: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an API permission denial."""
        msg = f"Permission denied: {required_permission} on {api_name}"
        logger.error("SECURITY: %s", msg)
        event = self._make_event(
            SecurityEventType.PERMISSION_DENIED, msg,
            source=api_name, success=False,
            details={**(details or {}), "required_permission": required_permission},
        )
        self._emit(event)

    def log_trade_event(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        success: bool = True,
        order_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a trade execution event to the audit trail."""
        event_type = SecurityEventType.TRADE_EXECUTED if success else SecurityEventType.TRADE_REJECTED
        msg = f"Trade {'executed' if success else 'REJECTED'}: {side} {quantity} {symbol} @ {price}"
        event = self._make_event(
            event_type, msg, success=success,
            details={
                "symbol": symbol, "side": side,
                "quantity": quantity, "price": price,
                "order_id": order_id, **(details or {}),
            },
        )
        self._emit(event)

    def log_system_event(
        self, event_type: SecurityEventType, message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a system lifecycle event (start, stop, config change)."""
        event = self._make_event(event_type, message, details=details)
        self._emit(event)

    def get_recent_events(self, limit: int = 100) -> list:
        """Read the last `limit` events from the audit log."""
        if not os.path.exists(self._audit_path):
            return []
        try:
            with open(self._audit_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            events = []
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return events
        except OSError:
            return []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
security_logger = SecurityLogger()
