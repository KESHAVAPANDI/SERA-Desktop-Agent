import asyncio
import sys

# Ensure Windows console encoding handles UTF-8
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.runtime import SERARuntime
from app.core.state import SERAStatus


async def main():
    print("=" * 60)
    print("SERA 1.0 RUNTIME CORE TEST")
    print("=" * 60)

    # Initialize runtime
    runtime = SERARuntime()

    print(f"\nInitial Status: {runtime.state.status.value}")
    assert runtime.state.status == SERAStatus.IDLE

    # 1. Test Local Intent (Brightness)
    print("\n--- [1] Testing Local Intent: Set brightness to 50% ---")
    resp = await runtime.process_text("set my brightness to 50%")
    print(f"Response: {resp}")
    print(f"Runtime Status after local action: {runtime.state.status.value}")

    # 2. Test Local Intent (Volume)
    print("\n--- [2] Testing Local Intent: Set volume to 30% ---")
    resp = await runtime.process_text("make volume 30%")
    print(f"Response: {resp}")

    # 3. Test Agent System Diagnostics Tool
    print("\n--- [3] Testing Agent Query: What is my system battery and CPU? ---")
    resp = await runtime.process_text("What is my system battery percentage and CPU usage?")
    print(f"Response: {resp}")

    # 4. Test Safety Confirmation Flow (Restart PC -> Cancel)
    print("\n--- [4] Testing Safety Confirmation Flow: Restart Computer ---")
    resp = await runtime.process_text("Restart my computer please")
    print(f"Response: {resp}")
    print(f"Status: {runtime.state.status.value}")
    print(f"Pending Confirmation: {runtime.state.pending_confirmation}")

    assert runtime.state.status == SERAStatus.CONFIRMING_ACTION
    assert runtime.state.pending_confirmation is not None

    # Cancel confirmation
    print("\n--- [5] User denies confirmation: 'No, cancel that' ---")
    resp = await runtime.process_text("No, cancel that")
    print(f"Response: {resp}")
    print(f"Status after cancellation: {runtime.state.status.value}")
    print(f"Pending Confirmation: {runtime.state.pending_confirmation}")

    assert runtime.state.status == SERAStatus.IDLE
    assert runtime.state.pending_confirmation is None

    print("\n=" * 60)
    print("ALL RUNTIME CORE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
