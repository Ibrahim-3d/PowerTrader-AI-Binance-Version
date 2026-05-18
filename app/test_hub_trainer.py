#!/usr/bin/env python3
"""
Direct test of the hub's trainer launching logic without GUI
"""

import os
import subprocess
import sys
import time
import threading
import queue
import glob
import shutil
from typing import Optional, Dict, Any


class ProcInfo:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.proc: Optional[subprocess.Popen] = None


def _reader_thread(proc: subprocess.Popen, q: queue.Queue, prefix: str) -> None:
    """Copy of hub's _reader_thread function"""
    try:
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            q.put(f"{prefix}{line.rstrip()}")
            print(f"CAPTURED: {prefix}{line.rstrip()}")
    except Exception as e:
        print(f"READER_THREAD_ERROR: {e}")
    finally:
        q.put(f"{prefix}[process exited]")
        print(f"READER_THREAD: {prefix}[process exited]")


def _monitor_trainer_process(
    coin: str, proc: subprocess.Popen, check_count: int = 0
) -> None:
    """Monitor trainer process like the hub does"""
    try:
        if proc and proc.poll() is not None:
            print(
                f"DEBUG: Trainer process for {coin} exited with code: {proc.returncode}"
            )
            try:
                remaining_output = proc.stdout.read() if proc.stdout else ""
                if remaining_output:
                    print(f"DEBUG: Final output from {coin}: {remaining_output}")
            except:
                pass
            return proc.returncode
        else:
            # Process still running, check again in 2 seconds
            print(
                f"DEBUG: Trainer {coin} still running (PID: {proc.pid if proc else 'None'})"
            )
            time.sleep(2)
            return _monitor_trainer_process(coin, proc, check_count + 1)
    except Exception as e:
        print(f"DEBUG: Error monitoring {coin}: {e}")
        return -1


def test_hub_trainer_launch(coin: str = "XRP") -> int:
    """Test the exact hub trainer launching logic"""
    print(f"Testing hub trainer launch for {coin}")

    # Define paths like the hub does
    app_dir = r"C:\Users\Administrator\PowerTrader\PowerTrader_AI\app"
    project_dir = app_dir
    hub_dir = os.path.join(app_dir, "hub_data")

    # Define coin folders like the hub does
    coin_folders = {
        "BTC": project_dir,  # BTC runs from main folder
        "ETH": os.path.join(project_dir, "ETH"),
        "XRP": os.path.join(project_dir, "XRP"),
        "BNB": os.path.join(project_dir, "BNB"),
        "DOGE": os.path.join(project_dir, "DOGE"),
    }

    coin_cwd = coin_folders.get(coin, project_dir)
    trainer_name = "pt_trainer.py"

    # Create coin folder and copy trainer if needed (like hub does)
    if coin != "BTC":
        try:
            if not os.path.isdir(coin_cwd):
                os.makedirs(coin_cwd, exist_ok=True)

            src_main_folder = coin_folders.get("BTC", project_dir)
            src_trainer_path = os.path.join(src_main_folder, trainer_name)
            dst_trainer_path = os.path.join(coin_cwd, trainer_name)

            if os.path.isfile(src_trainer_path):
                shutil.copy2(src_trainer_path, dst_trainer_path)
        except Exception as e:
            print(f"Warning: Could not prepare coin folder: {e}")

    trainer_path = os.path.join(coin_cwd, trainer_name)
    print(f"DEBUG: Looking for trainer at: {trainer_path}")

    if not os.path.isfile(trainer_path):
        print(f"ERROR: Trainer not found at {trainer_path}")
        return -1

    print(f"DEBUG: Trainer found, proceeding with launch")

    # Clean up training files like the hub does
    try:
        patterns = [
            "trainer_last_training_time.txt",
            "trainer_status.json",
            "trainer_last_start_time.txt",
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
                except Exception:
                    pass

        if deleted:
            print(f"Deleted {deleted} training file(s) for {coin} before training")
    except Exception:
        pass

    # Setup subprocess like the hub does
    q = queue.Queue()
    info = ProcInfo(name=f"Trainer-{coin}", path=trainer_path)

    env = os.environ.copy()
    env["POWERTRADER_HUB_DIR"] = hub_dir

    try:
        cmd_args = [sys.executable, "-u", info.path, coin]
        print(f"DEBUG: Command args: {cmd_args}")
        print(f"DEBUG: Working directory: {coin_cwd}")
        print(
            f"DEBUG: Environment POWERTRADER_HUB_DIR: {env.get('POWERTRADER_HUB_DIR')}"
        )

        info.proc = subprocess.Popen(
            cmd_args,
            cwd=coin_cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        print(f"DEBUG: Process started with PID: {info.proc.pid}")

        # Give it a moment to start and check if it's still running
        time.sleep(0.5)
        if info.proc.poll() is not None:
            print(
                f"DEBUG: Process {info.proc.pid} already terminated with exit code: {info.proc.returncode}"
            )
            try:
                stdout, stderr = info.proc.communicate(timeout=1)
                print(f"DEBUG: Process output: {stdout}")
                if stderr:
                    print(f"DEBUG: Process stderr: {stderr}")
            except:
                pass
            return info.proc.returncode

        print(f"DEBUG: Subprocess launched successfully for {coin}")
        t = threading.Thread(
            target=_reader_thread,
            args=(info.proc, q, f"[{coin}] "),
            daemon=True,
        )
        t.start()

        # Monitor the process like the hub does
        return _monitor_trainer_process(coin, info.proc)

    except Exception as e:
        print(f"DEBUG: ERROR starting trainer for {coin}: {e}")
        return -1


if __name__ == "__main__":
    print("Testing Hub Trainer Launch Logic")
    print("=" * 40)

    exit_code = test_hub_trainer_launch("XRP")

    if exit_code == 0:
        print(f"\n✅ SUCCESS: Hub trainer logic completed with exit code {exit_code}")
    else:
        print(f"\n❌ FAILURE: Hub trainer logic failed with exit code {exit_code}")
