#!/usr/bin/env python3
"""
Test script to simulate exactly how the hub launches trainer subprocesses
to debug the exit code 1 issue.
"""

import os
import subprocess
import sys
import threading
import time
import queue


def _reader_thread(proc: subprocess.Popen, q: queue.Queue, prefix: str) -> None:
    """Simulate the hub's _reader_thread function"""
    try:
        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            q.put(f"{prefix}{line.rstrip()}")
            print(f"CAPTURED: {prefix}{line.rstrip()}")  # Debug: show captured output
    except Exception as e:
        print(f"READER_THREAD_ERROR: {e}")
    finally:
        q.put(f"{prefix}[process exited]")
        print(f"READER_THREAD: {prefix}[process exited]")


def test_subprocess_trainer():
    """Test launching trainer exactly like the hub does"""
    coin = "XRP"
    coin_cwd = r"C:\Users\Administrator\PowerTrader\PowerTrader_AI\app\XRP"
    trainer_path = os.path.join(coin_cwd, "pt_trainer.py")
    hub_dir = r"C:\Users\Administrator\PowerTrader\PowerTrader_AI\app\hub_data"
    
    print(f"Testing subprocess launch for {coin}")
    print(f"Working directory: {coin_cwd}")
    print(f"Trainer path: {trainer_path}")
    
    # Setup environment exactly like the hub
    env = os.environ.copy()
    env["POWERTRADER_HUB_DIR"] = hub_dir
    
    # Setup queue and command args exactly like the hub
    q = queue.Queue()
    cmd_args = [sys.executable, "-u", trainer_path, coin]
    
    print(f"Command args: {cmd_args}")
    print(f"Environment POWERTRADER_HUB_DIR: {env.get('POWERTRADER_HUB_DIR')}")
    
    try:
        # Launch subprocess exactly like the hub
        proc = subprocess.Popen(
            cmd_args,
            cwd=coin_cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        print(f"Process started with PID: {proc.pid}")
        
        # Start reader thread exactly like the hub
        reader_thread = threading.Thread(
            target=_reader_thread,
            args=(proc, q, f"[{coin}] "),
            daemon=True,
        )
        reader_thread.start()
        
        # Monitor the process
        start_time = time.time()
        check_count = 0
        while proc.poll() is None:
            check_count += 1
            elapsed = time.time() - start_time
            print(f"Check #{check_count}: Process still running (PID: {proc.pid}) - Elapsed: {elapsed:.1f}s")
            time.sleep(2)
            
            # Safety timeout after 2 minutes
            if elapsed > 120:
                print("TIMEOUT: Killing process after 2 minutes")
                proc.terminate()
                break
        
        # Process finished
        exit_code = proc.returncode
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\nPROCESS FINISHED:")
        print(f"Exit code: {exit_code}")
        print(f"Total runtime: {total_time:.1f} seconds")
        print(f"Process checks: {check_count}")
        
        # Try to get any remaining output
        try:
            remaining_output = proc.stdout.read() if proc.stdout else ""
            if remaining_output:
                print(f"Final output: {remaining_output}")
        except Exception as e:
            print(f"Error reading final output: {e}")
        
        # Check queue for captured output
        print(f"\nCAPTURED OUTPUT SUMMARY:")
        output_lines = []
        try:
            while True:
                line = q.get_nowait()
                output_lines.append(line)
        except:
            pass
        
        print(f"Total output lines captured: {len(output_lines)}")
        if output_lines:
            print(f"First line: {output_lines[0]}")
            print(f"Last line: {output_lines[-1]}")
        
        return exit_code
        
    except Exception as e:
        print(f"ERROR launching subprocess: {e}")
        return -1


if __name__ == "__main__":
    print("PowerTrader AI Subprocess Trainer Test")
    print("=" * 50)
    
    exit_code = test_subprocess_trainer()
    
    if exit_code == 0:
        print(f"\n✅ SUCCESS: Trainer completed with exit code {exit_code}")
    else:
        print(f"\n❌ FAILURE: Trainer failed with exit code {exit_code}")
