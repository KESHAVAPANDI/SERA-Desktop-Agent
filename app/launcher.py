import asyncio
import logging
import os
import sys
import webbrowser
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.runtime import SERARuntime
from app.ui.server import SERAUIServer

logger = logging.getLogger(__name__)


async def start_sera(
    headless: bool = False,
    host: str = "127.0.0.1",
    port: int = 8765,
    auto_open_browser: bool = True,
    config_path: str | None = None,
):
    """Starts unified SERA Voice Runtime and Command Center UI Server in a single process."""
    load_dotenv()

    # 1. Initialize SERA Runtime (Mic, Hotkey, Wake Word, STT, Router, Agent, TTS)
    runtime = SERARuntime(config_path=config_path)

    # 2. Optionally Initialize and Start UI Command Center
    ui_server = None
    if not headless:
        ui_server = SERAUIServer(
            host=host,
            port=port,
            runtime=runtime,
        )
        await ui_server.start()

        if auto_open_browser:
            target_url = f"http://{host}:{port}"
            try:
                # Open Command Center in default browser
                asyncio.get_event_loop().call_later(0.5, lambda: webbrowser.open(target_url))
            except Exception as e:
                logger.debug(f"[Launcher] Could not automatically open browser: {e}")

    print("=" * 60)
    if not headless:
        print(f"SERA COMMAND CENTER: http://{host}:{port}")
    else:
        print("SERA RUNNING IN HEADLESS MODE (No UI Server)")
    print(f"VOICE CONTROL: Hotkey ({runtime.config.data.get('hotkey', {}).get('combination', 'ctrl+space')}) | Wake Word ('{getattr(runtime, 'wakeword_phrase', 'SERA')}')")
    print("=" * 60)

    # 3. Run runtime event loop
    try:
        await runtime.run()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        if ui_server:
            await ui_server.stop()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SERA 1.0 — Desktop Agent & Command Center")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode without web UI server")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser on startup")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="UI server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="UI server port (default: 8765)")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")

    args = parser.parse_args()

    try:
        asyncio.run(
            start_sera(
                headless=args.headless,
                host=args.host,
                port=args.port,
                auto_open_browser=not args.no_browser and not args.headless,
                config_path=args.config,
            )
        )
    except KeyboardInterrupt:
        print("\n[SERA] Shutdown complete.")


if __name__ == "__main__":
    main()
