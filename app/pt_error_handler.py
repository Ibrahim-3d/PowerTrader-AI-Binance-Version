"""
PowerTraderAI+ Centralized Error Management System
Single application-wide error handler with notification routing and
classification. All modules should use `get_handler()` instead of
creating their own ErrorHandler instances.

Usage:
    from pt_error_handler import get_handler, on_critical, handle

    # Register a GUI alert callback for critical errors
    on_critical(lambda report: show_alert(report.user_message))

    # Handle an exception anywhere in the codebase
    try:
        risky_operation()
    except Exception as exc:
        handle(exc, context={"operation": "risky_operation"})

    # Or via the global handler directly
    handler = get_handler()
    handler.handle_error(exc)
"""

import logging
import threading
from typing import Callable, Dict, List, Optional

from pt_errors import (
    ErrorCategory,
    ErrorHandler,
    ErrorReport,
    ErrorSeverity,
    PowerTraderError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Notification callback type alias
# ---------------------------------------------------------------------------
NotificationCallback = Callable[[ErrorReport], None]


# ---------------------------------------------------------------------------
# ApplicationErrorHandler — singleton wrapping ErrorHandler
# ---------------------------------------------------------------------------
class ApplicationErrorHandler:
    """
    Application-wide singleton error handler.

    Wraps pt_errors.ErrorHandler and adds:
    - Per-severity notification callbacks (e.g. pop GUI alerts for CRITICAL)
    - Global error bus: all modules share one instance
    - Thread-safe callback registration / invocation
    - Error suppression rules for known noisy errors
    """

    _instance: Optional["ApplicationErrorHandler"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ApplicationErrorHandler":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialised = False
            return cls._instance

    def _ensure_init(self) -> None:
        if self._initialised:
            return
        self._handler = ErrorHandler(logger=logging.getLogger("pt.errors"))
        self._callbacks: Dict[ErrorSeverity, List[NotificationCallback]] = {
            sev: [] for sev in ErrorSeverity
        }
        self._suppressed_modules: set = set()
        self._cb_lock = threading.Lock()
        self._initialised = True

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------
    def register_callback(
        self, severity: ErrorSeverity, callback: NotificationCallback
    ) -> None:
        """
        Register a callback fired whenever an error of `severity` is handled.
        Callbacks must be non-blocking (offload heavy work to a thread).
        """
        self._ensure_init()
        with self._cb_lock:
            self._callbacks[severity].append(callback)

    def unregister_all(self, severity: Optional[ErrorSeverity] = None) -> None:
        """Clear callbacks for a severity level (or all levels if None)."""
        self._ensure_init()
        with self._cb_lock:
            if severity:
                self._callbacks[severity].clear()
            else:
                for cbs in self._callbacks.values():
                    cbs.clear()

    # ------------------------------------------------------------------
    # Suppression
    # ------------------------------------------------------------------
    def suppress_module(self, module_name: str) -> None:
        """Suppress notifications for errors originating from `module_name`."""
        self._ensure_init()
        self._suppressed_modules.add(module_name)

    def unsuppress_module(self, module_name: str) -> None:
        self._ensure_init()
        self._suppressed_modules.discard(module_name)

    # ------------------------------------------------------------------
    # Core handle
    # ------------------------------------------------------------------
    def handle(
        self,
        error: Exception,
        context: Optional[Dict] = None,
        reraise: bool = False,
    ) -> ErrorReport:
        """
        Handle an exception: classify, log, fire callbacks.

        Args:
            error: The exception to handle
            context: Additional key/value context for the report
            reraise: If True, re-raise the exception after handling

        Returns:
            ErrorReport with full classification and metadata
        """
        self._ensure_init()
        report = self._handler.handle_error(error, context=context)
        self._fire_callbacks(report)
        if reraise:
            raise error
        return report

    def handle_critical(
        self, error: Exception, context: Optional[Dict] = None
    ) -> ErrorReport:
        """Handle and immediately fire all CRITICAL callbacks."""
        self._ensure_init()
        report = self._handler.handle_error(error, context=context)
        # Force severity to CRITICAL for escalation
        if report.severity != ErrorSeverity.CRITICAL:
            report.severity = ErrorSeverity.CRITICAL
        self._fire_callbacks(report)
        return report

    def _fire_callbacks(self, report: ErrorReport) -> None:
        self._ensure_init()
        if report.module in self._suppressed_modules:
            return
        with self._cb_lock:
            callbacks = list(self._callbacks.get(report.severity, []))
        for cb in callbacks:
            try:
                cb(report)
            except Exception as cb_exc:
                logger.warning("Error callback raised an exception: %s", cb_exc)

    # ------------------------------------------------------------------
    # Query / stats
    # ------------------------------------------------------------------
    def get_summary(self) -> Dict:
        self._ensure_init()
        return self._handler.get_error_summary()

    def get_recent_errors(self, limit: int = 20) -> List[ErrorReport]:
        self._ensure_init()
        return self._handler.error_reports[-limit:]

    def get_critical_errors(self) -> List[ErrorReport]:
        self._ensure_init()
        return [
            r for r in self._handler.error_reports
            if r.severity == ErrorSeverity.CRITICAL
        ]

    def clear_history(self) -> None:
        """Clear in-memory error history (does NOT affect logs)."""
        self._ensure_init()
        self._handler.error_reports.clear()
        self._handler.error_counts.clear()

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset singleton — for testing only."""
        with cls._lock:
            cls._instance = None


# ---------------------------------------------------------------------------
# Module-level convenience API
# ---------------------------------------------------------------------------
def get_handler() -> ApplicationErrorHandler:
    """Return the application-wide singleton error handler."""
    h = ApplicationErrorHandler()
    h._ensure_init()
    return h


def handle(
    error: Exception,
    context: Optional[Dict] = None,
    reraise: bool = False,
) -> ErrorReport:
    """Module-level shortcut: handle(exc) from anywhere."""
    return get_handler().handle(error, context=context, reraise=reraise)


def on_critical(callback: NotificationCallback) -> None:
    """Register a callback that fires on every CRITICAL error."""
    get_handler().register_callback(ErrorSeverity.CRITICAL, callback)


def on_error(callback: NotificationCallback) -> None:
    """Register a callback that fires on HIGH severity errors."""
    get_handler().register_callback(ErrorSeverity.HIGH, callback)


def on_warning(callback: NotificationCallback) -> None:
    """Register a callback that fires on MEDIUM severity errors."""
    get_handler().register_callback(ErrorSeverity.MEDIUM, callback)


def configure_gui_alerts(
    critical_callback: Optional[NotificationCallback] = None,
    error_callback: Optional[NotificationCallback] = None,
) -> None:
    """
    Convenience: register GUI alert callbacks for CRITICAL and HIGH errors.
    Call once during application startup.

    Example:
        configure_gui_alerts(
            critical_callback=lambda r: messagebox.showerror("Critical", r.user_message),
            error_callback=lambda r: messagebox.showwarning("Error", r.user_message),
        )
    """
    handler = get_handler()
    if critical_callback:
        handler.register_callback(ErrorSeverity.CRITICAL, critical_callback)
    if error_callback:
        handler.register_callback(ErrorSeverity.HIGH, error_callback)
