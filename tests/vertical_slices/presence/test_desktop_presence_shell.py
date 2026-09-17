"""Vertical Slice Test Suite — Native Transparent Desktop Shell (Phase 2B).

Mandate:
- Real-world verification of pywebview desktop overlay window configuration.
- Verification of 100% alpha-transparency, frameless, and on-top flags.
- Validation of Python-to-JS API bridge (ping, window control, click-through).
- Empirical verification of assets and integration with EvidenceVerificationFabric.
"""

import os
import sys
import pytest
from app.ui.desktop_presence import (
    DesktopPresenceConfig,
    DesktopPresenceLauncher,
    DesktopPresenceAPI,
)
from app.core.verification import EvidenceVerificationFabric, EvidenceType


@pytest.fixture
def fabric():
    return EvidenceVerificationFabric()


def test_desktop_presence_default_config():
    """Verifies that default DesktopPresenceConfig complies with Phase 2B visual specifications."""
    cfg = DesktopPresenceConfig()
    assert cfg.title == "SERA Presence"
    assert cfg.frameless is True, "Must be borderless/frameless"
    assert cfg.transparent is True, "Must enable alpha transparency"
    assert cfg.on_top is True, "Must float on top of desktop"
    assert cfg.width == 560
    assert cfg.height == 680
    assert cfg.dock_position == "bottom-right"
    assert cfg.background_color == "#000000"


def test_desktop_presence_custom_config():
    """Verifies custom docking positions and dimensions."""
    cfg = DesktopPresenceConfig(
        width=480,
        height=600,
        dock_position="center",
        port=9000,
    )
    launcher = DesktopPresenceLauncher(config=cfg)
    assert launcher.config.width == 480
    assert launcher.config.height == 600
    assert launcher.config.port == 9000

    url = launcher.get_presence_url()
    assert url == "http://127.0.0.1:9000/presence"

    x, y = launcher.compute_window_position()
    assert x >= 0
    assert y >= 0


def test_window_position_computation():
    """Verifies positioning logic for bottom-right and center docking."""
    launcher = DesktopPresenceLauncher()
    x, y = launcher.compute_window_position()
    assert isinstance(x, int)
    assert isinstance(y, int)
    assert x > 0, "Window x-coordinate should be placed in screen boundary"
    assert y > 0, "Window y-coordinate should be placed in screen boundary"


def test_presence_api_bridge():
    """Verifies JS-to-Python API bridge responses."""
    launcher = DesktopPresenceLauncher()
    api = launcher.api

    ping_res = api.ping()
    assert ping_res["status"] == "online"
    assert ping_res["surface"] == "native_desktop_shell"
    assert ping_res["platform"] == sys.platform
    assert ping_res["timestamp"] > 0

    # Test safe window controls when window is not yet active
    assert api.toggle_on_top() is False
    api.minimize()
    api.hide()
    api.show()
    api.close()


def test_desktop_presence_dry_run_lifecycle():
    """Verifies launcher initialization in dry_run mode without blocking."""
    launcher = DesktopPresenceLauncher()
    launcher.launch(dry_run=True)
    assert launcher.window is None
    assert launcher._is_running is False


def test_desktop_presence_assets_verified(fabric):
    """Empirically verifies that required desktop presence assets exist on disk."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    presence_html = os.path.join(base_dir, "app", "ui", "static", "presence.html")
    presence_css = os.path.join(base_dir, "app", "ui", "static", "css", "presence.css")
    vendor_three = os.path.join(base_dir, "app", "ui", "static", "js", "vendor", "three.min.js")

    rec_html = fabric.verify_file_system(presence_html, check_exists=True, min_bytes=500)
    assert rec_html.evidence_type == EvidenceType.FILE_SYSTEM
    assert rec_html.verified is True

    rec_css = fabric.verify_file_system(presence_css, check_exists=True, min_bytes=500)
    assert rec_css.verified is True

    rec_three = fabric.verify_file_system(vendor_three, check_exists=True, min_bytes=100000)
    assert rec_three.verified is True


def test_pywebview_window_options_contract():
    """Verifies that pywebview window parameters strictly reflect transparency & overlay contracts."""
    launcher = DesktopPresenceLauncher()
    # Create window instance using pywebview
    window = launcher.create_window(dry_run=False)
    assert window is not None
    assert window.title == "SERA Presence"
    assert window.frameless is True
    assert window.transparent is True
    assert window.on_top is True
    assert window.initial_width == 560
    assert window.initial_height == 680

    # Clean up window object
    try:
        window.destroy()
    except Exception:
        pass


def test_presence_http_endpoint_serving():
    """Verifies that the internal SERA UI server processes /presence and returns presence.html."""
    import asyncio
    from app.ui.server import SERAUIServer

    server = SERAUIServer()

    async def _test():
        status, headers, body = await server._process_http("GET", "/presence", {}, b"")
        assert "200" in status
        assert b"SERA 2.0" in body
        assert b"presence-canvas" in body

    asyncio.run(_test())


if __name__ == "__main__":
    test_desktop_presence_default_config()
    test_desktop_presence_custom_config()
    test_window_position_computation()
    test_presence_api_bridge()
    test_desktop_presence_dry_run_lifecycle()
    test_desktop_presence_assets_verified(EvidenceVerificationFabric())
    test_pywebview_window_options_contract()
    test_presence_http_endpoint_serving()
    print("ALL DESKTOP PRESENCE SHELL VERTICAL SLICE TESTS PASSED!")
