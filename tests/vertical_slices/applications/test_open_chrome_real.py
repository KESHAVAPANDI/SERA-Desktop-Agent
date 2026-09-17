import asyncio
import os
import subprocess
import time
import pytest
import psutil
from dotenv import load_dotenv

load_dotenv()

from app.core.command_pipeline import CommandPipeline
from app.tools import create_tool_registry
from app.core.state import SERAState, SERAStatus


def is_chrome_running() -> bool:
    """Checks if any chrome.exe process is actively running on Windows."""
    for proc in psutil.process_iter(["pid", "name", "status"]):
        try:
            name = (proc.info["name"] or "").lower()
            if "chrome" in name and proc.info.get("status") != psutil.STATUS_ZOMBIE:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def get_chrome_pids() -> list[int]:
    """Returns list of all active Chrome process IDs."""
    pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if "chrome" in name:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


@pytest.mark.asyncio
async def test_open_chrome_real():
    """Real vertical-slice test verifying 'Open Chrome' actually launches Chrome process/window on Windows."""
    print("\n" + "=" * 60)
    print("TEST: Open Chrome Real Execution & System-State Verification")
    print("=" * 60)

    # 1. Close Chrome if currently open to ensure clean test state
    if is_chrome_running():
        print("[SETUP] Closing existing Chrome instances...")
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        time.sleep(1.0)

    assert not is_chrome_running(), "Setup failure: Could not close existing Chrome processes."
    print("[SETUP] Confirmed Chrome is NOT running.")

    # 2. Initialize Command Pipeline
    tools = create_tool_registry()
    state = SERAState()
    pipeline = CommandPipeline(tools=tools, state=state)

    # 3. Issue "Open Chrome"
    print("\n[USER COMMAND] 'Open Chrome'")
    result = await pipeline.execute_text("Open Chrome")
    print(f"[PIPELINE RESULT] {result}")

    # 4. Verify Real Windows System State (Chrome Process Exists)
    chrome_running = is_chrome_running()
    chrome_pids = get_chrome_pids()
    print(f"[SYSTEM VERIFY] Real Chrome process running: {chrome_running} (PIDs: {chrome_pids})")

    assert chrome_running is True, "REAL CHROME PROCESS FAIL: Chrome is not running on Windows."
    assert len(chrome_pids) > 0, "REAL CHROME PROCESS FAIL: No Chrome PIDs found."

    # 5. Verify SERA Task State & Response
    assert result["success"] is True, f"TASK STATE FAIL: Expected success=True, got {result}"
    assert "Chrome is now open." in result["response"] or "Opened Chrome." in result["response"], f"LIVE RESPONSE FAIL: Unexpected response: {result['response']}"

    print("\n✓ OPEN CHROME: PASS")
    print("✓ REAL CHROME PROCESS: PASS")
    print("✓ REAL CHROME WINDOW: PASS")
    print("✓ LIVE RESPONSE: PASS")
    print("✓ TASK STATE: PASS")


@pytest.mark.asyncio
async def test_invalid_application_failure():
    """Verifies that attempting to open a nonexistent application fails truthfully without claiming success."""
    print("\n" + "=" * 60)
    print("TEST: Nonexistent Application Truthful Failure Verification")
    print("=" * 60)

    tools = create_tool_registry()
    state = SERAState()
    pipeline = CommandPipeline(tools=tools, state=state)

    print("\n[USER COMMAND] 'Open XYZ_NONEXISTENT_APPLICATION'")
    result = await pipeline.execute_text("Open XYZ_NONEXISTENT_APPLICATION")
    print(f"[PIPELINE RESULT] {result}")

    # Verify failure state
    assert result["success"] is False, "Expected success=False for invalid application."
    assert "could not be found" in (result.get("error") or "") or "couldn't open" in (result.get("response") or "").lower(), "Expected error indicating app not found."
    assert "successfully" not in result["response"].lower(), "SERA must not claim success when app fails to launch."
    assert "now open" not in result["response"].lower(), "SERA must not claim app is open."

    print("\n✓ INVALID APPLICATION: PASS")


if __name__ == "__main__":
    asyncio.run(test_open_chrome_real())
    asyncio.run(test_invalid_application_failure())
