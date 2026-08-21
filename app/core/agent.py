import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from app.core.events import EventBus
from app.core.router import ModelRouter
from app.core.state import SERAState, SERAStatus
from app.models.llm.base import LLMResponse
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class SERAAgent:
    """Core SERA Agent with deterministic turn termination contract, conversational fast-path,
    and duplicate tool call execution protection."""

    SYSTEM_PROMPT = """You are SERA, a personal AI desktop assistant running on the user's Windows PC.

LANGUAGE:
- Always communicate in English.
- The user's spoken language is English.
- Never switch to another language unless explicitly requested.
- If the input contains ambiguous or incorrectly transcribed words, interpret them in the context of English.

VOICE ASSISTANT BEHAVIOR:
- Be concise, natural, and conversational.
- Normally respond in 1-2 sentences.
- Avoid markdown formatting, asterisks, bullet lists, and tables in spoken responses.
- Do not use emojis in spoken responses.
- Do not output code unless explicitly requested.

PC CONTROL:
- Always call the corresponding tool whenever the user asks to perform an action (including open/close apps, diagnostics, wifi, audio, brightness, restart, or shutdown).
- Invoke the tool immediately and the safety system will handle confirmation if needed.
- Once a tool completes successfully, summarize the result in one short sentence and finish. Do not call the same tool again.
- If a tool fails, explain that the action failed.

IDENTITY:
- Your name is SERA.
- You are a desktop AI assistant running locally on the user's Windows computer.
"""

    GREETING_PATTERNS = {
        "hi", "hello", "hey", "hey sera", "hello sera", "hi sera",
        "good morning", "good afternoon", "good evening",
        "how are you", "how are you doing", "what's up", "whats up",
        "thank you", "thanks", "thanks sera", "who are you", "what can you do",
    }

    def __init__(
        self,
        router: ModelRouter,
        tools: ToolRegistry,
        state: SERAState | None = None,
        event_bus: EventBus | None = None,
        max_turn_timeout_seconds: float = 30.0,
    ):
        self.router = router
        self.tools = tools
        self.state = state or SERAState()
        self.event_bus = event_bus or EventBus()
        self.max_turn_timeout_seconds = max_turn_timeout_seconds
        self.conversation: list[dict[str, Any]] = []
        self._turn_executed_tools: set[str] = set()

    def is_conversational_fast_path(self, message: str) -> bool:
        """Determines if a message is a greeting or quick query that bypasses tool planning."""
        cleaned = message.lower().strip().rstrip(".!?")
        if cleaned in self.GREETING_PATTERNS:
            return True
        if any(cleaned.startswith(f"{g} ") or cleaned.endswith(f" {g}") for g in ("hi", "hello", "hey", "thanks")):
            return True
        return False

    async def run(
        self,
        user_message: str,
        preferred_role: str | None = None,
        turn_id: str | None = None,
    ) -> str:
        """Executes a complete agent turn with deterministic completion guarantee."""
        turn_id = turn_id or f"turn-{int(time.time() * 1000)}"
        self._turn_executed_tools.clear()

        self.state.transition_to(SERAStatus.THINKING)
        self.state.last_user_message = user_message

        try:
            return await asyncio.wait_for(
                self._run_internal(user_message, preferred_role=preferred_role, turn_id=turn_id),
                timeout=self.max_turn_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[SERAAgent] Task timed out after {self.max_turn_timeout_seconds}s.")
            self.state.transition_to(SERAStatus.BROKEN)
            timeout_msg = "Task exceeded safety timeout limit."
            self.state.last_response = timeout_msg
            return timeout_msg

    async def _run_internal(
        self,
        user_message: str,
        preferred_role: str | None = None,
        turn_id: str = "turn-0",
    ) -> str:
        # -------------------------------------------------------------
        # Route 1: Conversational Fast-Path (0 Tools, 1 Round)
        # -------------------------------------------------------------
        if self.is_conversational_fast_path(user_message):
            self.state.active_model_role = "fast"
            fast_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            response, _ = await self.router.generate_with_fallback(
                messages=fast_messages,
                tools=[],
                preferred_role="fast",
            )
            final_text = response.text.strip() or "Hello! How can I help you today?"
            self.state.last_response = final_text
            self.state.active_tool_name = None
            return final_text

        # -------------------------------------------------------------
        # Route 2: Standard Reasoning & Tool Execution Loop
        # -------------------------------------------------------------
        self.conversation = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        if not preferred_role:
            preferred_role = self.router.select_role_for_task(user_message)

        self.state.active_model_role = preferred_role

        response, active_role = await self.router.generate_with_fallback(
            messages=self.conversation,
            tools=self.tools.schemas(),
            preferred_role=preferred_role,
        )

        max_tool_rounds = 3
        round_count = 0

        while response.has_tool_calls and round_count < max_tool_rounds:
            round_count += 1
            self.state.transition_to(SERAStatus.EXECUTING)

            executed_any_new_tool = False

            for tool_call in response.tool_calls:
                self.state.active_tool_name = tool_call.name
                args_dict = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
                tool_sig = f"{turn_id}:{tool_call.name}:{json.dumps(args_dict, sort_keys=True)}"

                # Duplicate Tool Call Guard
                if tool_sig in self._turn_executed_tools:
                    logger.warning(f"[SERAAgent] Blocked duplicate tool invocation: {tool_sig}")
                    continue

                self._turn_executed_tools.add(tool_sig)
                executed_any_new_tool = True

                print(f"\n[SERA TOOL] {tool_call.name}")
                print(f"[ARGUMENTS] {tool_call.arguments}")

                # Check if tool requires explicit user confirmation
                tool_instance = self.tools.get(tool_call.name)
                if tool_instance and getattr(tool_instance, "requires_confirmation", False) is True:
                    prompt = getattr(
                        tool_instance,
                        "confirmation_prompt",
                        f"Are you sure you want to execute {tool_call.name}?",
                    )
                    self.state.set_pending_confirmation(
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments,
                        prompt=str(prompt),
                    )
                    return str(prompt)

                # Execute tool
                result = await self.tools.execute(
                    tool_call.name,
                    tool_call.arguments,
                )
                self.state.last_tool_result = result
                print(f"[RESULT] {result}")

                # Deterministic Single-Step Fast Finish
                # If a deterministic action (like open_application or set_brightness) succeeded, stop immediately
                if tool_call.name in ("open_application", "close_application", "set_brightness", "set_volume", "mute_system", "unmute_system"):
                    if isinstance(result, dict) and result.get("success", False):
                        if tool_call.name == "open_application":
                            app_name = args_dict.get("app_name") or args_dict.get("application", "Application")
                            final_resp = f"Opened {app_name.capitalize()}."
                        elif tool_call.name == "close_application":
                            app_name = args_dict.get("app_name") or args_dict.get("application", "Application")
                            final_resp = f"Closed {app_name.capitalize()}."
                        else:
                            final_resp = str(result.get("message") or "Action completed.")

                        self.state.last_response = final_resp
                        self.state.active_tool_name = None
                        return final_resp

                args_str = json.dumps(args_dict) if isinstance(args_dict, (dict, list)) else str(args_dict)

                self.conversation.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": args_str,
                                },
                            }
                        ],
                    }
                )

                self.conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                    }
                )

            if not executed_any_new_tool:
                # No new tools to execute; break tool loop to avoid infinite stalls
                break

            # Continue conversation with tool outputs
            response, _ = await self.router.generate_with_fallback(
                messages=self.conversation,
                tools=self.tools.schemas(),
                preferred_role=active_role,
            )

        final_text = response.text.strip() or "I have completed the task."
        self.state.last_response = final_text
        self.state.active_tool_name = None
        return final_text

    async def run_stream(
        self,
        user_message: str,
        preferred_role: str | None = None,
        metrics=None,
        turn_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Streams response tokens from LLM, routing conversational/action commands directly."""
        turn_id = turn_id or f"turn-{int(time.time() * 1000)}"
        self.state.transition_to(SERAStatus.THINKING)
        self.state.last_user_message = user_message

        # Conversational Fast Path or Explicit Action -> run() directly
        msg_lower = user_message.lower().strip()
        action_prefixes = (
            "open ", "close ", "launch ", "start ", "stop ", "kill ",
            "restart ", "shutdown ", "sleep ", "lock ", "set brightness",
            "set volume", "mute", "unmute", "wifi status", "battery status",
            "cpu usage", "memory usage", "disk usage", "what time is it", "current time",
        )

        if self.is_conversational_fast_path(user_message) or any(msg_lower.startswith(p) for p in action_prefixes):
            full_response = await self.run(user_message, preferred_role=preferred_role, turn_id=turn_id)
            yield full_response
            return

        # General stream reasoning
        self.conversation = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        if not preferred_role:
            preferred_role = self.router.select_role_for_task(user_message)

        self.state.active_model_role = preferred_role

        if metrics:
            metrics.llm_request_started_at = time.time()

        first_token = True
        accumulated_tokens: list[str] = []

        try:
            async for token, role in self.router.generate_stream_with_fallback(
                messages=self.conversation,
                tools=self.tools.schemas(),
                preferred_role=preferred_role,
            ):
                if first_token:
                    first_token = False
                    if metrics:
                        metrics.llm_first_token_at = time.time()

                accumulated_tokens.append(token)
                yield token

            final_text = "".join(accumulated_tokens).strip()
            if metrics:
                metrics.llm_completed_at = time.time()

            self.state.last_response = final_text
            self.state.active_tool_name = None

        except Exception as e:
            logger.info(f"[SERAAgent] Streaming fallback to full tool loop execution: {e}")
            full_response = await self.run(user_message, preferred_role=preferred_role, turn_id=turn_id)
            yield full_response