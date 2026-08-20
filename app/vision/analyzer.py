import json
import logging
import re
import time
from typing import Any

from app.core.router import ModelRouter
from app.core.telemetry import LatencyMetrics
from app.vision.capture import ScreenCapture
from app.vision.context import ScreenContextCache
from app.vision.models import ScreenContext, UIElement

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analyze this desktop screen capture and output a structured JSON object describing the screen state:
{
  "application": "Name of the primary active or focused application (e.g. Visual Studio Code, Google Chrome, File Explorer, Desktop)",
  "window_title": "Title of the active window or document",
  "summary": "1-2 concise sentences summarizing what the user is looking at or doing",
  "visible_text": ["List of key visible text phrases, error messages, code snippets, or headlines on screen"],
  "elements": [
    {
      "type": "button | input | text | window | menu | tab | link | icon",
      "text": "Label or content of the UI element",
      "x": 0,
      "y": 0,
      "width": 0,
      "height": 0
    }
  ]
}

Return ONLY the raw JSON object. Do not wrap in markdown or add conversational filler.
"""


class ScreenPerceptionEngine:
    """Coordinates screen capture, perceptual caching, multimodal analysis, and structured perception."""

    def __init__(
        self,
        router: ModelRouter,
        capture_service: ScreenCapture | None = None,
        cache: ScreenContextCache | None = None,
        vision_cfg: dict | None = None,
    ):
        cfg = vision_cfg or {}
        self.router = router
        self.capture = capture_service or ScreenCapture(
            max_width=cfg.get("max_width", 1920),
            image_quality=cfg.get("image_quality", 85),
            image_format=cfg.get("image_format", "jpeg"),
        )
        self.cache = cache or ScreenContextCache(
            enabled=cfg.get("cache_enabled", True),
            ttl_seconds=cfg.get("cache_duration_seconds", 5.0),
        )

    def is_vision_query(self, query: str) -> bool:
        """Determines if a user prompt is asking to inspect or read the screen."""
        lower = query.lower().strip()
        keywords = [
            "on my screen",
            "on screen",
            "this screen",
            "my screen",
            "what error",
            "what is open",
            "what app is open",
            "what application is open",
            "what window",
            "read my screen",
            "read the text on",
            "what webpage",
            "what website",
            "look at my screen",
            "see on my screen",
        ]
        return any(k in lower for k in keywords)

    async def analyze_screen(
        self,
        query: str,
        metrics: LatencyMetrics | None = None,
    ) -> tuple[ScreenContext, str]:
        """Performs screen capture, cached/multimodal perception, and generates spoken response."""
        t0 = time.perf_counter()

        # 1. Capture screen
        img, img_bytes, screen_hash, orig_w, orig_h = self.capture.capture_screen()
        t_capture = time.perf_counter()
        if metrics:
            metrics.screen_capture_ms = round((t_capture - t0) * 1000, 2)

        # 2. Check perceptual cache
        cached = self.cache.get(screen_hash)
        if cached is not None:
            if metrics:
                metrics.screen_context_cache_hit = True
                metrics.total_screen_analysis_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(f"[ScreenPerception] Perceptual Cache Hit for hash {screen_hash[:8]}")
            voice_resp = cached.format_voice_summary(query)
            return cached, voice_resp

        if metrics:
            metrics.screen_context_cache_hit = False

        # 3. Vision Model Invocation
        t_req_start = time.perf_counter()
        messages = [
            {"role": "user", "content": f"{VISION_PROMPT}\nUser Specific Query: {query}"}
        ]

        response, model_role = await self.router.generate_with_fallback(
            messages=messages,
            images=[img_bytes],
            preferred_role="vision",
        )
        t_req_end = time.perf_counter()
        if metrics:
            metrics.vision_request_ms = round((t_req_end - t_req_start) * 1000, 2)

        # 4. Parse & Validate Structured ScreenContext
        t_parse_start = time.perf_counter()
        context = self._parse_vision_response(
            raw_text=response.text or "",
            screen_hash=screen_hash,
            width=orig_w,
            height=orig_h,
        )
        t_parse_end = time.perf_counter()
        if metrics:
            metrics.vision_parse_ms = round((t_parse_end - t_parse_start) * 1000, 2)
            metrics.total_screen_analysis_ms = round((t_parse_end - t0) * 1000, 2)

        # 5. Update Cache
        self.cache.set(screen_hash, context)

        # 6. Format spoken response
        voice_response = context.format_voice_summary(query)
        return context, voice_response

    def _parse_vision_response(
        self,
        raw_text: str,
        screen_hash: str,
        width: int,
        height: int,
    ) -> ScreenContext:
        """Parses JSON output from vision model into validated ScreenContext."""
        cleaned = raw_text.strip()
        # Remove markdown fences if present
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            data = json.loads(cleaned)
            elements = []
            for el in data.get("elements", []):
                try:
                    elements.append(UIElement(**el))
                except Exception:
                    pass

            return ScreenContext(
                timestamp=time.time(),
                screen_hash=screen_hash,
                width=width,
                height=height,
                application=data.get("application", "Active Application"),
                window_title=data.get("window_title", "Active Window"),
                summary=data.get("summary", "Screen captured successfully."),
                visible_text=data.get("visible_text", []),
                elements=elements,
            )

        except Exception as e:
            logger.warning(f"[ScreenPerception] JSON parse failed ({e}). Building fallback context from raw text.")
            return ScreenContext(
                timestamp=time.time(),
                screen_hash=screen_hash,
                width=width,
                height=height,
                application="Desktop",
                window_title="Active Window",
                summary=cleaned[:200] if cleaned else "Screen active.",
                visible_text=[cleaned[:100]] if cleaned else [],
                elements=[],
            )
