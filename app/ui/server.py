import asyncio
import json
import logging
import mimetypes
import os
from typing import Any
import websockets
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

logger = logging.getLogger(__name__)


class SERAUIServer:
    """Lightweight asynchronous HTTP & WebSocket server for SERA Command Center UI."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        static_dir: str | None = None,
        runtime=None,
    ):
        self.host = host
        self.port = port
        self.static_dir = static_dir or os.path.join(os.path.dirname(__file__), "static")
        self.runtime = runtime
        self.clients: set = set()
        self._server = None
        self._is_running = False

    async def start(self):
        """Starts the unified HTTP & WebSocket server."""
        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port,
            process_request=self.process_http_request,
        )
        self._is_running = True
        logger.info(f"[SERAUIServer] Serving Command Center at http://{self.host}:{self.port}")
        print(f"[SERA UI] Command Center online: http://{self.host}:{self.port}")

    async def stop(self):
        """Stops the UI server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._is_running = False
            logger.info("[SERAUIServer] Stopped.")

    async def broadcast_event(self, event_type: str, data: dict[str, Any]):
        """Broadcasts real-time runtime events to all connected UI clients."""
        if not self.clients:
            return
        payload = json.dumps({"event": event_type, "data": data, "timestamp": asyncio.get_event_loop().time()})
        await asyncio.gather(
            *[client.send(payload) for client in self.clients],
            return_exceptions=True,
        )

    async def handler(self, websocket):
        """Handles real-time bi-directional WebSocket connections."""
        self.clients.add(websocket)
        logger.debug(f"[SERAUIServer] Client connected: {websocket.remote_address}")

        # Send initial snapshot on connect
        snapshot = self._get_initial_snapshot()
        await websocket.send(json.dumps({"event": "SNAPSHOT", "data": snapshot}))

        try:
            async for message in websocket:
                try:
                    msg_data = json.loads(message)
                    action = msg_data.get("action")
                    if action == "USER_PROMPT":
                        prompt_text = msg_data.get("text", "")
                        if self.runtime and hasattr(self.runtime, "agent"):
                            asyncio.create_task(self.runtime.agent.run(prompt_text))
                    elif action == "INTERRUPT":
                        if self.runtime and hasattr(self.runtime, "audio"):
                            self.runtime.audio.interrupt()
                except Exception as e:
                    logger.warning(f"[SERAUIServer] Error handling client message: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            logger.debug("[SERAUIServer] Client disconnected.")

    async def process_http_request(self, connection, request: Request) -> Response | None:
        """Handles HTTP GET requests for static frontend assets and REST endpoints."""
        # WebSocket upgrade request
        upgrade_header = request.headers.get("Upgrade", "")
        if upgrade_header.lower() == "websocket":
            return None

        # Clean path
        path = request.path.split("?")[0]
        if path == "/" or path == "":
            path = "/index.html"

        # API Endpoints
        if path.startswith("/api/"):
            return self._handle_api(path)

        # Serve static file
        local_path = os.path.normpath(os.path.join(self.static_dir, path.lstrip("/")))
        if not local_path.startswith(os.path.abspath(self.static_dir)):
            return Response(403, "Forbidden", Headers([("Content-Type", "text/plain")]), b"Forbidden")

        if os.path.isfile(local_path):
            content_type, _ = mimetypes.guess_type(local_path)
            content_type = content_type or "application/octet-stream"
            try:
                with open(local_path, "rb") as f:
                    body = f.read()
                return Response(
                    200,
                    "OK",
                    Headers([
                        ("Content-Type", content_type),
                        ("Content-Length", str(len(body))),
                        ("Access-Control-Allow-Origin", "*"),
                    ]),
                    body,
                )
            except Exception as e:
                return Response(500, "Internal Server Error", Headers([("Content-Type", "text/plain")]), str(e).encode())

        return Response(404, "Not Found", Headers([("Content-Type", "text/plain")]), b"Not Found")

    def _handle_api(self, endpoint: str) -> Response:
        headers = Headers([
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
        ])

        if endpoint == "/api/state":
            data = self._get_initial_snapshot()
            body = json.dumps(data).encode("utf-8")
            return Response(200, "OK", headers, body)

        if endpoint == "/api/providers":
            providers_data = self._get_providers_summary()
            body = json.dumps(providers_data).encode("utf-8")
            return Response(200, "OK", headers, body)

        return Response(404, "Not Found", headers, b'{"error": "Endpoint not found"}')

    def _get_initial_snapshot(self) -> dict[str, Any]:
        """Collects current runtime state snapshot."""
        state_str = "IDLE"
        if self.runtime and hasattr(self.runtime, "state") and hasattr(self.runtime.state, "status"):
            state_str = self.runtime.state.status.value

        return {
            "status": state_str,
            "active_task": getattr(self.runtime.state, "last_user_message", None) if self.runtime and hasattr(self.runtime, "state") else None,
            "gpu_usage_pct": 18.4,
            "system_memory_mb": 3420,
            "roles": self._get_roles_summary(),
            "providers": self._get_providers_summary(),
        }

    def _get_roles_summary(self) -> dict[str, Any]:
        if not self.runtime or not hasattr(self.runtime, "router"):
            return {
                "reasoning": [{"provider": "groq", "model": "openai/gpt-oss-120b"}],
                "fast": [{"provider": "mistral", "model": "mistral-small-latest"}],
                "desktop": [{"provider": "mistral", "model": "codestral-latest"}],
                "vision": [{"provider": "groq", "model": "qwen/qwen3.6-27b"}],
                "ocr": [{"provider": "mistral", "model": "mistral-ocr-latest"}],
                "embeddings": [{"provider": "mistral", "model": "mistral-embed"}],
            }
        summary = {}
        for r_name in ["reasoning", "fast", "desktop", "vision", "ocr", "embeddings"]:
            cands = self.runtime.router.get_role_candidates(r_name)
            summary[r_name] = [
                {"provider": c.provider_name, "model": c.model_name}
                for c in cands
            ]
        return summary

    def _get_providers_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "groq",
                "display_name": "Groq LPU",
                "status": "HEALTHY",
                "models": [
                    {
                        "model_id": "openai/gpt-oss-120b",
                        "display_name": "GPT-OSS 120B",
                        "role": "reasoning",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "reasoning": True, "tool_calling": True, "streaming": True},
                        "quota": {"requests_used": 28, "requests_limit": 100, "tokens_used": 14200, "tokens_limit": 100000, "reset_time_str": "3h 42m"},
                        "recent_avg_latency_ms": 380.0,
                        "recent_avg_ttft_ms": 110.0,
                    },
                    {
                        "model_id": "qwen/qwen3.6-27b",
                        "display_name": "Qwen 3.6 27B Vision",
                        "role": "vision",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "vision": True, "streaming": True},
                        "quota": {"requests_used": 12, "requests_limit": 100, "tokens_used": 8900, "tokens_limit": 100000, "reset_time_str": "3h 42m"},
                        "recent_avg_latency_ms": 410.0,
                        "recent_avg_ttft_ms": 130.0,
                    }
                ]
            },
            {
                "provider_name": "mistral",
                "display_name": "Mistral AI",
                "status": "HEALTHY",
                "models": [
                    {
                        "model_id": "mistral-small-latest",
                        "display_name": "Mistral Small",
                        "role": "fast",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "streaming": True, "tool_calling": True},
                        "quota": {"requests_used": 15, "requests_limit": 500, "tokens_used": 4200, "tokens_limit": 500000, "reset_time_str": "23h 10m"},
                        "recent_avg_latency_ms": 380.0,
                        "recent_avg_ttft_ms": 140.0,
                    },
                    {
                        "model_id": "codestral-latest",
                        "display_name": "Codestral",
                        "role": "desktop",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "tool_calling": True, "structured_output": True},
                        "quota": {"requests_used": 9, "requests_limit": 500, "tokens_used": 6100, "tokens_limit": 500000, "reset_time_str": "23h 10m"},
                        "recent_avg_latency_ms": 490.0,
                        "recent_avg_ttft_ms": 160.0,
                    },
                    {
                        "model_id": "mistral-large-latest",
                        "display_name": "Mistral Large",
                        "role": "reasoning (fallback)",
                        "is_primary": False,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "reasoning": True, "tool_calling": True},
                        "quota": {"requests_used": 4, "requests_limit": 500, "tokens_used": 3800, "tokens_limit": 500000, "reset_time_str": "23h 10m"},
                        "recent_avg_latency_ms": 750.0,
                        "recent_avg_ttft_ms": 240.0,
                    }
                ]
            },
            {
                "provider_name": "cerebras",
                "display_name": "Cerebras Fast Inference",
                "status": "UNAVAILABLE",
                "models": [
                    {
                        "model_id": "gpt-oss-120b",
                        "display_name": "GPT-OSS 120B",
                        "role": "inactive",
                        "is_primary": False,
                        "health_status": "AUTH_ERROR",
                        "cooldown_remaining_s": 60.0,
                        "capabilities": {"text": True, "reasoning": True},
                        "quota": {"is_unknown": True},
                        "recent_avg_latency_ms": None,
                        "recent_avg_ttft_ms": None,
                    }
                ]
            },
            {
                "provider_name": "zai",
                "display_name": "Z.AI GLM Models",
                "status": "RATE_LIMITED",
                "models": [
                    {
                        "model_id": "glm-5",
                        "display_name": "GLM 5",
                        "role": "inactive",
                        "is_primary": False,
                        "health_status": "RATE_LIMITED",
                        "cooldown_remaining_s": 60.0,
                        "capabilities": {"text": True, "reasoning": True},
                        "quota": {"is_unknown": True},
                        "recent_avg_latency_ms": None,
                        "recent_avg_ttft_ms": None,
                    }
                ]
            }
        ]
