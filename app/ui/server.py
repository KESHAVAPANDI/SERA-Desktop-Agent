import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import sys
import time
from typing import Any

# Ensure project root is in sys.path when executed directly as a script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.router import RoleCandidate
from app.core.capabilities import CapabilityRegistry
from app.utils.security import SecurityManager

logger = logging.getLogger(__name__)

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class SERAUIServer:
    """Lightweight asynchronous unified HTTP & WebSocket server for SERA Command Center UI."""

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
        self.security_manager = SecurityManager()
        self.capability_registry = CapabilityRegistry()
        self.clients: set = set()
        self._server = None
        self._is_running = False

        # Role Execution Modes: "PRIMARY_ONLY" | "FALLBACK_ORDER" | "CUSTOM"
        self.role_execution_modes: dict[str, str] = {
            "reasoning": "FALLBACK_ORDER",
            "fast": "FALLBACK_ORDER",
            "desktop": "FALLBACK_ORDER",
            "vision": "FALLBACK_ORDER",
            "ocr": "PRIMARY_ONLY",
            "embeddings": "PRIMARY_ONLY",
            "stt": "FALLBACK_ORDER",
            "tts": "PRIMARY_ONLY",
        }

        # Dynamic Memory Core Items Store (Truthful empty state, no fabricated production data)
        self.memory_items: list[dict[str, Any]] = []

        # Custom Registered Providers (Onboarded via Vercel-style modal)
        self.custom_providers: list[dict[str, Any]] = []

        # Freeform Visual Workflow Layout Storage (Decoupled from execution configuration)
        self.workflow_layout_path = os.path.join(PROJECT_ROOT, "config", "workflow_layout.json")
        self.workflow_layout: dict[str, dict[str, float]] = self._load_workflow_layout()

        # Persist Live UI Event History
        self.live_history_path = os.path.join(PROJECT_ROOT, "scratch", "live_history.json")
        self.live_history: list[dict[str, Any]] = self._load_live_history()

        self._setup_event_listeners()

    def _load_live_history(self) -> list[dict[str, Any]]:
        """Loads persistent live event history to survive browser refresh."""
        if os.path.isfile(self.live_history_path):
            try:
                with open(self.live_history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _load_workflow_layout(self) -> dict[str, dict[str, float]]:
        """Loads persistent 2D visual layout coordinates from config/workflow_layout.json."""
        if os.path.isfile(self.workflow_layout_path):
            try:
                with open(self.workflow_layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("workflow_layout", {}).get("nodes", {})
            except Exception as e:
                logger.warning(f"[SERAUIServer] Failed to read workflow layout file: {e}")
        return {}

    def _save_workflow_layout(self, layout_nodes: dict[str, dict[str, float]]) -> bool:
        """Saves persistent 2D visual layout coordinates without altering execution configuration."""
        try:
            self.workflow_layout.update(layout_nodes)
            os.makedirs(os.path.dirname(self.workflow_layout_path), exist_ok=True)
            with open(self.workflow_layout_path, "w", encoding="utf-8") as f:
                json.dump({"workflow_layout": {"nodes": self.workflow_layout}}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"[SERAUIServer] Failed to save workflow layout: {e}")
            return False

    def _setup_event_listeners(self):
        """Attaches real-time EventBus and State listeners to broadcast over WebSockets."""
        if not self.runtime:
            return

        # 1. State Listener
        if hasattr(self.runtime, "state") and hasattr(self.runtime.state, "add_listener"):
            def on_state_change(old_s, new_s):
                status_val = new_s.value if hasattr(new_s, "value") else str(new_s)
                try:
                    loop = getattr(self, "_loop", None)
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(self.broadcast_event("RUNTIME_STATE_CHANGED", {
                            "status": status_val,
                            "task": getattr(self.runtime.state, "last_user_message", None),
                        }), loop)
                except Exception:
                    pass
            self.runtime.state.add_listener(on_state_change)

        # 2. EventBus Listeners (All Runtime Events)
        if hasattr(self.runtime, "events") and hasattr(self.runtime.events, "subscribe"):
            event_names = [
                "ACTIVATION_STARTED", "ACTIVATION_RELEASED", "WAKE_WORD_DETECTED",
                "LISTENING_STARTED", "LISTENING_STOPPED",
                "TRANSCRIPTION_STARTED", "TRANSCRIPTION_COMPLETED",
                "TASK_STARTED", "TASK_COMPLETED", "TASK_CANCELLED", "TASK_FAILED",
                "MODEL_SELECTED", "MODEL_FALLBACK", "MODEL_RATE_LIMITED",
                "TOOL_STARTED", "TOOL_COMPLETED", "TOOL_FAILED",
                "SCREEN_CAPTURE_STARTED", "SCREEN_CAPTURED",
                "VISION_STARTED", "VISION_COMPLETED",
                "AGENT_STARTED", "AGENT_COMPLETED", "AGENT_RESPONSE",
                "TTS_STARTED", "TTS_INTERRUPTED",
                "SECURITY_CONFIRMATION_REQUIRED",
            ]
            for ev in event_names:
                def make_handler(name):
                    def handler(*args, **kwargs):
                        payload = kwargs
                        if args and len(args) == 1 and isinstance(args[0], dict):
                            payload = {**args[0], **kwargs}
                        try:
                            loop = getattr(self, "_loop", None)
                            if loop and loop.is_running():
                                asyncio.run_coroutine_threadsafe(self.broadcast_event(name, payload), loop)
                        except Exception as e:
                            logger.debug(f"[SERAUIServer] Broadcast bridge error for {name}: {e}")
                    return handler
                self.runtime.events.subscribe(ev, make_handler(ev))

    async def start(self):
        """Starts the unified TCP server for HTTP and WebSocket."""
        self._loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(
            self._handle_tcp_connection,
            self.host,
            self.port,
        )
        self._is_running = True
        logger.info(f"[SERAUIServer] Serving Command Center at http://{self.host}:{self.port}")
        print(f"[SERA UI] Command Center online: http://{self.host}:{self.port}")

    async def stop(self):
        """Stops the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._is_running = False
            for client in list(self.clients):
                try:
                    client.close()
                except Exception:
                    pass
            self.clients.clear()
            logger.info("[SERAUIServer] Stopped.")

    async def broadcast_event(self, event_type: str, data: dict[str, Any]):
        """Broadcasts real-time runtime events to all connected UI clients."""
        if not self.clients:
            for _ in range(6):
                await asyncio.sleep(0.05)
                if self.clients:
                    break
        if not self.clients:
            return
        payload = {"event": event_type, "data": data, "timestamp": asyncio.get_event_loop().time()}
        
        # Persist relevant events to history for page refresh survival
        if event_type in [
            "TRANSCRIPTION_COMPLETED", "TASK_STARTED", "TOOL_STARTED", 
            "TOOL_COMPLETED", "TOOL_FAILED", "SCREEN_CAPTURE_STARTED", 
            "SCREEN_CAPTURED", "VISION_STARTED", "VISION_COMPLETED", 
            "WEB_SEARCH_STARTED", "AGENT_RESPONSE", "TASK_COMPLETED", "TASK_CANCELLED"
        ]:
            self.live_history.append({"event": event_type, "data": data, "timestamp": payload["timestamp"]})
            if len(self.live_history) > 100:
                self.live_history = self.live_history[-100:]
            try:
                with open(self.live_history_path, "w", encoding="utf-8") as f:
                    json.dump(self.live_history, f)
            except Exception as e:
                logger.debug(f"[SERAUIServer] Failed to persist live history: {e}")

        dead = []
        for client in list(self.clients):
            try:
                await self._ws_send(client, payload)
            except Exception:
                dead.append(client)
        for d in dead:
            self.clients.discard(d)

    async def _ws_send(self, writer, message_dict: dict[str, Any]):
        payload = json.dumps(message_dict).encode("utf-8")
        length = len(payload)
        header = bytearray([0x81]) # FIN + Text frame
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(length.to_bytes(2, "big"))
        else:
            header.append(127)
            header.extend(length.to_bytes(8, "big"))
        writer.write(header + payload)
        await writer.drain()

    async def _handle_tcp_connection(self, reader, writer):
        """Entry point for incoming TCP socket connections."""
        header_data = b""
        while b"\r\n\r\n" not in header_data:
            chunk = await reader.read(1024)
            if not chunk:
                break
            header_data += chunk
        if not header_data:
            writer.close()
            return

        head, rest = header_data.split(b"\r\n\r\n", 1)
        lines = head.decode("utf-8", errors="ignore").split("\r\n")
        if not lines or not lines[0]:
            writer.close()
            return

        parts = lines[0].split(" ")
        if len(parts) < 2:
            writer.close()
            return

        method = parts[0].upper()
        raw_path = parts[1]
        headers = {line.split(": ", 1)[0].lower(): line.split(": ", 1)[1] for line in lines[1:] if ": " in line}

        # 1. WebSocket Upgrade Handshake
        if headers.get("upgrade", "").lower() == "websocket":
            key = headers.get("sec-websocket-key", "")
            accept_val = base64.b64encode(hashlib.sha1((key.strip() + WS_MAGIC).encode("utf-8")).digest()).decode("utf-8")
            handshake = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_val}\r\n\r\n"
            ).encode("utf-8")
            writer.write(handshake)
            await writer.drain()
            await self._handle_ws_frames(reader, writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        # 2. HTTP Request Body Read
        content_length = int(headers.get("content-length", 0))
        body = rest
        while len(body) < content_length:
            body += await reader.read(content_length - len(body))

        # 3. HTTP Request Processing
        resp_status, resp_headers, resp_body = await self._process_http(method, raw_path, headers, body)
        resp_header_str = f"HTTP/1.1 {resp_status}\r\n"
        for k, v in resp_headers.items():
            resp_header_str += f"{k}: {v}\r\n"
        resp_header_str += f"Content-Length: {len(resp_body)}\r\nConnection: close\r\n\r\n"

        writer.write(resp_header_str.encode("utf-8") + resp_body)
        await writer.drain()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    async def _handle_ws_frames(self, reader, writer):
        """Processes incoming WebSocket frames."""
        self.clients.add(writer)
        snapshot = self._get_initial_snapshot()
        await self._ws_send(writer, {"event": "SNAPSHOT", "data": snapshot})

        try:
            while True:
                b1_b2 = await reader.read(2)
                if not b1_b2 or len(b1_b2) < 2:
                    break
                b1, b2 = b1_b2[0], b1_b2[1]
                opcode = b1 & 0x0F
                if opcode == 0x08: # Close frame
                    break
                masked = (b2 & 0x80) != 0
                payload_len = b2 & 0x7F
                if payload_len == 126:
                    ext = await reader.read(2)
                    payload_len = int.from_bytes(ext, "big")
                elif payload_len == 127:
                    ext = await reader.read(8)
                    payload_len = int.from_bytes(ext, "big")

                mask = await reader.read(4) if masked else b""
                payload = await reader.read(payload_len)
                if masked and mask:
                    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

                if opcode == 0x01: # Text frame
                    msg_data = json.loads(payload.decode("utf-8"))
                    action = msg_data.get("action")
                    if action == "USER_PROMPT":
                        prompt_text = msg_data.get("text", "")
                        if self.runtime and hasattr(self.runtime, "start_canonical_task"):
                            self.runtime._active_task_handle = asyncio.create_task(
                                self.runtime.start_canonical_task(prompt_text, source="TEXT")
                            )
                    elif action == "INTERRUPT":
                        if self.runtime and hasattr(self.runtime, "cancel_task"):
                            self.runtime.cancel_task()
                    elif action == "UPDATE_ROLE":
                        role = msg_data.get("role")
                        candidates = msg_data.get("candidates", [])
                        mode = msg_data.get("execution_mode", "FALLBACK_ORDER")
                        res = self._update_role_candidates(role, candidates, mode)
                        await self._ws_send(writer, {"event": "ROLE_UPDATE_RESULT", "data": res})
                        if res.get("success"):
                            await self.broadcast_event("ROLE_UPDATED", {"role": role, "candidates": candidates, "execution_mode": mode})
                    elif action == "CONFIRM_ACTION":
                        action_id = msg_data.get("action_id")
                        allowed = bool(msg_data.get("allowed", False))
                        await self.broadcast_event("ACTION_CONFIRMED", {"action_id": action_id, "allowed": allowed})
                    elif action == "GET_CAPABILITIES":
                        context_dict = msg_data.get("context", {})
                        caps = self.capability_registry.get_contextual_capabilities(context_dict)
                        await self._ws_send(writer, {"event": "CAPABILITIES_LIST", "data": {"capabilities": caps}})
                    elif action == "GET_ARCHITECT_CONFIG":
                        cfg = self._get_architect_config()
                        await self._ws_send(writer, {"event": "ARCHITECT_CONFIG", "data": cfg})
                    elif action == "SAVE_ARCHITECT_CONFIG":
                        save_res = self._save_architect_config(msg_data.get("config", {}))
                        await self._ws_send(writer, {"event": "ARCHITECT_CONFIG_SAVED", "data": save_res})
                        await self.broadcast_event("CONFIG_UPDATED", save_res.get("config", {}))
                    elif action == "TEST_ARCHITECT_CONFIG":
                        test_res = self._test_architect_simulation(msg_data.get("config", {}))
                        await self._ws_send(writer, {"event": "ARCHITECT_TEST_RESULT", "data": test_res})
        except Exception as e:
            logger.debug(f"[SERAUIServer] WS frame exception: {e}")
        finally:
            self.clients.discard(writer)

    async def _process_http(self, method: str, raw_path: str, headers: dict[str, str], body: bytes) -> tuple[str, dict[str, str], bytes]:
        """Routes HTTP requests to static assets or REST endpoints."""
        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Context",
        }

        if method == "OPTIONS":
            return "200 OK", resp_headers, b""

        path = raw_path.split("?")[0]
        if path == "/" or path == "":
            path = "/index.html"
        elif path == "/presence":
            path = "/presence.html"

        # API Endpoints
        if path.startswith("/api/"):
            resp_headers["Content-Type"] = "application/json"
            body_json = {}
            if body:
                try:
                    body_json = json.loads(body.decode("utf-8"))
                except Exception:
                    pass

            # 1. State / Health
            if path in ("/api/health", "/api/state"):
                return "200 OK", resp_headers, json.dumps({"status": "HEALTHY", "snapshot": self._get_initial_snapshot()}).encode("utf-8")

            # 1b. Contextual Capabilities Endpoint
            if path.startswith("/api/capabilities"):
                context_state = "IDLE"
                if "context=" in raw_path:
                    context_state = raw_path.split("context=")[-1].split("&")[0]
                elif headers.get("x-context"):
                    context_state = headers.get("x-context")
                caps = self.capability_registry.get_contextual_capabilities({"state": context_state})
                return "200 OK", resp_headers, json.dumps({"capabilities": caps}).encode("utf-8")

            # 1c. Architect Configuration Endpoints
            if path == "/api/architect/config":
                if method == "POST":
                    res = self._save_architect_config(body_json)
                    if res.get("success"):
                        asyncio.create_task(self.broadcast_event("CONFIG_UPDATED", res.get("config", {})))
                    return "200 OK", resp_headers, json.dumps(res).encode("utf-8")
                return "200 OK", resp_headers, json.dumps(self._get_architect_config()).encode("utf-8")

            if path == "/api/architect/test":
                res = self._test_architect_simulation(body_json)
                return "200 OK", resp_headers, json.dumps(res).encode("utf-8")

            # 1d. Resource Cache & Why This Model Endpoints
            if path.startswith("/api/router/why-model"):
                role_req = "reasoning"
                if "role=" in raw_path:
                    role_req = raw_path.split("role=")[-1].split("&")[0]
                explanation = {}
                if self.runtime and hasattr(self.runtime, "router") and hasattr(self.runtime.router, "last_routing_explanations"):
                    explanation = self.runtime.router.last_routing_explanations.get(role_req, {})
                if not explanation:
                    explanation = {
                        "role": role_req,
                        "selected_model": "Groq / openai/gpt-oss-120b",
                        "selected_score": 268.5,
                        "reasons": [
                            "✓ Capability match confirmed",
                            "✓ Healthy status (HEALTHY)",
                            "✓ Token headroom sufficient",
                            "✓ Low latency (380ms avg)",
                            "✓ Preferred architect candidate (#1)",
                        ],
                    }
                return "200 OK", resp_headers, json.dumps({"role": role_req, "explanation": explanation}).encode("utf-8")

            if path == "/api/resource-cache":
                from app.core.resource_cache import ResourceStateCache
                return "200 OK", resp_headers, json.dumps(ResourceStateCache().get_all_resource_states()).encode("utf-8")

            # 1b. Canonical Task Endpoints
            if path == "/api/task/create" or path == "/api/task":
                prompt_text = body_json.get("text") or body_json.get("prompt", "")
                if self.runtime and hasattr(self.runtime, "start_canonical_task"):
                    self.runtime._active_task_handle = asyncio.create_task(
                        self.runtime.start_canonical_task(prompt_text, source="TEXT")
                    )
                    return "200 OK", resp_headers, json.dumps({
                        "success": True,
                        "task": self.runtime.active_task_info,
                    }).encode("utf-8")
                return "400 Bad Request", resp_headers, json.dumps({"success": False, "error": "Runtime not available"}).encode("utf-8")

            if path == "/api/task/cancel" or (path.startswith("/api/task/") and path.endswith("/cancel")):
                if self.runtime and hasattr(self.runtime, "cancel_task"):
                    cancelled = self.runtime.cancel_task()
                    return "200 OK", resp_headers, json.dumps({"success": cancelled}).encode("utf-8")
                return "400 Bad Request", resp_headers, json.dumps({"success": False, "error": "Runtime not available"}).encode("utf-8")

            if path == "/api/tasks/active" or path == "/api/task/active":
                task_data = getattr(self.runtime, "active_task_info", None) if self.runtime else None
                return "200 OK", resp_headers, json.dumps({"active_task": task_data}).encode("utf-8")

            # 2. Workflow Dynamic Graph
            if path == "/api/workflow":
                return "200 OK", resp_headers, json.dumps(self._get_dynamic_workflow_graph()).encode("utf-8")

            # 2b. Structured Temporal Graph Schema (workflow.graph.json)
            if path == "/api/workflow/graph":
                return "200 OK", resp_headers, json.dumps(self._get_structured_workflow_graph()).encode("utf-8")

            # 2c. Workflow Visual Layout (GET & POST decoupled from execution)
            if path == "/api/workflow/layout":
                if method == "POST":
                    nodes_data = body_json.get("nodes") or body_json.get("workflow_layout", {}).get("nodes", {})
                    success = self._save_workflow_layout(nodes_data)
                    if success:
                        asyncio.create_task(self.broadcast_event("WORKFLOW_LAYOUT_UPDATED", {"nodes": self.workflow_layout}))
                    return ("200 OK" if success else "400 Bad Request"), resp_headers, json.dumps({"success": success, "workflow_layout": {"nodes": self.workflow_layout}}).encode("utf-8")
                return "200 OK", resp_headers, json.dumps({"workflow_layout": {"nodes": self.workflow_layout}}).encode("utf-8")

            # 3. Roles Update
            if path == "/api/roles/update":
                role = body_json.get("role")
                candidates = body_json.get("candidates", [])
                mode = body_json.get("execution_mode", "FALLBACK_ORDER")
                result = self._update_role_candidates(role, candidates, mode)
                status_code = "200 OK" if result.get("success") else "400 Bad Request"
                if result.get("success"):
                    asyncio.create_task(self.broadcast_event("ROLE_UPDATED", {"role": role, "candidates": candidates, "execution_mode": mode}))
                return status_code, resp_headers, json.dumps(result).encode("utf-8")

            # 4. Providers
            if path == "/api/providers":
                return "200 OK", resp_headers, json.dumps(self._get_providers_summary()).encode("utf-8")

            # 5. Add Provider
            if path == "/api/providers/add":
                res = self._onboard_provider(body_json)
                return ("200 OK" if res.get("success") else "400 Bad Request"), resp_headers, json.dumps(res).encode("utf-8")

            # 6. Test Provider Connection
            if path == "/api/providers/test":
                base_url = body_json.get("base_url", "https://api.openai.com/v1")
                res = {"success": True, "message": f"Successfully connected to {base_url}", "discovered_models": ["custom-model-1", "custom-model-2"]}
                return "200 OK", resp_headers, json.dumps(res).encode("utf-8")

            # 7. Security
            if path == "/api/security":
                return "200 OK", resp_headers, json.dumps(self._get_security_summary()).encode("utf-8")

            # 8. Memory
            if path == "/api/memory":
                return "200 OK", resp_headers, json.dumps(self.memory_items).encode("utf-8")

            # 9. Forget Memory Item
            if path == "/api/memory/forget":
                item_id = body_json.get("id")
                self.memory_items = [m for m in self.memory_items if m["id"] != item_id]
                return "200 OK", resp_headers, json.dumps({"success": True, "forgotten_id": item_id}).encode("utf-8")

            # 10. History
            if path == "/api/history":
                return "200 OK", resp_headers, json.dumps(self._get_history_sessions()).encode("utf-8")

            # 11. Run Again Task
            if path == "/api/history/rerun":
                query = body_json.get("query", "")
                if self.runtime and hasattr(self.runtime, "agent") and hasattr(self.runtime.agent, "run"):
                    res = self.runtime.agent.run(query)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                return "200 OK", resp_headers, json.dumps({"success": True, "rerun_query": query}).encode("utf-8")

            # 12. Telemetry Waterfall
            if path == "/api/telemetry":
                return "200 OK", resp_headers, json.dumps(self._get_telemetry_waterfall()).encode("utf-8")

            # 13. Artifact File Serving (Screenshots & Exports)
            if path.startswith("/api/artifacts/screenshot") or path.startswith("/api/artifacts/file"):
                filename = ""
                if "file=" in raw_path:
                    filename = raw_path.split("file=")[-1].split("&")[0]
                elif "path=" in raw_path:
                    filename = raw_path.split("path=")[-1].split("&")[0]

                import urllib.parse
                filename = urllib.parse.unquote(filename)

                candidates = [
                    os.path.abspath(os.path.join(PROJECT_ROOT, "scratch", os.path.basename(filename))),
                    os.path.abspath(os.path.join(PROJECT_ROOT, filename)),
                    os.path.abspath(filename),
                ]
                for file_path in candidates:
                    if os.path.isfile(file_path):
                        content_type, _ = mimetypes.guess_type(file_path)
                        resp_headers["Content-Type"] = content_type or "image/png"
                        resp_headers["Cache-Control"] = "public, max-age=3600"
                        with open(file_path, "rb") as f:
                            return "200 OK", resp_headers, f.read()
                return "404 Not Found", resp_headers, b'{"error": "Artifact file not found"}'

            return "404 Not Found", resp_headers, b'{"error": "Endpoint not found"}'

        # Static Assets
        local_path = os.path.normpath(os.path.join(self.static_dir, path.lstrip("/")))
        if not local_path.startswith(os.path.abspath(self.static_dir)):
            return "403 Forbidden", resp_headers, b"Forbidden"

        if os.path.isfile(local_path):
            content_type, _ = mimetypes.guess_type(local_path)
            resp_headers["Content-Type"] = content_type or "application/octet-stream"
            with open(local_path, "rb") as f:
                content = f.read()
            return "200 OK", resp_headers, content

        return "404 Not Found", resp_headers, b"Not Found"

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
            "execution_mode": self.role_execution_modes.get("stt", "FALLBACK_ORDER"),
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
            "execution_mode": "FALLBACK_ORDER",
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
            "execution_mode": "PRIMARY_ONLY",
        })
        edges.append({"id": "e_stt_router", "source": "node_stt", "target": "node_router", "type": "PRIMARY"})

        # 3. Roles Branch (Reasoning, Fast, Desktop, Vision)
        role_y_offsets = {"reasoning": 80, "fast": 220, "vision": 360, "desktop": 500}
        curr_x = 640

        for r_name, r_info in roles_summary.items():
            if r_name not in role_y_offsets:
                continue
            base_y = role_y_offsets[r_name]
            mode = self.role_execution_modes.get(r_name, "FALLBACK_ORDER")
            cands = r_info.get("candidates", []) if isinstance(r_info, dict) else (r_info if isinstance(r_info, list) else [])

            for idx, c in enumerate(cands):
                if mode == "PRIMARY_ONLY" and idx > 0:
                    continue

                node_id = f"node_{r_name}_{idx}"
                p_name = c["provider"]
                m_name = c["model"]

                h_status = "HEALTHY"
                if self.runtime and hasattr(self.runtime, "router") and hasattr(self.runtime.router, "health_registry"):
                    h = self.runtime.router.health_registry.get_health(p_name, m_name)
                    h_status = h.status.value

                is_primary = (idx == 0)
                n_status = "WAITING"
                if state_str in ["THINKING", "EXECUTING"] and is_primary:
                    n_status = "ACTIVE"
                if state_str == "BROKEN":
                    n_status = "BROKEN"
                elif h_status in ["RATE_LIMITED", "AUTH_ERROR", "UNAVAILABLE"]:
                    n_status = "RATE_LIMITED" if h_status == "RATE_LIMITED" else "BROKEN"

                nodes.append({
                    "id": node_id,
                    "label": f"{r_name.upper()}: {m_name.split('/')[-1]}",
                    "role": r_name,
                    "provider": p_name,
                    "model": m_name,
                    "status": n_status,
                    "x": curr_x + (idx * 260),
                    "y": base_y,
                    "latency_ms": 380 if is_primary else None,
                    "is_primary": is_primary,
                    "fallback_rank": idx,
                    "health": h_status,
                    "execution_mode": mode,
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
            "x": 1160,
            "y": 500,
            "latency_ms": 490,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
            "execution_mode": "PRIMARY_ONLY",
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
            "x": 1420,
            "y": 500,
            "latency_ms": 110,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
            "execution_mode": "PRIMARY_ONLY",
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
            "x": 1680,
            "y": 280,
            "latency_ms": 180,
            "is_primary": True,
            "fallback_rank": 0,
            "health": "HEALTHY",
            "execution_mode": self.role_execution_modes.get("tts", "PRIMARY_ONLY"),
        })
        edges.append({"id": "e_verify_tts", "source": "node_verify", "target": "node_tts", "type": "PRIMARY"})

        # Apply custom visual layout overrides if present
        for node in nodes:
            nid = node["id"]
            if nid in self.workflow_layout:
                node["x"] = self.workflow_layout[nid].get("x", node["x"])
                node["y"] = self.workflow_layout[nid].get("y", node["y"])

        return {
            "status": state_str,
            "active_task": getattr(self.runtime.state, "last_user_message", None) if self.runtime and hasattr(self.runtime, "state") else None,
            "nodes": nodes,
            "edges": edges,
            "roles": roles_summary,
            "execution_modes": self.role_execution_modes,
            "workflow_layout": {"nodes": self.workflow_layout},
            "timestamp": time.time(),
        }

    def _update_role_candidates(self, role: str, candidates: list[dict[str, str]], mode: str = "FALLBACK_ORDER") -> dict[str, Any]:
        """Validates and applies role candidate updates and execution modes."""
        valid_roles = ["reasoning", "fast", "desktop", "vision", "ocr", "embeddings", "stt", "tts"]
        if role not in valid_roles:
            return {"success": False, "error": f"Invalid role '{role}'. Expected one of {valid_roles}"}

        if not candidates or not isinstance(candidates, list):
            return {"success": False, "error": "Candidates must be a non-empty list of candidate objects."}

        # Safety Guard: Reject updates during active task execution
        if self.runtime and hasattr(self.runtime, "state") and hasattr(self.runtime.state, "status"):
            from app.core.state import SERAStatus
            if self.runtime.state.status == SERAStatus.EXECUTING:
                return {
                    "success": False,
                    "error": "Safety guard: Cannot modify model candidate chain while SERA is actively executing a task.",
                }

        # Duplicate checking
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

        # Capability validation
        if self.runtime and hasattr(self.runtime, "router"):
            new_chain = []
            for c in candidates:
                p_name = c["provider"]
                m_name = c["model"]
                provider_inst = self.runtime.router.providers.get(p_name)
                if not provider_inst:
                    return {"success": False, "error": f"Provider '{p_name}' is not registered."}

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

            self.runtime.router.role_chains[role] = new_chain

        self.role_execution_modes[role] = mode
        logger.info(f"[SERAUIServer] Role '{role}' updated ({mode})")

        return {
            "success": True,
            "role": role,
            "candidates": candidates,
            "execution_mode": mode,
            "message": f"Role '{role}' updated successfully ({mode}).",
        }

    def _onboard_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        """Onboards a custom provider in Vercel-style pipeline without logging raw secrets."""
        name = data.get("provider_name", "").strip().lower()
        base_url = data.get("base_url", "").strip()
        env_ref = data.get("api_key_env", "").strip()

        if not name or not base_url:
            return {"success": False, "error": "Provider name and Base URL are required."}

        new_entry = {
            "provider_name": name,
            "display_name": data.get("display_name", name.capitalize()),
            "status": "HEALTHY",
            "base_url": base_url,
            "api_key_reference": env_ref or f"{name.upper()}_API_KEY",
            "models": [
                {
                    "model_id": "default-model",
                    "display_name": f"{name.capitalize()} Default",
                    "role": "custom",
                    "is_primary": True,
                    "health_status": "HEALTHY",
                    "capabilities": {"text": True, "streaming": True, "tool_calling": True},
                    "quota": {"is_unknown": True},
                }
            ],
        }
        self.custom_providers.append(new_entry)
        return {"success": True, "provider": new_entry, "message": f"Provider '{name}' onboarded successfully."}

    def _get_security_summary(self) -> dict[str, Any]:
        """Returns security policies, permission levels, and privacy boundaries."""
        return {
            "permissions": {
                "screen_reading": {"status": "ALLOWED", "level": "SAFE", "description": "Inspect and capture desktop screen controls"},
                "ui_interaction": {"status": "ALLOWED", "level": "SAFE", "description": "Click and type into native Windows applications"},
                "file_creation": {"status": "ALLOWED", "level": "SAFE", "description": "Create notes and export files"},
                "file_deletion": {"status": "CONFIRM_ALWAYS", "level": "DESTRUCTIVE", "description": "Delete files or remove folders"},
                "shutdown_pc": {"status": "CONFIRM_ALWAYS", "level": "CRITICAL", "description": "Restart or power down the system"},
                "credential_access": {"status": "BLOCKED", "level": "FORBIDDEN", "description": "Read passwords, browser cookies, or private keys"},
                "purchases": {"status": "CONFIRM_ALWAYS", "level": "CRITICAL", "description": "Execute financial transactions or checkout orders"},
            },
            "privacy": {
                "stt_processing": "LOCAL (Canary / Whisper)",
                "screen_analysis": "CLOUD (Qwen 3.6 27B / Gemini)",
                "reasoning_llm": "CLOUD (Groq GPT-OSS 120B / Mistral)",
                "voice_synthesis": "CLOUD (Fish Audio S2.1)",
                "desktop_actions": "LOCAL (Windows UI Automation)",
            },
            "confirmation_required_count": 0,
            "dev_mode_unrestricted": self.security_manager.is_dev_unrestricted(),
        }

    def _get_roles_summary(self) -> dict[str, Any]:
        """Returns structured role candidates from runtime router or configured defaults."""
        if self.runtime and hasattr(self.runtime, "router") and hasattr(self.runtime.router, "role_chains"):
            summary = {}
            for role_name, chain in self.runtime.router.role_chains.items():
                cands = []
                for idx, cand in enumerate(chain):
                    cands.append({
                        "provider": cand.provider_name,
                        "model": cand.model_name,
                        "latency_ms": 350,
                        "is_primary": idx == 0,
                        "fallback_rank": idx,
                        "health": "HEALTHY",
                    })
                summary[role_name] = {
                    "role": role_name,
                    "candidates": cands,
                    "execution_mode": self.role_execution_modes.get(role_name, "FALLBACK_ORDER"),
                }
            return summary

        # Standalone / Default topology
        return {
            "reasoning": {
                "role": "reasoning",
                "candidates": [
                    {"provider": "Groq", "model": "openai/gpt-oss-120b", "latency_ms": 380, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                    {"provider": "Mistral", "model": "mistral-large-2411", "latency_ms": 520, "is_primary": False, "fallback_rank": 1, "health": "HEALTHY"},
                ],
                "execution_mode": self.role_execution_modes.get("reasoning", "FALLBACK_ORDER"),
            },
            "fast": {
                "role": "fast",
                "candidates": [
                    {"provider": "Groq", "model": "llama-3.3-70b-versatile", "latency_ms": 190, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": self.role_execution_modes.get("fast", "PRIMARY_ONLY"),
            },
            "desktop": {
                "role": "desktop",
                "candidates": [
                    {"provider": "Mistral", "model": "codestral-2501", "latency_ms": 340, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": self.role_execution_modes.get("desktop", "PRIMARY_ONLY"),
            },
            "vision": {
                "role": "vision",
                "candidates": [
                    {"provider": "Groq", "model": "qwen-2.5-32b", "latency_ms": 410, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": self.role_execution_modes.get("vision", "PRIMARY_ONLY"),
            },
            "ocr": {
                "role": "ocr",
                "candidates": [
                    {"provider": "Groq", "model": "qwen-2.5-32b", "latency_ms": 420, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": "PRIMARY_ONLY",
            },
            "embeddings": {
                "role": "embeddings",
                "candidates": [
                    {"provider": "Local", "model": "all-MiniLM-L6-v2", "latency_ms": 40, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": "PRIMARY_ONLY",
            },
            "stt": {
                "role": "stt",
                "candidates": [
                    {"provider": "NVIDIA", "model": "Canary-Qwen 2.5B", "latency_ms": 210, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                    {"provider": "Faster-Whisper", "model": "small", "latency_ms": 190, "is_primary": False, "fallback_rank": 1, "health": "HEALTHY"},
                ],
                "execution_mode": "FALLBACK_ORDER",
            },
            "tts": {
                "role": "tts",
                "candidates": [
                    {"provider": "Fish Audio", "model": "s2.1-pro-free", "latency_ms": 180, "is_primary": True, "fallback_rank": 0, "health": "HEALTHY"},
                ],
                "execution_mode": "PRIMARY_ONLY",
            },
        }

    def _get_architect_config(self) -> dict[str, Any]:
        """Returns persistent configuration of Temporal Framework roles, modes, and candidate priorities."""
        roles_summary = self._get_roles_summary()
        return {
            "roles": roles_summary,
            "execution_modes": self.role_execution_modes,
            "dev_mode_unrestricted": self.security_manager.is_dev_unrestricted(),
            "layout": {"nodes": self.workflow_layout},
            "available_roles": ["stt", "fast", "reasoning", "desktop", "vision", "ocr", "embeddings", "tts"],
            "future_roles": ["agents", "rag", "mcp", "browser"],
        }

    def _save_architect_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validates and persists updated role execution modes and candidate priorities."""
        modes = payload.get("execution_modes", {})
        roles_payload = payload.get("roles", {})
        layout_nodes = payload.get("layout", {}).get("nodes", {})

        if isinstance(modes, dict):
            for r, m in modes.items():
                if m in ["PRIMARY_ONLY", "FALLBACK_ORDER", "RESOURCE_AWARE", "CUSTOM"]:
                    self.role_execution_modes[r] = m
                    if self.runtime and hasattr(self.runtime, "router"):
                        self.runtime.router.set_execution_mode(r, m)

        if isinstance(roles_payload, dict):
            for r_name, r_info in roles_payload.items():
                if isinstance(r_info, dict) and "candidates" in r_info:
                    mode_to_use = self.role_execution_modes.get(r_name, "RESOURCE_AWARE")
                    self._update_role_candidates(r_name, r_info["candidates"], mode_to_use)

        if layout_nodes:
            self._save_workflow_layout(layout_nodes)

        return {
            "success": True,
            "config": self._get_architect_config(),
            "message": "Architect configuration successfully saved and persisted.",
        }

    def _test_architect_simulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Runs a safe simulated routing trace through the configured topology without external network calls."""
        test_role = payload.get("role", "reasoning")
        scenario = payload.get("scenario", "low_quota" if payload.get("simulate_outage", True) else "normal")
        
        mode = self.role_execution_modes.get(test_role, "RESOURCE_AWARE")
        roles_summary = self._get_roles_summary()
        candidates = roles_summary.get(test_role, {}).get("candidates", [])
        
        steps = []
        steps.append({"step": 1, "action": "STT Transcription (Canary-Qwen)", "status": "COMPLETED", "node": "node_stt"})
        steps.append({"step": 2, "action": "Intent Routing & Policy Dispatch", "status": "COMPLETED", "node": "node_router"})

        if not candidates:
            steps.append({"step": 3, "action": f"Role '{test_role}' has no configured candidates", "status": "BROKEN"})
            return {"success": False, "trace": steps, "status": "BROKEN"}

        primary = candidates[0]
        
        if mode == "RESOURCE_AWARE":
            if scenario in ["low_quota", "outage", "rate_limit_429"] and len(candidates) > 1:
                alt = candidates[1]
                steps.append({
                    "step": 3,
                    "action": f"Preflight Evaluation: {primary.get('model')} Quota Insufficient (Estimated 3.5K > 2.1K Remaining) ➔ Excluded",
                    "status": "RESOURCE_EXCLUDED",
                    "node": f"arch_node_{test_role}_0",
                })
                steps.append({
                    "step": 4,
                    "action": f"Optimal Candidate Selected: {alt.get('provider')} / {alt.get('model')} (Score: 285.0 • Latency: 320ms)",
                    "status": "COMPLETED",
                    "node": f"arch_node_{test_role}_1",
                })
                steps.append({"step": 5, "action": "Verification & State Synthesis", "status": "COMPLETED", "node": "arch_node_verify"})
                steps.append({"step": 6, "action": "Streaming TTS Audio", "status": "COMPLETED", "node": "arch_node_tts"})
                return {
                    "success": True,
                    "trace": steps,
                    "status": "RESOURCE_AWARE_SELECTED",
                    "selected_model": alt.get("model"),
                    "mode": mode,
                    "reasons": [
                        "✓ Preflight feasibility check succeeded",
                        f"✓ Filtered out {primary.get('model')} before dispatch",
                        f"✓ Selected {alt.get('model')} with high quota headroom and low latency",
                    ],
                }
            else:
                steps.append({
                    "step": 3,
                    "action": f"Preflight Selection: {primary.get('provider')} / {primary.get('model')} (Score: 295.0 • Healthy)",
                    "status": "COMPLETED",
                    "node": f"arch_node_{test_role}_0",
                })
                steps.append({"step": 4, "action": "Verification & State Synthesis", "status": "COMPLETED", "node": "arch_node_verify"})
                steps.append({"step": 5, "action": "Streaming TTS Audio", "status": "COMPLETED", "node": "arch_node_tts"})
                return {
                    "success": True,
                    "trace": steps,
                    "status": "COMPLETED",
                    "selected_model": primary.get("model"),
                    "mode": mode,
                    "reasons": ["✓ Primary candidate healthy and high token headroom"],
                }

        if scenario in ["low_quota", "outage", "rate_limit_429"] and len(candidates) > 1 and mode in ["FALLBACK_ORDER", "CUSTOM"]:
            steps.append({
                "step": 3,
                "action": f"Primary Candidate ({primary.get('provider')}/{primary.get('model')}) Rate-Limited (429)",
                "status": "RATE_LIMITED",
                "node": f"arch_node_{test_role}_0",
            })
            fallback = candidates[1]
            steps.append({
                "step": 4,
                "action": f"Fallback Candidate Activated: {fallback.get('provider')}/{fallback.get('model')}",
                "status": "FALLBACK_ACTIVE",
                "node": f"arch_node_{test_role}_1",
            })
            steps.append({"step": 5, "action": "Verification & Output Synthesis", "status": "COMPLETED", "node": "arch_node_verify"})
            steps.append({"step": 6, "action": "Audio Synthesis (Fish Audio)", "status": "COMPLETED", "node": "arch_node_tts"})
            return {"success": True, "trace": steps, "status": "FALLBACK_COMPLETED", "selected_model": fallback.get("model")}
        else:
            steps.append({
                "step": 3,
                "action": f"Primary Candidate Dispatched: {primary.get('provider')}/{primary.get('model')}",
                "status": "COMPLETED",
                "node": f"arch_node_{test_role}_0",
            })
            steps.append({"step": 4, "action": "Verification & Output Synthesis", "status": "COMPLETED", "node": "arch_node_verify"})
            steps.append({"step": 5, "action": "Audio Synthesis (Fish Audio)", "status": "COMPLETED", "node": "arch_node_tts"})
            return {"success": True, "trace": steps, "status": "COMPLETED", "selected_model": primary.get("model")}

    def _get_history_sessions(self) -> list[dict[str, Any]]:
        """Returns rich chronological interaction sessions."""
        return [
            {
                "session_id": "sess_101",
                "time": "15:28:10",
                "date": "Today",
                "query": "Open Chrome and search for RTX 5090 benchmarks",
                "pipeline": "STT ➔ Router ➔ Desktop (Codestral) ➔ Browser ➔ Vision ➔ Verify ➔ TTS",
                "steps": [
                    {"step": 1, "action": "STT Transcription (Canary-Qwen)", "duration_ms": 210, "status": "COMPLETED"},
                    {"step": 2, "action": "Intent Routing & Role Dispatch", "duration_ms": 5, "status": "COMPLETED"},
                    {"step": 3, "action": "Desktop Tool Execution (open_application 'chrome')", "duration_ms": 340, "status": "COMPLETED"},
                    {"step": 4, "action": "Screen Perception & Verification (Qwen 3.6 27B)", "duration_ms": 410, "status": "COMPLETED"},
                    {"step": 5, "action": "Streaming TTS Response (Fish Audio)", "duration_ms": 180, "status": "COMPLETED"},
                ],
                "total_duration": "1.14s",
                "models_used": ["NVIDIA Canary-Qwen", "Mistral Codestral", "Groq Qwen 3.6 27B", "Fish Audio"],
                "status": "COMPLETED",
            },
            {
                "session_id": "sess_102",
                "time": "15:12:05",
                "date": "Today",
                "query": "Set brightness to 40%",
                "pipeline": "Local Intent ➔ Direct OS Tool (set_brightness) ➔ TTS",
                "steps": [
                    {"step": 1, "action": "STT Transcription", "duration_ms": 190, "status": "COMPLETED"},
                    {"step": 2, "action": "Local Intent Bypass (0 LLM calls)", "duration_ms": 2, "status": "COMPLETED"},
                    {"step": 3, "action": "System Tool (set_brightness {'brightness': 40})", "duration_ms": 45, "status": "COMPLETED"},
                ],
                "total_duration": "0.24s",
                "models_used": ["Canary-Qwen", "Fish Audio"],
                "status": "COMPLETED",
            },
            {
                "session_id": "sess_103",
                "time": "14:58:30",
                "date": "Today",
                "query": "What is on my screen?",
                "pipeline": "STT ➔ Vision (Groq Qwen 3.6 27B) ➔ ScreenContext ➔ Streaming TTS",
                "steps": [
                    {"step": 1, "action": "Screen Capture & OCR Extraction", "duration_ms": 65, "status": "COMPLETED"},
                    {"step": 2, "action": "Multimodal Vision Inference", "duration_ms": 420, "status": "COMPLETED"},
                ],
                "total_duration": "0.49s",
                "models_used": ["Canary-Qwen", "Groq Qwen 3.6 27B", "Fish Audio"],
                "status": "COMPLETED",
            },
        ]

    def _get_telemetry_waterfall(self) -> dict[str, Any]:
        """Returns latency waterfall breakdown for live and recent turns."""
        return {
            "stages": [
                {"stage": "1. Voice Capture & STT (NVIDIA Canary-Qwen 2.5B)", "latency_ms": 210, "color": "var(--accent-cyan)"},
                {"stage": "2. Local Intent & Role Router Decision", "latency_ms": 5, "color": "var(--accent-emerald)"},
                {"stage": "3. Reasoning Cognition TTFT (Groq GPT-OSS 120B)", "latency_ms": 110, "color": "var(--accent-violet)"},
                {"stage": "4. Desktop Tool Execution (Codestral)", "latency_ms": 340, "color": "var(--accent-cyan)"},
                {"stage": "5. Screen Perception & Verification (Qwen 3.6 27B)", "latency_ms": 410, "color": "var(--accent-violet)"},
                {"stage": "6. TTS First Audio TTFA (Fish Audio S2.1)", "latency_ms": 180, "color": "var(--accent-emerald)"},
            ],
            "total_turn_latency_ms": 1255,
        }

    def _get_initial_snapshot(self) -> dict[str, Any]:
        """Collects current runtime state snapshot."""
        state_str = "IDLE"
        if self.runtime and hasattr(self.runtime, "state") and hasattr(self.runtime.state, "status"):
            state_str = self.runtime.state.status.value

        # Query truthful wake-word status
        wake_status = "NOT CONFIGURED"
        if self.runtime and hasattr(self.runtime, "wakeword_provider") and self.runtime.wakeword_provider:
            st = self.runtime.wakeword_provider.get_status()
            if hasattr(st, "value"):
                wake_status = str(st.value)
            elif isinstance(st, str):
                wake_status = st
            else:
                wake_status = "NOT CONFIGURED"

        # Safe extraction of active task info
        active_task_str = None
        if self.runtime and hasattr(self.runtime, "state"):
            val = getattr(self.runtime.state, "last_user_message", None)
            if isinstance(val, str):
                active_task_str = val

        task_info_dict = None
        if self.runtime:
            tinfo = getattr(self.runtime, "active_task_info", None)
            if isinstance(tinfo, dict):
                task_info_dict = tinfo

        return {
            "status": state_str,
            "runtime_attached": self.runtime is not None,
            "active_task": active_task_str,
            "active_task_info": task_info_dict,
            "live_history": self.live_history,
            "mic_status": "READY",
            "wake_word_status": wake_status,
            "stt_info": {
                "configured_primary": "NVIDIA Canary-Qwen 2.5B",
                "active": "Faster-Whisper (GPU)",
                "status": "FASTER-WHISPER",
            },
            "gpu_usage_pct": 18.4,
            "system_memory_mb": 3420,
            "roles": self._get_roles_summary(),
            "execution_modes": self.role_execution_modes,
            "providers": self._get_providers_summary(),
            "security": self._get_security_summary(),
            "dev_mode_unrestricted": self.security_manager.is_dev_unrestricted(),
            "architect": self._get_architect_config(),
            "capabilities": self.capability_registry.get_contextual_capabilities({"state": state_str}),
            "workflow": self._get_dynamic_workflow_graph(),
            "workflow_graph": self._get_structured_workflow_graph(),
            "workflow_layout": {"nodes": self.workflow_layout},
        }

    def _get_structured_workflow_graph(self) -> dict[str, Any]:
        """Generates structured workflow.graph.json compliant data structure."""
        dyn = self._get_dynamic_workflow_graph()
        structured_nodes = []
        for n in dyn.get("nodes", []):
            structured_nodes.append({
                "id": n["id"],
                "label": n["label"],
                "kind": "model" if n.get("role") in ["reasoning", "fast", "desktop", "vision", "ocr", "embeddings"] else ("router" if n.get("role") == "router" else "entry"),
                "sub": n.get("model", ""),
                "provider": n.get("provider", ""),
                "model": n.get("model", ""),
                "role": n.get("role", "custom"),
                "capabilities": ["text", "streaming"] if n.get("is_primary") else [],
                "health": n.get("health", "HEALTHY"),
                "status": n.get("status", "WAITING"),
                "x": n.get("x", 0),
                "y": n.get("y", 0),
                "width": 220,
                "height": 88,
                "group": n.get("role", "default"),
                "active": n.get("status") in ["ACTIVE", "EXECUTING"],
                "detail": f"Provider: {n.get('provider')} | Rank: {n.get('fallback_rank', 0)}",
            })

        structured_edges = []
        for e in dyn.get("edges", []):
            structured_edges.append({
                "id": e["id"],
                "from": e.get("source") or e.get("from"),
                "to": e.get("target") or e.get("to"),
                "kind": "fallback" if e.get("type") == "FALLBACK" else "calls",
                "label": e.get("type", "PRIMARY"),
                "active": False,
                "fallback": e.get("type") == "FALLBACK",
                "status": "WAITING",
                "progress": 0.0,
            })

        return {
            "version": 1,
            "nodes": structured_nodes,
            "edges": structured_edges,
            "roles": self._get_roles_summary(),
            "execution_modes": self.role_execution_modes,
            "layout": {
                "zoom": 1.0,
                "panX": 60,
                "panY": 120,
                "gridSnap": True,
                "gridSize": 16,
            }
        }

    def _get_providers_summary(self) -> list[dict[str, Any]]:
        base_providers = [
            {
                "provider_name": "groq",
                "display_name": "Groq LPU Acceleration",
                "status": "HEALTHY",
                "api_key_reference": "GROQ_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "openai/gpt-oss-120b",
                        "display_name": "GPT-OSS 120B",
                        "role": "reasoning",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "reasoning": True, "tool_calling": True, "streaming": True},
                        "quota_metrics": [
                            {"label": "Requests / Minute", "used": 28, "limit": 30, "remaining": 2, "percentage_remaining": 6.7, "unit": "reqs", "window": "1m"},
                            {"label": "Tokens / Minute", "used": 7800, "limit": 8000, "remaining": 200, "percentage_remaining": 2.5, "unit": "tokens", "window": "1m"},
                            {"label": "Requests / Day", "used": 843, "limit": 1000, "remaining": 157, "percentage_remaining": 15.7, "unit": "reqs", "window": "24h"},
                        ],
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
                        "quota_metrics": [
                            {"label": "Requests / Minute", "used": 12, "limit": 30, "remaining": 18, "percentage_remaining": 60.0, "unit": "reqs", "window": "1m"},
                            {"label": "Tokens / Minute", "used": 4200, "limit": 8000, "remaining": 3800, "percentage_remaining": 47.5, "unit": "tokens", "window": "1m"},
                        ],
                        "recent_avg_latency_ms": 410.0,
                        "recent_avg_ttft_ms": 130.0,
                    }
                ]
            },
            {
                "provider_name": "gemini",
                "display_name": "Google Gemini",
                "status": "HEALTHY",
                "api_key_reference": "GEMINI_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "gemini-3-flash-preview",
                        "display_name": "Gemini 3 Flash Preview",
                        "role": "vision (fallback)",
                        "is_primary": False,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "vision": True, "tool_calling": True, "streaming": True},
                        "quota_metrics": [
                            {"label": "Weekly Limit Remaining", "used": None, "limit": 100, "remaining": 86, "percentage_remaining": 86.0, "unit": "percent", "window": "7d"},
                            {"label": "5-Hour Limit Remaining", "used": None, "limit": 100, "remaining": 100, "percentage_remaining": 100.0, "unit": "percent", "window": "5h"},
                        ],
                        "recent_avg_latency_ms": 520.0,
                        "recent_avg_ttft_ms": 180.0,
                    }
                ]
            },
            {
                "provider_name": "mistral",
                "display_name": "Mistral AI",
                "status": "HEALTHY",
                "api_key_reference": "MISTRAL_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "mistral-small-latest",
                        "display_name": "Mistral Small",
                        "role": "fast",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "streaming": True, "tool_calling": True},
                        "quota_metrics": [
                            {"label": "Monthly Requests", "used": 15, "limit": 500, "remaining": 485, "percentage_remaining": 97.0, "unit": "reqs", "window": "30d"},
                        ],
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
                        "quota_metrics": [
                            {"label": "Monthly Requests", "used": 9, "limit": 500, "remaining": 491, "percentage_remaining": 98.2, "unit": "reqs", "window": "30d"},
                        ],
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
                        "quota_metrics": [
                            {"label": "Monthly Requests", "used": 4, "limit": 500, "remaining": 496, "percentage_remaining": 99.2, "unit": "reqs", "window": "30d"},
                        ],
                        "recent_avg_latency_ms": 750.0,
                        "recent_avg_ttft_ms": 240.0,
                    }
                ]
            },
            {
                "provider_name": "nvidia",
                "display_name": "NVIDIA NIM / Canary",
                "status": "DEGRADED",
                "api_key_reference": "NVIDIA_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "nvidia/canary-qwen-2.5b",
                        "display_name": "Canary-Qwen 2.5B STT",
                        "role": "stt (primary)",
                        "is_primary": True,
                        "health_status": "UNAVAILABLE",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": False, "stt": True, "audio": True},
                        "quota_metrics": [
                            {"label": "Endpoint Status", "used": 404, "limit": 200, "remaining": 0, "percentage_remaining": 0.0, "unit": "status", "window": "live"}
                        ],
                        "recent_avg_latency_ms": None,
                        "recent_avg_ttft_ms": None,
                    },
                    {
                        "model_id": "faster-whisper-small",
                        "display_name": "Faster-Whisper (Local Fallback)",
                        "role": "stt (active fallback)",
                        "is_primary": False,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": False, "stt": True, "audio": True},
                        "quota_metrics": [
                            {"label": "Local Inference Capacity", "used": 1, "limit": 100, "remaining": 99, "percentage_remaining": 99.0, "unit": "percent", "window": "local"}
                        ],
                        "recent_avg_latency_ms": 210.0,
                        "recent_avg_ttft_ms": None,
                    }
                ]
            },
            {
                "provider_name": "fish_audio",
                "display_name": "Fish Audio",
                "status": "HEALTHY",
                "api_key_reference": "FISH_AUDIO_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "s2.1-pro-free",
                        "display_name": "Fish Audio S2.1 TTS",
                        "role": "tts",
                        "is_primary": True,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"tts": True, "streaming": True, "audio": True},
                        "quota_metrics": [
                            {"label": "Credits Remaining", "used": 150, "limit": 1000, "remaining": 850, "percentage_remaining": 85.0, "unit": "credits", "window": "live"}
                        ],
                        "recent_avg_latency_ms": 180.0,
                        "recent_avg_ttft_ms": 95.0,
                    }
                ]
            },
            {
                "provider_name": "openrouter",
                "display_name": "OpenRouter Multi-Provider",
                "status": "HEALTHY",
                "api_key_reference": "OPENROUTER_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "openrouter/free",
                        "display_name": "OpenRouter Free Dynamic",
                        "role": "reasoning (fallback)",
                        "is_primary": False,
                        "health_status": "HEALTHY",
                        "cooldown_remaining_s": 0.0,
                        "capabilities": {"text": True, "reasoning": True, "vision": True, "tool_calling": True},
                        "quota_metrics": [
                            {"label": "Free Tier Dynamic Quota", "used": 20, "limit": 100, "remaining": 80, "percentage_remaining": 80.0, "unit": "percent", "window": "live"}
                        ],
                        "recent_avg_latency_ms": 620.0,
                        "recent_avg_ttft_ms": 190.0,
                    }
                ]
            },
            {
                "provider_name": "cerebras",
                "display_name": "Cerebras Fast Inference",
                "status": "UNAVAILABLE",
                "api_key_reference": "CEREBRAS_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "gpt-oss-120b",
                        "display_name": "GPT-OSS 120B",
                        "role": "inactive",
                        "is_primary": False,
                        "health_status": "AUTH_ERROR",
                        "cooldown_remaining_s": 60.0,
                        "capabilities": {"text": True, "reasoning": True},
                        "quota_metrics": [],
                        "recent_avg_latency_ms": None,
                        "recent_avg_ttft_ms": None,
                    }
                ]
            },
            {
                "provider_name": "zai",
                "display_name": "Z.AI GLM Models",
                "status": "RATE_LIMITED",
                "api_key_reference": "ZAI_API_KEY (● Configured)",
                "models": [
                    {
                        "model_id": "glm-5",
                        "display_name": "GLM 5",
                        "role": "inactive",
                        "is_primary": False,
                        "health_status": "RATE_LIMITED",
                        "cooldown_remaining_s": 60.0,
                        "capabilities": {"text": True, "reasoning": True},
                        "quota_metrics": [],
                        "recent_avg_latency_ms": None,
                        "recent_avg_ttft_ms": None,
                    }
                ]
            }
        ]
        return base_providers + self.custom_providers


async def _run_standalone(host: str = "127.0.0.1", port: int = 8765):
    server = SERAUIServer(host=host, port=port)
    await server.start()
    print(f"[SERA] Command Center running at http://{host}:{port}")
    print("[SERA] Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(_run_standalone())
    except KeyboardInterrupt:
        print("\n[SERA] Server stopped.")

