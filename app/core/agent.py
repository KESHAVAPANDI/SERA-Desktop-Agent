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
    SYSTEM_PROMPT = """You are SERA, a personal AI desktop assistant running on the user's Windows PC.

LANGUAGE:
- Always communicate in English.
- The user's spoken language is English.
- Never switch to another language unless explicitly requested.
- If the input contains ambiguous or incorrectly transcribed words, interpret them in the context of English.

VOICE ASSISTANT BEHAVIOR:
- Be concise, natural, and conversational.
- Normally respond in 1-3 sentences.
- Avoid markdown formatting, asterisks, bullet lists, and tables in spoken responses.
- Do not use emojis in spoken responses.
- Do not output code unless explicitly requested.

PC CONTROL:
- Always call the corresponding tool whenever the user asks to perform an action (including open/close apps, diagnostics, wifi, audio, brightness, restart, or shutdown).
- Do not verbally ask for confirmation yourself before calling a tool; invoke the tool immediately and the safety system will handle user confirmation automatically.
- Never claim an action was completed unless the tool result confirms it.
- If a tool fails, clearly explain that the action failed.
- Do not invent tool results.

IDENTITY:
- Your name is SERA.
- You are a desktop AI assistant running locally on the user's Windows computer.
"""

    def __init__(
        self,
        router: ModelRouter,
        tools: ToolRegistry,
        state: SERAState | None = None,
        event_bus: EventBus | None = None,
    ):
        self.router = router
        self.tools = tools
        self.state = state or SERAState()
        self.event_bus = event_bus or EventBus()
        self.conversation: list[dict[str, Any]] = []

    async def run(
        self,
        user_message: str,
        preferred_role: str | None = None,
    ) -> str:
        self.state.transition_to(SERAStatus.THINKING)
        self.state.last_user_message = user_message

        # Build turn conversation
        self.conversation = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        if not preferred_role:
            preferred_role = self.router.select_role_for_task(user_message)

        self.state.active_model_role = preferred_role

        response, active_role = await self.router.generate_with_fallback(
            messages=self.conversation,
            tools=self.tools.schemas(),
            preferred_role=preferred_role,
        )

        # -----------------------------------------
        # Tool Execution Loop
        # -----------------------------------------
        max_tool_turns = 5
        turn_count = 0

        while response.has_tool_calls and turn_count < max_tool_turns:
            turn_count += 1
            self.state.transition_to(SERAStatus.EXECUTING)

            for tool_call in response.tool_calls:
                self.state.active_tool_name = tool_call.name

                print(f"\n[SERA TOOL] {tool_call.name}")
                print(f"[ARGUMENTS] {tool_call.arguments}")

                # Check if tool requires explicit confirmation
                tool_instance = self.tools.get(tool_call.name)
                if tool_instance and getattr(tool_instance, "requires_confirmation", False):
                    prompt = getattr(
                        tool_instance,
                        "confirmation_prompt",
                        f"Are you sure you want to execute {tool_call.name}?",
                    )
                    self.state.set_pending_confirmation(
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments,
                        prompt=prompt,
                    )
                    return prompt

                # Execute tool
                result = await self.tools.execute(
                    tool_call.name,
                    tool_call.arguments,
                )
                self.state.last_tool_result = result
                print(f"[RESULT] {result}")

                args_str = (
                    json.dumps(tool_call.arguments)
                    if isinstance(tool_call.arguments, (dict, list))
                    else str(tool_call.arguments)
                )

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
                        "content": (
                            json.dumps(result)
                            if isinstance(result, (dict, list))
                            else str(result)
                        ),
                    }
                )

            # Continue conversation with tool outputs
            response, _ = await self.router.generate_with_fallback(
                messages=self.conversation,
                tools=self.tools.schemas(),
                preferred_role=active_role,
            )

        final_text = response.text or "I completed the request."
        self.state.last_response = final_text
        self.state.active_tool_name = None

        self.conversation.append(
            {
                "role": "assistant",
                "content": final_text,
            }
        )

        return final_text

    async def run_stream(
        self,
        user_message: str,
        preferred_role: str | None = None,
        metrics=None,
    ) -> AsyncIterator[str]:
        """Streams response tokens from LLM in real-time, handling tools if triggered."""
        self.state.transition_to(SERAStatus.THINKING)
        self.state.last_user_message = user_message

        self.conversation = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        if not preferred_role:
            preferred_role = self.router.select_role_for_task(user_message)

        self.state.active_model_role = preferred_role

        # If the request is an explicit system action command, execute tool loop directly
        action_prefixes = [
            "open ", "close ", "launch ", "start ", "stop ", "kill ",
            "restart ", "shutdown ", "sleep ", "lock ", "set brightness",
            "set volume", "mute", "unmute", "wifi status", "battery status",
            "cpu usage", "memory usage", "disk usage", "what time is it", "current time",
        ]
        msg_lower = user_message.lower().strip()
        is_conversational_question = msg_lower.startswith(("explain", "tell me", "why", "how does", "what are", "describe", "write a", "who is", "who are"))

        if not is_conversational_question and any(msg_lower.startswith(p) or f" {p}" in msg_lower for p in action_prefixes):
            full_response = await self.run(user_message, preferred_role=preferred_role)
            yield full_response
            return

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
            self.conversation.append(
                {
                    "role": "assistant",
                    "content": final_text,
                }
            )

        except Exception as e:
            logger.info(f"[SERAAgent] Streaming fallback to full tool loop execution: {e}")
            full_response = await self.run(user_message, preferred_role=preferred_role)
            yield full_response