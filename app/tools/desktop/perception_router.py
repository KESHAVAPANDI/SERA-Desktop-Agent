import logging
import time
from typing import Any

from app.tools.desktop.models import NativeWindowContext
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.vision.analyzer import ScreenPerceptionEngine
from app.vision.models import ScreenContext, UIElement

logger = logging.getLogger(__name__)


class DesktopPerceptionRouter:
    """Coordinates the Desktop Perception Hierarchy: Native UI -> Groq Qwen Vision -> Gemini -> OpenRouter."""

    def __init__(
        self,
        inspector: WindowsUIInspector | None = None,
        vision_engine: ScreenPerceptionEngine | None = None,
        prefer_native: bool = True,
    ):
        self.inspector = inspector or WindowsUIInspector()
        self.vision_engine = vision_engine
        self.prefer_native = prefer_native

    def is_desktop_query(self, query: str) -> bool:
        """Checks if a user query requires screen or desktop perception."""
        lower = query.lower().strip()
        keywords = [
            "on my screen", "on screen", "this screen", "my screen",
            "what error", "what app is open", "what application is open",
            "what window", "window title", "what buttons", "what controls",
            "read my screen", "read the text on", "what webpage", "what website",
            "look at my screen", "see on my screen", "active window"
        ]
        return any(k in lower for k in keywords)

    async def perceive(
        self,
        query: str,
        metrics: Any = None,
    ) -> tuple[str, str, dict[str, Any]]:
        """Executes perception using cheapest reliable method.

        Returns:
            (spoken_response, perception_method, raw_context_dict)
        """
        t0 = time.perf_counter()
        lower_q = query.lower()

        # -------------------------------------------------------------
        # Tier 1: Native Windows UI Automation (Zero Cloud Latency)
        # -------------------------------------------------------------
        if self.prefer_native:
            t_native_start = time.perf_counter()
            native_ctx = self.inspector.get_active_window_context()
            t_native_end = time.perf_counter()
            if metrics:
                metrics.ui_inspection_ms = round((t_native_end - t_native_start) * 1000, 2)

            # Evaluate sufficiency
            if native_ctx and (native_ctx.window_title or native_ctx.controls):
                is_pure_app_query = any(k in lower_q for k in ["what app", "what application", "window title", "active window"])
                is_button_query = "button" in lower_q or "controls" in lower_q

                if is_pure_app_query:
                    spoken = f"You currently have {native_ctx.application} open with the window title '{native_ctx.window_title}'."
                    if metrics:
                        metrics.perception_method = "native"
                        metrics.total_screen_analysis_ms = round((time.perf_counter() - t0) * 1000, 2)
                    return spoken, "native", native_ctx.model_dump()

                if is_button_query and native_ctx.controls:
                    buttons = [c.name for c in native_ctx.controls if c.type == "button" and c.name]
                    if buttons:
                        btn_str = ", ".join(buttons[:5])
                        spoken = f"In {native_ctx.application}, I can see buttons: {btn_str}."
                        if metrics:
                            metrics.perception_method = "native"
                            metrics.total_screen_analysis_ms = round((time.perf_counter() - t0) * 1000, 2)
                        return spoken, "native", native_ctx.model_dump()

        # -------------------------------------------------------------
        # Tier 2: Multi-Model Vision Router (Qwen -> Gemini -> OpenRouter)
        # -------------------------------------------------------------
        if self.vision_engine:
            logger.info("[DesktopPerceptionRouter] Native context insufficient for query. Routing to Vision Router...")
            screen_ctx, voice_resp = await self.vision_engine.analyze_screen(query, metrics=metrics)
            providers = getattr(getattr(self.vision_engine, "router", None), "providers", {})
            vision_provider = str(providers.get("vision", ""))
            method = "vision_qwen" if "qwen" in vision_provider.lower() else "vision_gemini"
            if metrics:
                metrics.perception_method = method
            raw_data = screen_ctx.model_dump() if hasattr(screen_ctx, "model_dump") else {}
            return voice_resp, method, raw_data

        return "I could not inspect your desktop.", "failed", {}
