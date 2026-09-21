"""SERA 2.0 — Master System Launcher (sera.py)

Orchestrates the complete SERA desktop operating system:
1. Starts the SERA Python Runtime & EventBus Server (app/ui/server.py).
2. Verifies port 8765 and performs a real WebSocket handshake to ws://127.0.0.1:8765.
3. Starts the Native Electron Primary Presence overlay.
4. Manages lifecycle with graceful teardown of all child processes on exit.

Author: Keshava Pandi A S <keshavapandi@gmail.com>
"""

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Root paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(PROJECT_ROOT, "app", "ui", "server.py")
PRESENCE_DIR = os.path.join(PROJECT_ROOT, "presence_desktop")
ELECTRON_EXE = os.path.join(PRESENCE_DIR, "node_modules", "electron", "dist", "electron.exe")

HOST = "127.0.0.1"
PORT = 8765
HTTP_HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
WS_URL = f"ws://{HOST}:{PORT}"

# Global process tracking for graceful teardown
CHILD_PROCESSES: list[subprocess.Popen] = []
IS_SHUTTING_DOWN = False


def log(msg: str):
    print(f"[SERA Launcher] {msg}", flush=True)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently open."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def verify_http_endpoint(url: str, timeout: float = 10.0) -> bool:
    """Poll HTTP health endpoint until responsive or timeout expires."""
    deadline = time.time() + timeout
    log(f"Verifying HTTP health endpoint at {url}...")
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SERALauncher/2.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status in (200, 404):
                    log(f"HTTP health check PASSED (Status: {resp.status})")
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, socket.timeout):
            time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    log("HTTP health check FAILED: Timeout reached")
    return False


async def _async_verify_ws(url: str, timeout: float = 5.0) -> bool:
    """Perform real WebSocket handshake using websockets library."""
    try:
        import websockets
        async with websockets.connect(url, open_timeout=timeout) as ws:
            log("WebSocket handshake PASSED (ws connection established)")
            return True
    except ImportError:
        # Fallback to raw socket RFC 6455 handshake
        return _raw_ws_handshake(HOST, PORT, timeout)
    except Exception as e:
        log(f"WebSocket handshake FAILED: {e}")
        return False


def _raw_ws_handshake(host: str, port: int, timeout: float = 5.0) -> bool:
    """Fallback manual HTTP-to-WebSocket upgrade handshake."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            handshake = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            s.sendall(handshake.encode("ascii"))
            resp = s.recv(1024).decode("utf-8", errors="ignore")
            if "101 Switching Protocols" in resp or "Sec-WebSocket-Accept" in resp:
                log("Raw WebSocket handshake PASSED (101 Switching Protocols)")
                return True
            log(f"Raw WebSocket handshake response unexpected:\n{resp[:200]}")
            return False
    except Exception as e:
        log(f"Raw WebSocket handshake FAILED: {e}")
        return False


def verify_websocket_endpoint(url: str, timeout: float = 5.0) -> bool:
    """Verify that the actual WebSocket endpoint is fully open and accepts handshakes."""
    log(f"Verifying WebSocket endpoint at {url}...")
    try:
        return asyncio.run(_async_verify_ws(url, timeout=timeout))
    except Exception as e:
        log(f"WebSocket verification error: {e}")
        return False


def shutdown_handler(sig=None, frame=None):
    """Gracefully terminate all spawned child processes."""
    global IS_SHUTTING_DOWN
    if IS_SHUTTING_DOWN:
        return
    IS_SHUTTING_DOWN = True

    print("\n" + "=" * 60, flush=True)
    log("Initiating graceful shutdown of all SERA child processes...")

    for proc in reversed(CHILD_PROCESSES):
        if proc.poll() is None:
            try:
                log(f"Terminating PID {proc.pid}...")
                proc.terminate()
            except Exception as e:
                log(f"Error terminating PID {proc.pid}: {e}")

    # Wait for clean exit
    deadline = time.time() + 2.5
    for proc in CHILD_PROCESSES:
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.1)
        if proc.poll() is None:
            try:
                log(f"Force-killing stubborn PID {proc.pid}...")
                proc.kill()
            except Exception:
                pass

    log("All child processes terminated cleanly. SERA shutdown complete.")
    print("=" * 60, flush=True)


def get_python_executable() -> str:
    """Find the working Python interpreter that has the project dependencies installed."""
    candidates = [
        # 1. Current sys.executable if it can import dependencies
        sys.executable,
        # 2. Python 3.14 main installation with dependencies
        r"C:\Users\kesha\AppData\Local\Programs\Python\Python314\python.exe",
        # 3. Windows Python launcher
        "py",
        # 4. Project virtual environment (.venv)
        os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
    ]
    for cand in candidates:
        if not cand:
            continue
        try:
            cmd = [cand, "-c", "import numpy; import sounddevice"]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            if res.returncode == 0:
                return cand
        except Exception:
            continue
    return sys.executable


def start_runtime_server() -> subprocess.Popen | None:
    """Start Python backend runtime if not already active."""
    if is_port_in_use(PORT, HOST):
        log(f"Detected existing service on port {PORT}. Checking health...")
        if verify_http_endpoint(HTTP_HEALTH_URL, timeout=2.0):
            log(f"Existing SERA runtime is active and healthy on port {PORT}.")
            return None
        log(f"Port {PORT} in use but unresponsive. Please free port {PORT} and retry.")
        return None

    python_bin = get_python_executable()
    log(f"Starting SERA Runtime Server using {python_bin} ({SERVER_SCRIPT})...")
    env = os.environ.copy()
    proc = subprocess.Popen(
        [python_bin, SERVER_SCRIPT],
        cwd=PROJECT_ROOT,
        env=env,
    )
    CHILD_PROCESSES.append(proc)
    log(f"Runtime Server started with PID {proc.pid}")
    return proc


def launch_presence_overlay(snapshot_mode: bool = False, voice_snapshot: bool = False) -> subprocess.Popen | None:
    """Start native Electron Primary Presence overlay."""
    if not os.path.exists(ELECTRON_EXE):
        log(f"ERROR: Electron executable not found at: {ELECTRON_EXE}")
        log("Run 'cd presence_desktop && npm install' to install dependencies.")
        return None

    log(f"Starting Primary Presence Overlay ({ELECTRON_EXE})...")
    args = [ELECTRON_EXE, "."]
    if voice_snapshot:
        args.append("--snapshot-voice")
    elif snapshot_mode:
        args.append("--snapshot")

    proc = subprocess.Popen(
        args,
        cwd=PRESENCE_DIR,
    )
    CHILD_PROCESSES.append(proc)
    log(f"Presence Overlay started with PID {proc.pid}")
    return proc


def main():
    # Register signal handlers for clean SIGINT / SIGTERM teardown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    voice_snapshot = "--snapshot-voice" in sys.argv
    snapshot_mode = ("--snapshot" in sys.argv) or ("--verify" in sys.argv)
    verify_only = snapshot_mode or voice_snapshot
    headless = "--headless" in sys.argv

    print("=" * 60)
    print("  SERA 2.0 — MASTER SYSTEM LAUNCHER")
    print("  Creator / Author: Keshava Pandi A S <keshavapandi@gmail.com>")
    print("  Surface: Native Windows Transparent Presence + Command Center")
    print("=" * 60)

    # 1. Start Runtime Server
    server_proc = start_runtime_server()

    # 2. Verify HTTP port 8765
    http_ok = verify_http_endpoint(HTTP_HEALTH_URL, timeout=30.0)
    if not http_ok:
        log("FATAL: SERA Runtime Server failed to respond on HTTP health check.")
        shutdown_handler()
        sys.exit(1)

    # 3. Verify real WebSocket connection
    ws_ok = verify_websocket_endpoint(WS_URL, timeout=6.0)
    if not ws_ok:
        log("FATAL: WebSocket endpoint verification failed. Cannot claim PASS.")
        shutdown_handler()
        sys.exit(1)

    log("Core Runtime & WebSocket Bridge verified operational!")

    if headless:
        log("Headless mode requested. Server running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            shutdown_handler()
        return

    # 4. Start Presence Overlay
    presence_proc = launch_presence_overlay(snapshot_mode=verify_only, voice_snapshot=voice_snapshot)
    if not presence_proc:
        log("FATAL: Failed to launch Presence Overlay.")
        shutdown_handler()
        sys.exit(1)

    if verify_only:
        log("Verification mode active. Waiting for presence snapshot sequence...")
        exit_code = presence_proc.wait(timeout=12.0)
        log(f"Presence verification finished with exit code {exit_code}")
        shutdown_handler()
        if exit_code == 0:
            log("ALL PHASE 2D SYSTEM VERIFICATION CHECKS PASSED.")
            sys.exit(0)
        else:
            log("Verification check failed.")
            sys.exit(1)

    # 5. Normal Interactive Loop
    log("SERA 2.0 is running live! Press Ctrl+Space on your desktop to summon.")
    log("Press Ctrl+C in this terminal (or close the Presence window) to exit.")

    try:
        # Supervise child processes
        while True:
            time.sleep(0.5)
            # If presence window was closed by user
            if presence_proc.poll() is not None:
                log(f"Presence Overlay window closed (code {presence_proc.poll()}).")
                break
            # If backend server died unexpectedly
            if server_proc and server_proc.poll() is not None:
                log(f"WARNING: Backend server exited unexpectedly (code {server_proc.poll()}).")
                break
    except KeyboardInterrupt:
        log("Keyboard interrupt received.")
    finally:
        shutdown_handler()


if __name__ == "__main__":
    main()
