"""
PowerTrader AI+ Process Management
Handles background processes, monitoring, and log streaming
"""

import os
import subprocess
import threading
import time
import queue
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import signal
import sys
import psutil
import weakref
from pathlib import Path


@dataclass
class ProcInfo:
    """Information about a managed process."""

    name: str
    path: str
    args: List[str] = None
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env_vars is None:
            self.env_vars = {}


@dataclass
class ProcessStats:
    """Statistics for a running process."""

    pid: int
    name: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    running_time: float = 0.0
    status: str = "unknown"
    return_code: Optional[int] = None


class LogProc:
    """
    Manages a subprocess with live log streaming to a queue.
    """

    def __init__(
        self, proc_info: ProcInfo, log_queue: queue.Queue, max_log_lines: int = 1000
    ):
        self.proc_info = proc_info
        self.log_queue = log_queue
        self.max_log_lines = max_log_lines

        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._log_buffer: List[str] = []
        self._running = False
        self._lock = threading.RLock()

    def start(self) -> bool:
        """Start the process."""
        with self._lock:
            if self._running:
                return False

            try:
                # Setup environment
                env = os.environ.copy()
                env.update(self.proc_info.env_vars)

                # Determine working directory
                working_dir = self.proc_info.working_dir
                if not working_dir:
                    working_dir = os.path.dirname(self.proc_info.path)

                # Build command
                cmd = [sys.executable, self.proc_info.path] + self.proc_info.args

                # Start process
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=working_dir,
                    env=env,
                    bufsize=1,  # Line buffered
                    universal_newlines=True,
                )

                self.start_time = time.time()
                self._running = True

                # Start log streaming threads
                self._stdout_thread = threading.Thread(
                    target=self._stream_output,
                    args=(self.process.stdout, "STDOUT"),
                    daemon=True,
                )
                self._stderr_thread = threading.Thread(
                    target=self._stream_output,
                    args=(self.process.stderr, "STDERR"),
                    daemon=True,
                )

                self._stdout_thread.start()
                self._stderr_thread.start()

                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitor_process, daemon=True
                )
                self._monitor_thread.start()

                self._log_message(
                    f"Started {self.proc_info.name} (PID: {self.process.pid})"
                )
                return True

            except Exception as e:
                self._log_message(f"Failed to start {self.proc_info.name}: {e}")
                self._cleanup()
                return False

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the process gracefully."""
        with self._lock:
            if not self._running or not self.process:
                return True

            try:
                self._log_message(f"Stopping {self.proc_info.name}...")

                # Try graceful shutdown first
                if sys.platform == "win32":
                    # On Windows, send CTRL_C_EVENT
                    self.process.send_signal(signal.CTRL_C_EVENT)
                else:
                    # On Unix, send SIGTERM
                    self.process.terminate()

                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown failed
                    self._log_message(f"Force killing {self.proc_info.name}...")
                    self.process.kill()
                    self.process.wait()

                self._cleanup()
                self._log_message(f"Stopped {self.proc_info.name}")
                return True

            except Exception as e:
                self._log_message(f"Error stopping {self.proc_info.name}: {e}")
                self._cleanup()
                return False

    def is_running(self) -> bool:
        """Check if the process is running."""
        with self._lock:
            if not self._running or not self.process:
                return False

            return self.process.poll() is None

    def get_stats(self) -> Optional[ProcessStats]:
        """Get process statistics."""
        with self._lock:
            if not self.is_running():
                return None

            try:
                proc = psutil.Process(self.process.pid)
                running_time = time.time() - (self.start_time or time.time())

                return ProcessStats(
                    pid=self.process.pid,
                    name=self.proc_info.name,
                    cpu_percent=proc.cpu_percent(),
                    memory_mb=proc.memory_info().rss / (1024 * 1024),
                    running_time=running_time,
                    status=proc.status(),
                    return_code=self.process.returncode,
                )

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return None

    def get_log_buffer(self) -> List[str]:
        """Get the current log buffer."""
        with self._lock:
            return self._log_buffer.copy()

    def clear_log_buffer(self):
        """Clear the log buffer."""
        with self._lock:
            self._log_buffer.clear()

    def _stream_output(self, stream, stream_name: str):
        """Stream output from subprocess to log queue."""
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break

                line = line.rstrip()
                if line:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    formatted_line = f"[{timestamp}] {line}"

                    # Add to queue
                    try:
                        self.log_queue.put_nowait(formatted_line)
                    except queue.Full:
                        # If queue is full, remove oldest and add new
                        try:
                            self.log_queue.get_nowait()
                            self.log_queue.put_nowait(formatted_line)
                        except queue.Empty:
                            pass

                    # Add to buffer
                    with self._lock:
                        self._log_buffer.append(formatted_line)
                        if len(self._log_buffer) > self.max_log_lines:
                            self._log_buffer = self._log_buffer[-self.max_log_lines :]

        except Exception as e:
            self._log_message(
                f"Error streaming {stream_name} for {self.proc_info.name}: {e}"
            )
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _monitor_process(self):
        """Monitor the process and handle its completion."""
        try:
            if self.process:
                self.process.wait()
                return_code = self.process.returncode

                with self._lock:
                    if self._running:
                        self._log_message(
                            f"{self.proc_info.name} finished with return code {return_code}"
                        )
                        self._cleanup()

        except Exception as e:
            self._log_message(f"Error monitoring {self.proc_info.name}: {e}")

    def _log_message(self, message: str):
        """Log a message to the queue and buffer."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        try:
            self.log_queue.put_nowait(formatted_message)
        except queue.Full:
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(formatted_message)
            except queue.Empty:
                pass

        with self._lock:
            self._log_buffer.append(formatted_message)
            if len(self._log_buffer) > self.max_log_lines:
                self._log_buffer = self._log_buffer[-self.max_log_lines :]

    def _cleanup(self):
        """Clean up process resources."""
        self._running = False

        # Close streams
        if self.process:
            try:
                if self.process.stdout:
                    self.process.stdout.close()
                if self.process.stderr:
                    self.process.stderr.close()
            except Exception:
                pass


class ProcessManager:
    """
    Manages multiple processes with monitoring and log aggregation.
    """

    def __init__(self, max_log_lines_per_process: int = 1000):
        self.processes: Dict[str, LogProc] = {}
        self.log_queues: Dict[str, queue.Queue] = {}
        self.max_log_lines_per_process = max_log_lines_per_process
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable]] = {}

    def register_process(self, process_id: str, proc_info: ProcInfo) -> bool:
        """Register a new process for management."""
        with self._lock:
            if process_id in self.processes:
                return False

            log_queue = queue.Queue(maxsize=1000)
            log_proc = LogProc(proc_info, log_queue, self.max_log_lines_per_process)

            self.processes[process_id] = log_proc
            self.log_queues[process_id] = log_queue

            return True

    def start_process(self, process_id: str) -> bool:
        """Start a registered process."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            if not log_proc:
                return False

            success = log_proc.start()

            # Call callbacks
            for callback in self._callbacks.get(process_id, []):
                try:
                    callback("started" if success else "failed", log_proc)
                except Exception:
                    pass

            return success

    def stop_process(self, process_id: str, timeout: float = 5.0) -> bool:
        """Stop a running process."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            if not log_proc:
                return True

            success = log_proc.stop(timeout)

            # Call callbacks
            for callback in self._callbacks.get(process_id, []):
                try:
                    callback("stopped", log_proc)
                except Exception:
                    pass

            return success

    def restart_process(self, process_id: str, timeout: float = 5.0) -> bool:
        """Restart a process."""
        with self._lock:
            if self.is_process_running(process_id):
                if not self.stop_process(process_id, timeout):
                    return False

            return self.start_process(process_id)

    def is_process_running(self, process_id: str) -> bool:
        """Check if a process is running."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            return log_proc.is_running() if log_proc else False

    def get_process_stats(self, process_id: str) -> Optional[ProcessStats]:
        """Get statistics for a process."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            return log_proc.get_stats() if log_proc else None

    def get_all_stats(self) -> Dict[str, ProcessStats]:
        """Get statistics for all processes."""
        with self._lock:
            stats = {}
            for process_id, log_proc in self.processes.items():
                stat = log_proc.get_stats()
                if stat:
                    stats[process_id] = stat
            return stats

    def get_log_queue(self, process_id: str) -> Optional[queue.Queue]:
        """Get the log queue for a process."""
        return self.log_queues.get(process_id)

    def get_log_buffer(self, process_id: str) -> List[str]:
        """Get the log buffer for a process."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            return log_proc.get_log_buffer() if log_proc else []

    def clear_log_buffer(self, process_id: str):
        """Clear the log buffer for a process."""
        with self._lock:
            log_proc = self.processes.get(process_id)
            if log_proc:
                log_proc.clear_log_buffer()

    def start_all(self) -> Dict[str, bool]:
        """Start all registered processes."""
        results = {}
        for process_id in list(self.processes.keys()):
            results[process_id] = self.start_process(process_id)
        return results

    def stop_all(self, timeout: float = 5.0) -> Dict[str, bool]:
        """Stop all running processes."""
        results = {}
        for process_id in list(self.processes.keys()):
            results[process_id] = self.stop_process(process_id, timeout)
        return results

    def register_callback(
        self, process_id: str, callback: Callable[[str, LogProc], None]
    ):
        """Register a callback for process events."""
        with self._lock:
            if process_id not in self._callbacks:
                self._callbacks[process_id] = []
            self._callbacks[process_id].append(callback)

    def unregister_callback(self, process_id: str, callback: Callable):
        """Unregister a process callback."""
        with self._lock:
            callbacks = self._callbacks.get(process_id, [])
            if callback in callbacks:
                callbacks.remove(callback)

    def unregister_process(self, process_id: str) -> bool:
        """Unregister a process (stops it first if running)."""
        with self._lock:
            if process_id not in self.processes:
                return False

            # Stop the process if running
            self.stop_process(process_id)

            # Remove from tracking
            del self.processes[process_id]
            if process_id in self.log_queues:
                del self.log_queues[process_id]
            if process_id in self._callbacks:
                del self._callbacks[process_id]

            return True

    def cleanup(self):
        """Clean up all processes and resources."""
        self.stop_all(timeout=10.0)

        with self._lock:
            self.processes.clear()
            self.log_queues.clear()
            self._callbacks.clear()


class LogStreamAggregator:
    """
    Aggregates log streams from multiple processes.
    """

    def __init__(self, process_manager: ProcessManager):
        self.process_manager = process_manager
        self._aggregated_logs: Dict[str, List[str]] = {}
        self._running = False
        self._aggregator_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Callable]] = {}

    def start_aggregation(self):
        """Start log aggregation."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._aggregator_thread = threading.Thread(
                target=self._aggregate_logs, daemon=True
            )
            self._aggregator_thread.start()

    def stop_aggregation(self):
        """Stop log aggregation."""
        with self._lock:
            self._running = False

    def subscribe_to_logs(self, process_id: str, callback: Callable[[str], None]):
        """Subscribe to logs from a specific process."""
        with self._lock:
            if process_id not in self._subscribers:
                self._subscribers[process_id] = []
            self._subscribers[process_id].append(callback)

    def unsubscribe_from_logs(self, process_id: str, callback: Callable):
        """Unsubscribe from logs."""
        with self._lock:
            subscribers = self._subscribers.get(process_id, [])
            if callback in subscribers:
                subscribers.remove(callback)

    def get_aggregated_logs(self, process_id: str) -> List[str]:
        """Get aggregated logs for a process."""
        with self._lock:
            return self._aggregated_logs.get(process_id, []).copy()

    def _aggregate_logs(self):
        """Background thread that aggregates logs."""
        while self._running:
            try:
                # Process logs from all queues
                for process_id, log_queue in self.process_manager.log_queues.items():
                    logs_processed = 0

                    while logs_processed < 100:  # Limit per iteration
                        try:
                            log_line = log_queue.get_nowait()

                            # Add to aggregated logs
                            with self._lock:
                                if process_id not in self._aggregated_logs:
                                    self._aggregated_logs[process_id] = []

                                self._aggregated_logs[process_id].append(log_line)

                                # Limit aggregated log size
                                if len(self._aggregated_logs[process_id]) > 1000:
                                    self._aggregated_logs[process_id] = (
                                        self._aggregated_logs[process_id][-1000:]
                                    )

                                # Notify subscribers
                                for callback in self._subscribers.get(process_id, []):
                                    try:
                                        callback(log_line)
                                    except Exception:
                                        pass

                            logs_processed += 1

                        except queue.Empty:
                            break

                # Sleep briefly to avoid busy waiting
                time.sleep(0.1)

            except Exception:
                time.sleep(1.0)  # Back off on errors


# Global process manager instance
_global_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """Get the global process manager instance."""
    global _global_process_manager
    if _global_process_manager is None:
        _global_process_manager = ProcessManager()
    return _global_process_manager


def setup_process_manager() -> ProcessManager:
    """Setup and return the global process manager."""
    global _global_process_manager
    _global_process_manager = ProcessManager()
    return _global_process_manager


if __name__ == "__main__":
    # Example usage
    import tempfile

    # Create a simple test script
    test_script = """
import time
import sys

for i in range(10):
    print(f"Line {i+1} from test script")
    if i % 3 == 0:
        print(f"Error message {i+1}", file=sys.stderr)
    time.sleep(1)

print("Test script completed")
"""

    # Write test script to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_script)
        test_script_path = f.name

    try:
        # Test process management
        proc_manager = ProcessManager()

        # Register test process
        proc_info = ProcInfo(
            name="Test Process",
            path=test_script_path,
            args=[],
            env_vars={"TEST_VAR": "test_value"},
        )

        proc_manager.register_process("test", proc_info)

        # Start log aggregation
        aggregator = LogStreamAggregator(proc_manager)
        aggregator.start_aggregation()

        def log_callback(log_line):
            print(f"Received: {log_line}")

        aggregator.subscribe_to_logs("test", log_callback)

        # Start the process
        print("Starting test process...")
        success = proc_manager.start_process("test")
        print(f"Start success: {success}")

        # Monitor for a while
        start_time = time.time()
        while time.time() - start_time < 15:
            stats = proc_manager.get_process_stats("test")
            if stats:
                print(
                    f"Process stats: PID={stats.pid}, CPU={stats.cpu_percent}%, "
                    f"Memory={stats.memory_mb:.1f}MB, Running={stats.running_time:.1f}s"
                )
            else:
                print("Process not running")
                break

            time.sleep(2)

        # Stop everything
        print("Stopping test process...")
        proc_manager.stop_process("test")
        aggregator.stop_aggregation()

        print("Process management test completed!")

    finally:
        # Clean up test script
        try:
            os.unlink(test_script_path)
        except Exception:
            pass
