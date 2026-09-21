import asyncio
import logging
import psutil
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class SeraSelfCloseTool(Tool):
    """Dedicated native SERA Presence self-close tool with verified process shutdown."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    @property
    def name(self) -> str:
        return "sera_self_close"

    @property
    def description(self) -> str:
        return (
            "Safely closes the SERA Primary Presence desktop window and process. "
            "Use this when the user asks SERA to close itself, exit, or shut down presence."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        logger.info("[SeraSelfCloseTool] Initiating native SERA self-close...")

        # 1. Broadcast PRESENCE_CLOSE event over EventBus to trigger clean Electron window close
        if self.event_bus and hasattr(self.event_bus, "emit"):
            try:
                self.event_bus.emit("PRESENCE_CLOSE", {"action": "QUIT", "source": "USER_REQUEST"})
            except Exception as e:
                logger.debug(f"[SeraSelfCloseTool] EventBus emit error: {e}")

        # 2. Locate Presence / Electron processes
        presence_procs = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                p_name = (proc.info.get("name") or "").lower()
                if "electron" in p_name and "presence_desktop" in cmd:
                    presence_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 3. Wait up to 2.5s for clean shutdown via WebSocket
        deadline = asyncio.get_event_loop().time() + 2.5
        all_closed = False

        while asyncio.get_event_loop().time() < deadline:
            remaining = [p for p in presence_procs if p.is_running()]
            if not remaining:
                all_closed = True
                break
            await asyncio.sleep(0.1)

        # 4. If any Electron presence process is still running, terminate gracefully
        closed_pids = []
        for proc in presence_procs:
            try:
                if proc.is_running():
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except psutil.TimeoutExpired:
                        proc.kill()
                closed_pids.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                closed_pids.append(proc.pid)

        # 5. Final Verification: Confirm no presence processes exist
        verified_dead = True
        for p in presence_procs:
            if p.is_running():
                verified_dead = False
                break

        if verified_dead:
            return {
                "success": True,
                "message": "SERA Presence window and process have been safely closed and verified.",
                "closed_pids": closed_pids,
                "verified": True,
            }
        else:
            return {
                "success": False,
                "error": "Failed to fully terminate Presence process.",
                "verified": False,
            }
