import asyncio
import json
import logging
import mimetypes
import os
from typing import Any
import websockets
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from app.core.router import RoleCandidate

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
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """Attaches real-time EventBus and State listeners to broadcast over WebSockets."""
        if not self.runtime:
            return

        # 1. State Listener
        if hasattr(self.runtime, "state") and hasattr(self.runtime.state, "add_listener"):
            def on_state_change(old_s, new_s):
                asyncio.create_task(self.broadcast_event("RUNTIME_STATE_CHANGED", {
                    "status": new_s.value if hasattr(new_s, "value") else str(new_s),
                    "task": getattr(self.runtime.state, "last_user_message", None),
                }))
            self.runtime.state.add_listener(on_state_change)

        # 2. EventBus Listeners
        if hasattr(self.runtime, "events") and hasattr(self.runtime.events, "subscribe"):
            event_names = [
                "MODEL_SELECTED", "MODEL_FALLBACK", "MODEL_RATE_LIMITED",
                "TOOL_STARTED", "TOOL_COMPLETED",
                "VISION_STARTED", "VISION_COMPLETED",
                "AGENT_STARTED", "AGENT_COMPLETED",
                "TTS_STARTED", "TTS_INTERRUPTED",
                "TASK_CANCELLED", "TASK_COMPLETED",
            ]
            for ev in event_names:
                def make_handler(name):
                    def handler(**kwargs):
                        asyncio.create_task(self.broadcast_event(name, kwargs))
                    return handler
                self.runtime.events.subscribe(ev, make_handler(ev))

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
                    elif action == "UPDATE_ROLE":
                        role = msg_data.get("role")
                        candidates = msg_data.get("candidates", [])
                        res = self._update_role_candidates(role, candidates)
                        await websocket.send(json.dumps({"event": "ROLE_UPDATE_RESULT", "data": res}))
                        if res.get("success"):
                            await self.broadcast_event("ROLE_UPDATED", {"role": role, "candidates": candidates})
                except Exception as e:
                    logger.warning(f"[SERAUIServer] Error handling client message: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            logger.debug("[SERAUIServer] Client disconnected.")

    async def process_http_request(self, connection, request: Request) -> Response | None:
        """Handles HTTP GET & POST requests for static frontend assets and REST endpoints."""
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
            return await self._handle_api(connection, request, path)

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

    async def _handle_api(self, connection, request: Request, endpoint: str) -> Response:
        headers = Headers([
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])

        if request.headers.get("Method", "GET").upper() == "OPTIONS":
            return Response(200, "OK", headers, b"")

        if endpoint == "/api/state":
            data = self._get_initial_snapshot()
            return Response(200, "OK", headers, json.dumps(data).encode("utf-8"))

        if endpoint == "/api/providers":
            providers_data = self._get_providers_summary()
            return Response(200, "OK", headers, json.dumps(providers_data).encode("utf-8"))

        if endpoint == "/api/workflow":
            workflow_data = self._get_dynamic_workflow_graph()
            return Response(200, "OK", headers, json.dumps(workflow_data).encode("utf-8"))

        if endpoint == "/api/roles/update":
            # For POST requests via API
            try:
                body_bytes = getattr(request, "body", b"") or b"{}"
                body_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
                role = body_json.get("role")
                candidates = body_json.get("candidates", [])
                result = self._update_role_candidates(role, candidates)
                status_code = 200 if result.get("success") else 400
                if result.get("success"):
                    asyncio.create_task(self.broadcast_event("ROLE_UPDATED", {"role": role, "candidates": candidates}))
                return Response(status_code, "OK" if status_code == 200 else "Bad Request", headers, json.dumps(result).encode("utf-8"))
            except Exception as e:
                return Response(400, "Bad Request", headers, json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

        return Response(404, "Not Found", headers, b'{"error": "Endpoint not found"}')

    def _get_dynamic_workflow_graph(self) -> dict[str, Any]:
        """Generates dynamic horizontal execution graph from backend role configuration & health."""
        roles_summary = self._get_roles_summary()
        state_str = "IDLE"
        if self.runtime and hasattr(self.runtime, "state") and hasattr(self.runtime.state, "status"):
            state_str = self.runtime.state.status.value

        nodes = []
        edges = []

        # 1. STT Node (Input)
        nodes.append({
            "id": "node_stt",
            "label": "VOICE INPUT (STT)",
            "role": "stt",
            "provider": "NVIDIA",
            "model": "Canary-Qwen 2.5B",
            "status": "COMPLETED" if state_str not in ["IDLE", "LISTENING", "TRANSCRIBING"] else ("ACTIVE" if state_str in ["LISTENING", "TRANSCRIBING"] else "WAITING"),
            "x": 40,
            "y": 140,
            "latency_ms": 210,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
        })

        # STT Fallback
        nodes.append({
            "id": "node_stt_fb",
            "label": "Faster-Whisper (GPU)",
            "role": "stt",
            "provider": "Faster-Whisper",
            "model": "small",
            "status": "SKIPPED",
            "x": 40,
            "y": 280,
            "latency_ms": None,
            "is_primary": False,
            "fallback_rank": 1,
            "health": "HEALTHY",
        })
        edges.append({"id": "e_stt_fb", "source": "node_stt", "target": "node_stt_fb", "type": "FALLBACK"})

        # 2. Router Node
        nodes.append({
            "id": "node_router",
            "label": "ROLE & INTENT ROUTER",
            "role": "router",
            "provider": "Local",
            "model": "Intent Engine",
            "status": "COMPLETED" if state_str in ["THINKING", "EXECUTING", "SPEAKING"] else ("ACTIVE" if state_str == "THINKING" else "WAITING"),
            "x": 300,
            "y": 140,
            "latency_ms": 5,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
        })
        edges.append({"id": "e_stt_router", "source": "node_stt", "target": "node_router", "type": "PRIMARY"})

        # 3. Roles Branch (Reasoning, Fast, Desktop, Vision)
        role_y_offsets = {"reasoning": 60, "fast": 140, "desktop": 220, "vision": 300}
        curr_x = 580

        for r_name, cands in roles_summary.items():
            if r_name not in role_y_offsets:
                continue
            base_y = role_y_offsets[r_name]

            for idx, c in enumerate(cands):
                node_id = f"node_{r_name}_{idx}"
                p_name = c["provider"]
                m_name = c["model"]

                # Health
                h_status = "HEALTHY"
                if self.runtime and hasattr(self.runtime, "router") and hasattr(self.runtime.router, "health_registry"):
                    h = self.runtime.router.health_registry.get_health(p_name, m_name)
                    h_status = h.status.value

                is_primary = (idx == 0)
                n_status = "WAITING"
                if state_str in ["THINKING", "EXECUTING"] and is_primary:
                    n_status = "ACTIVE"
                if h_status in ["RATE_LIMITED", "AUTH_ERROR", "UNAVAILABLE"]:
                    n_status = h_status

                nodes.append({
                    "id": node_id,
                    "label": f"{r_name.upper()}: {m_name.split('/')[-1]}",
                    "role": r_name,
                    "provider": p_name,
                    "model": m_name,
                    "status": n_status,
                    "x": curr_x + (idx * 20),
                    "y": base_y + (idx * 50 if not is_primary else 0),
                    "latency_ms": 380 if is_primary else None,
                    "is_primary": is_primary,
                    "fallback_rank": idx,
                    "health": h_status,
                })

                if is_primary:
                    edges.append({"id": f"e_router_{r_name}", "source": "node_router", "target": node_id, "type": "PRIMARY"})
                else:
                    prev_id = f"node_{r_name}_{idx - 1}"
                    edges.append({"id": f"e_fb_{r_name}_{idx}", "source": prev_id, "target": node_id, "type": "FALLBACK"})

        # 4. Tools & Actions Node
        nodes.append({
            "id": "node_tools",
            "label": "SEMANTIC UI ACTIONS",
            "role": "tools",
            "provider": "Windows UIA",
            "model": "TargetResolver",
            "status": "ACTIVE" if state_str == "EXECUTING" else ("COMPLETED" if state_str == "SPEAKING" else "WAITING"),
            "x": 920,
            "y": 140,
            "latency_ms": 490,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
        })
        edges.append({"id": "e_desktop_tools", "source": "node_desktop_0", "target": "node_tools", "type": "PRIMARY"})

        # 5. Verification Node
        nodes.append({
            "id": "node_verify",
            "label": "OBSERVE ➔ VERIFY",
            "role": "verification",
            "provider": "Vision & UIA",
            "model": "StateInspector",
            "status": "COMPLETED" if state_str == "SPEAKING" else "WAITING",
            "x": 1180,
            "y": 140,
            "latency_ms": 110,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
        })
        edges.append({"id": "e_tools_verify", "source": "node_tools", "target": "node_verify", "type": "PRIMARY"})

        # 6. Streaming TTS Node
        nodes.append({
            "id": "node_tts",
            "label": "STREAMING TTS",
            "role": "tts",
            "provider": "Fish Audio",
            "model": "s2.1-pro-free",
            "status": "ACTIVE" if state_str == "SPEAKING" else "WAITING",
            "x": 1420,
            "y": 140,
            "latency_ms": 180,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
        })
        edges.append({"id": "e_verify_tts", "source": "node_verify", "target": "node_tts", "type": "PRIMARY"})

        return {
            "status": state_str,
            "active_task": getattr(self.runtime.state, "last_user_message", None) if self.runtime and hasattr(self.runtime, "state") else None,
            "nodes": nodes,
            "edges": edges,
            "roles": roles_summary,
            "timestamp": asyncio.get_event_loop().time(),
        }

    def _update_role_candidates(self, role: str, candidates: list[dict[str, str]]) -> dict[str, Any]:
        """Validates and applies role candidate updates to the live ModelRouter."""
        valid_roles = ["reasoning", "fast", "desktop", "vision", "ocr", "embeddings"]
        if role not in valid_roles:
            return {"success": False, "error": f"Invalid role '{role}'. Expected one of {valid_roles}"}

        if not candidates or not isinstance(candidates, list):
            return {"success": False, "error": "Candidates must be a non-empty list of candidate objects."}

        # Safety Check: Do not modify active router during active execution
        if self.runtime and hasattr(self.runtime, "state") and hasattr(self.runtime.state, "status"):
            from app.core.state import SERAStatus
            if self.runtime.state.status == SERAStatus.EXECUTING:
                return {
                    "success": False,
                    "error": "Safety guard: Cannot modify model candidate chain while SERA is actively executing a task.",
                }

        # Check for duplicates
        seen = set()
        for c in candidates:
            p = c.get("provider")
            m = c.get("model")
            if not p or not m:
                return {"success": False, "error": "Candidate must include both 'provider' and 'model'."}
            key = f"{p}:{m}"
            if key in seen:
                return {"success": False, "error": f"Duplicate candidate in chain: '{key}'"}
            seen.add(key)

        # Validate capabilities if router available
        if self.runtime and hasattr(self.runtime, "router"):
            new_chain = []
            for c in candidates:
                p_name = c["provider"]
                m_name = c["model"]
                provider_inst = self.runtime.router.providers.get(p_name)
                if not provider_inst:
                    return {"success": False, "error": f"Provider '{p_name}' is not registered."}

                # Capability checks
                caps = provider_inst.capabilities()
                if role == "vision" and not caps.get("vision", False):
                    return {"success": False, "error": f"Provider '{p_name}' does not support vision required for role '{role}'."}
                if role == "desktop" and not caps.get("tool_calling", False):
                    return {"success": False, "error": f"Provider '{p_name}' does not support tool calling required for role '{role}'."}

                new_chain.append(RoleCandidate(
                    provider_name=p_name,
                    model_name=m_name,
                    provider=provider_inst,
                    role=role,
                ))

            # Apply update to router
            self.runtime.router.role_chains[role] = new_chain
            logger.info(f"[SERAUIServer] Role '{role}' candidate chain updated: {[f'{c.provider_name}:{c.model_name}' for c in new_chain]}")

        return {
            "success": True,
            "role": role,
            "candidates": candidates,
            "message": f"Role '{role}' updated successfully.",
        }

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
            "workflow": self._get_dynamic_workflow_graph(),
        }

    def _get_roles_summary(self) -> dict[str, Any]:
        if not self.runtime or not hasattr(self.runtime, "router"):
            return {
                "reasoning": [
                    {"provider": "groq", "model": "openai/gpt-oss-120b"},
                    {"provider": "mistral", "model": "mistral-large-latest"},
                    {"provider": "mistral", "model": "mistral-medium-3.5"},
                    {"provider": "openrouter", "model": "openrouter/free"},
                ],
                "fast": [
                    {"provider": "mistral", "model": "mistral-small-latest"},
                    {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
                    {"provider": "openrouter", "model": "openrouter/free"},
                ],
                "desktop": [
                    {"provider": "mistral", "model": "codestral-latest"},
                    {"provider": "groq", "model": "openai/gpt-oss-120b"},
                    {"provider": "openrouter", "model": "openrouter/free"},
                ],
                "vision": [
                    {"provider": "groq", "model": "qwen/qwen3.6-27b"},
                    {"provider": "gemini", "model": "gemini-3-flash-preview"},
                    {"provider": "openrouter", "model": "openrouter/free"},
                ],
                "ocr": [
                    {"provider": "mistral", "model": "mistral-ocr-latest"},
                ],
                "embeddings": [
                    {"provider": "mistral", "model": "mistral-embed"},
                ],
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
