"""Subprocess lifecycle management for trainer/thinker/trader processes."""

from __future__ import annotations

import glob
import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from powertrader.hub.utils import safe_read_json

logger = logging.getLogger(__name__)


@dataclass
class ProcInfo:
    name: str
    path: str
    proc: Optional[subprocess.Popen] = None


@dataclass
class LogProc:
    """A running process with a live log queue for stdout/stderr lines."""
    info: ProcInfo
    log_q: "queue.Queue[str]"
    thread: Optional[threading.Thread] = None
    is_trainer: bool = False
    coin: Optional[str] = None


class ProcessManager:
    """Manages subprocess lifecycle for trainer/thinker/trader."""

    def __init__(
        self,
        project_dir: str,
        hub_dir: str,
        settings: dict,
        coin_folders: Dict[str, str],
        coins: List[str],
        on_error: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.project_dir = project_dir
        self.hub_dir = hub_dir
        self.settings = settings
        self.coin_folders = coin_folders
        self.coins = coins
        self._on_error = on_error  # callback(title, message) for GUI error display

        self.runner_ready_path = os.path.join(hub_dir, "runner_ready.json")

        self.proc_neural = ProcInfo(
            name="Neural Runner",
            path=os.path.abspath(os.path.join(project_dir, settings["script_neural_runner2"])),
        )
        self.proc_trader = ProcInfo(
            name="Trader",
            path=os.path.abspath(os.path.join(project_dir, settings["script_trader"])),
        )
        self.proc_trainer_path = os.path.abspath(
            os.path.join(project_dir, settings["script_neural_trainer"])
        )

        self.runner_log_q: queue.Queue[str] = queue.Queue()
        self.trader_log_q: queue.Queue[str] = queue.Queue()
        self.trainers: Dict[str, LogProc] = {}

        self._auto_start_trader_pending = False

    def _show_error(self, title: str, msg: str) -> None:
        if self._on_error:
            self._on_error(title, msg)

    # ---- low-level process control ----

    @staticmethod
    def _reader_thread(proc: subprocess.Popen, q: queue.Queue[str], prefix: str) -> None:
        try:
            while True:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue
                q.put(f"{prefix}{line.rstrip()}")
        except OSError as exc:
            logger.debug("Reader thread I/O error: %s", exc)
        finally:
            q.put(f"{prefix}[process exited]")

    def _start_process(
        self,
        p: ProcInfo,
        log_q: Optional[queue.Queue[str]] = None,
        prefix: str = "",
    ) -> None:
        if p.proc and p.proc.poll() is None:
            return
        if not os.path.isfile(p.path):
            self._show_error("Missing script", f"Cannot find: {p.path}")
            return

        env = os.environ.copy()
        env["POWERTRADER_HUB_DIR"] = self.hub_dir

        try:
            p.proc = subprocess.Popen(
                [sys.executable, "-u", p.path],
                cwd=self.project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if log_q is not None:
                t = threading.Thread(
                    target=self._reader_thread, args=(p.proc, log_q, prefix), daemon=True
                )
                t.start()
        except OSError as exc:
            logger.error("Failed to start %s: %s", p.name, exc)
            self._show_error("Failed to start", f"{p.name} failed to start:\n{exc}")

    @staticmethod
    def _stop_process(p: ProcInfo) -> None:
        if not p.proc or p.proc.poll() is not None:
            return
        try:
            p.proc.terminate()
        except OSError as exc:
            logger.debug("Failed to terminate %s: %s", p.name, exc)

    # ---- neural / trader ----

    def start_neural(self) -> None:
        try:
            with open(self.runner_ready_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "ready": False, "stage": "starting"}, f)
        except OSError as exc:
            logger.debug("Failed to write runner_ready: %s", exc)
        self._start_process(self.proc_neural, log_q=self.runner_log_q, prefix="[RUNNER] ")

    def start_trader(self) -> None:
        self._start_process(self.proc_trader, log_q=self.trader_log_q, prefix="[TRADER] ")

    def stop_neural(self) -> None:
        self._stop_process(self.proc_neural)

    def stop_trader(self) -> None:
        self._stop_process(self.proc_trader)

    def is_neural_running(self) -> bool:
        return bool(self.proc_neural.proc and self.proc_neural.proc.poll() is None)

    def is_trader_running(self) -> bool:
        return bool(self.proc_trader.proc and self.proc_trader.proc.poll() is None)

    def toggle_all_scripts(self, after_cb: Optional[Callable[[int, Callable], None]] = None) -> None:
        """Toggle start/stop. after_cb is tk.after-like scheduler for polling."""
        if self.is_neural_running() or self.is_trader_running() or self._auto_start_trader_pending:
            self.stop_all_scripts()
            return
        self.start_all_scripts(after_cb=after_cb)

    def start_all_scripts(self, after_cb: Optional[Callable[[int, Callable], None]] = None) -> None:
        all_trained = all(self.coin_is_trained(c) for c in self.coins) if self.coins else False
        if not all_trained:
            self._show_error(
                "Training required",
                "All coins must be trained before starting Neural Runner.\n\nUse Train All first.",
            )
            return

        self._auto_start_trader_pending = True
        self.start_neural()

        if after_cb:
            after_cb(250, lambda: self._poll_runner_ready_then_start_trader(after_cb))

    def stop_all_scripts(self) -> None:
        self._auto_start_trader_pending = False
        self.stop_neural()
        self.stop_trader()
        try:
            with open(self.runner_ready_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "ready": False, "stage": "stopped"}, f)
        except OSError as exc:
            logger.debug("Failed to write runner_ready on stop: %s", exc)

    # ---- runner readiness gate ----

    def read_runner_ready(self) -> Dict[str, Any]:
        try:
            if os.path.isfile(self.runner_ready_path):
                with open(self.runner_ready_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("read_runner_ready failed: %s", exc)
        return {"ready": False}

    def _poll_runner_ready_then_start_trader(
        self, after_cb: Optional[Callable[[int, Callable], None]] = None,
    ) -> None:
        if not self._auto_start_trader_pending:
            return
        if not self.is_neural_running():
            self._auto_start_trader_pending = False
            return

        st = self.read_runner_ready()
        if bool(st.get("ready", False)):
            self._auto_start_trader_pending = False
            if not self.is_trader_running():
                self.start_trader()
            return

        if after_cb:
            try:
                after_cb(250, lambda: self._poll_runner_ready_then_start_trader(after_cb))
            except (RuntimeError, ValueError, TypeError) as exc:
                logger.debug("Polling schedule failed: %s", exc)

    # ---- training ----

    def coin_is_trained(self, coin: str) -> bool:
        coin = coin.upper().strip()
        folder = self.coin_folders.get(coin, "")
        if not folder or not os.path.isdir(folder):
            return False

        try:
            st = safe_read_json(os.path.join(folder, "trainer_status.json"))
            if isinstance(st, dict):
                state = str(st.get("state", "")).upper()
                if state in ("TRAINING", "INTERRUPTED"):
                    return False
        except (OSError, ValueError):
            pass

        stamp_path = os.path.join(folder, "trainer_last_training_time.txt")
        try:
            if not os.path.isfile(stamp_path):
                return False
            with open(stamp_path, "r", encoding="utf-8") as f:
                raw = (f.read() or "").strip()
            ts = float(raw) if raw else 0.0
            if ts <= 0:
                return False
            return (time.time() - ts) <= (14 * 24 * 60 * 60)
        except (OSError, ValueError) as exc:
            logger.debug("coin_is_trained(%s) check failed: %s", coin, exc)
            return False

    def running_trainers(self) -> List[str]:
        running: List[str] = []
        for c, lp in self.trainers.items():
            try:
                if lp.info.proc and lp.info.proc.poll() is None:
                    running.append(c)
            except OSError:
                pass

        for c in self.coins:
            try:
                coin = (c or "").strip().upper()
                folder = self.coin_folders.get(coin, "")
                if not folder or not os.path.isdir(folder):
                    continue
                status_path = os.path.join(folder, "trainer_status.json")
                st = safe_read_json(status_path)
                if isinstance(st, dict) and str(st.get("state", "")).upper() == "TRAINING":
                    stamp_path = os.path.join(folder, "trainer_last_training_time.txt")
                    try:
                        if os.path.isfile(stamp_path) and os.path.isfile(status_path):
                            if os.path.getmtime(stamp_path) >= os.path.getmtime(status_path):
                                continue
                    except OSError:
                        pass
                    running.append(coin)
            except (OSError, ValueError) as exc:
                logger.debug("running_trainers check for %s failed: %s", c, exc)

        out: List[str] = []
        seen: set = set()
        for c in running:
            cc = (c or "").strip().upper()
            if cc and cc not in seen:
                seen.add(cc)
                out.append(cc)
        return out

    def coin_has_checkpoint(self, coin: str) -> bool:
        coin = coin.upper().strip()
        folder = self.coin_folders.get(coin, "")
        if not folder:
            return False
        try:
            return os.path.isfile(os.path.join(folder, "trainer_checkpoint.json"))
        except OSError:
            return False

    def training_status_map(self) -> Dict[str, str]:
        running = set(self.running_trainers())
        out: Dict[str, str] = {}
        for c in self.coins:
            if c in running:
                out[c] = "TRAINING"
            elif self.coin_is_trained(c):
                out[c] = "TRAINED"
            elif self.coin_has_checkpoint(c):
                out[c] = "INTERRUPTED"
            else:
                out[c] = "NOT TRAINED"
        return out

    def start_trainer_for_coin(
        self,
        coin: str,
        force_retrain: bool = False,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        coin = coin.upper().strip()
        if not coin:
            return

        self.stop_neural()

        coin_cwd = self.coin_folders.get(coin, self.project_dir)
        trainer_name = os.path.basename(
            str(self.settings.get("script_neural_trainer", "pt_trainer.py"))
        )

        if coin != "BTC":
            try:
                if not os.path.isdir(coin_cwd):
                    os.makedirs(coin_cwd, exist_ok=True)
                src_main_folder = self.coin_folders.get("BTC", self.project_dir)
                src_trainer_path = os.path.join(src_main_folder, trainer_name)
                dst_trainer_path = os.path.join(coin_cwd, trainer_name)
                if os.path.isfile(src_trainer_path):
                    shutil.copy2(src_trainer_path, dst_trainer_path)
            except OSError as exc:
                logger.warning("Failed to copy trainer for %s: %s", coin, exc)

        trainer_path = os.path.join(coin_cwd, trainer_name)
        if not os.path.isfile(trainer_path):
            self._show_error("Missing trainer", f"Cannot find trainer for {coin} at:\n{trainer_path}")
            return

        if coin in self.trainers and self.trainers[coin].info.proc and self.trainers[coin].info.proc.poll() is None:
            return

        if force_retrain:
            try:
                patterns = [
                    "trainer_last_training_time.txt",
                    "trainer_status.json",
                    "trainer_last_start_time.txt",
                    "trainer_checkpoint.json",
                    "trainer_progress.json",
                    "killer.txt",
                    "memories_*.txt",
                    "memory_weights_*.txt",
                    "neural_perfect_threshold_*.txt",
                ]
                deleted = 0
                for pat in patterns:
                    for fp in glob.glob(os.path.join(coin_cwd, pat)):
                        try:
                            os.remove(fp)
                            deleted += 1
                        except OSError as exc:
                            logger.debug("Failed to remove %s: %s", fp, exc)
                if deleted and on_status:
                    on_status(f"Deleted {deleted} training file(s) for {coin} (force retrain)")
            except OSError as exc:
                logger.warning("Force retrain cleanup failed for %s: %s", coin, exc)
        else:
            for fname in ["killer.txt", "trainer_status.json"]:
                try:
                    fp = os.path.join(coin_cwd, fname)
                    if os.path.isfile(fp):
                        os.remove(fp)
                except OSError as exc:
                    logger.debug("Failed to remove %s: %s", fp, exc)

        q: queue.Queue[str] = queue.Queue()
        info = ProcInfo(name=f"Trainer-{coin}", path=trainer_path)

        env = os.environ.copy()
        env["POWERTRADER_HUB_DIR"] = self.hub_dir

        try:
            info.proc = subprocess.Popen(
                [sys.executable, "-u", info.path, coin],
                cwd=coin_cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            t = threading.Thread(
                target=self._reader_thread, args=(info.proc, q, f"[{coin}] "), daemon=True
            )
            t.start()
            self.trainers[coin] = LogProc(info=info, log_q=q, thread=t, is_trainer=True, coin=coin)
        except OSError as exc:
            logger.error("Failed to start trainer for %s: %s", coin, exc)
            self._show_error("Failed to start", f"Trainer for {coin} failed to start:\n{exc}")

    def stop_trainer_for_coin(self, coin: str) -> None:
        coin = coin.upper().strip()
        lp = self.trainers.get(coin)
        if not lp or not lp.info.proc or lp.info.proc.poll() is not None:
            return
        try:
            lp.info.proc.terminate()
        except OSError as exc:
            logger.debug("Failed to terminate trainer for %s: %s", coin, exc)
