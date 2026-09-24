"""
SERA 2.0 — Unified Local Semantic Interpreter.

Encapsulates language semantic interpretation behind a clean, provider-agnostic interface:
interpret(utterance, context) -> CanonicalIntent

Does NOT execute tools, control Windows, or verify success.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, Union

from app.core.semantic.prompt import build_semantic_prompt
from app.core.semantic.schema import (
    ActionFamily,
    CanonicalIntent,
    CompactSemanticContext,
)
from app.core.semantic.validator import SemanticValidator
from app.models.llm.ollama import OllamaProvider

logger = logging.getLogger("sera.semantic.interpreter")


class SemanticInterpreter:
    """Unified Semantic Interpreter translating natural language into CanonicalIntent."""

    def __init__(
        self,
        provider: Optional[OllamaProvider] = None,
        model: str = "qwen3.5:4b",
        timeout: float = 10.0,
    ):
        self.model = os.environ.get("SEMANTIC_MODEL", model)
        self.timeout = float(os.environ.get("SEMANTIC_TIMEOUT", str(timeout)))
        self.provider = provider or OllamaProvider(model=self.model, timeout=self.timeout + 5.0)

    @staticmethod
    def extract_compact_context(
        graph_state: Optional[Any] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> CompactSemanticContext:
        """Extracts minimal language-relevant context without leaking secrets or full state."""
        ctx = extra_context or {}
        if graph_state is not None:
            active_app = getattr(graph_state, "active_application", None) or ctx.get("active_application")
            active_browser = getattr(graph_state, "active_browser", None) or ctx.get("active_browser")
            active_tab = getattr(graph_state, "active_browser_tab", None) or ctx.get("active_tab")
            current_url = getattr(graph_state, "current_url", None) or ctx.get("current_url")
            last_action = getattr(graph_state, "last_verified_action", None) or ctx.get("last_verified_action")
            raw_input = getattr(graph_state, "raw_user_input", "") or ctx.get("utterance", "")
            entities = ctx.get("relevant_entities", [])
            recent = ctx.get("recent_verified_actions", [])
        else:
            active_app = ctx.get("active_application")
            active_browser = ctx.get("active_browser")
            active_tab = ctx.get("active_tab")
            current_url = ctx.get("current_url")
            last_action = ctx.get("last_verified_action")
            raw_input = ctx.get("utterance", "")
            entities = ctx.get("relevant_entities", [])
            recent = ctx.get("recent_verified_actions", [])

        return CompactSemanticContext(
            utterance=raw_input,
            active_application=active_app,
            active_browser=active_browser,
            active_tab=active_tab,
            current_url=current_url,
            last_verified_action=last_action,
            relevant_entities=entities,
            recent_verified_actions=recent,
        )

    async def interpret_async(
        self,
        utterance: str,
        context: Optional[Union[CompactSemanticContext, Dict[str, Any]]] = None,
    ) -> CanonicalIntent:
        """Asynchronously interprets utterance + context into CanonicalIntent."""
        clean_utterance = (utterance or "").strip()
        if not clean_utterance:
            return CanonicalIntent(
                intent="unknown",
                action_family=ActionFamily.UNKNOWN.value,
                confidence=0.0,
                needs_clarification=True,
                ambiguity_reason="Empty utterance provided",
            )

        if isinstance(context, CompactSemanticContext):
            ctx_dict = context.to_dict()
        elif isinstance(context, dict):
            ctx_dict = context
        else:
            ctx_dict = {}

        messages = build_semantic_prompt(clean_utterance, ctx_dict)

        start_time = time.perf_counter()
        try:
            # Fast-path timeout bounded at self.timeout (default 5.0s)
            raw_output = await asyncio.wait_for(
                self.provider.generate_structured(messages, model=self.model),
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.debug(f"Semantic interpretation completed in {elapsed_ms:.1f}ms")

            intent_obj, is_valid, err_reason = SemanticValidator.validate(raw_output)
            return intent_obj

        except asyncio.TimeoutError:
            err_msg = f"Semantic model timed out after {self.timeout}s"
            logger.warning(err_msg)
            return CanonicalIntent(
                intent="unknown",
                action_family=ActionFamily.UNKNOWN.value,
                confidence=0.0,
                needs_clarification=True,
                ambiguity_reason=err_msg,
            )
        except Exception as err:
            err_msg = f"Semantic interpretation failed: {err}"
            logger.warning(err_msg)
            return CanonicalIntent(
                intent="unknown",
                action_family=ActionFamily.UNKNOWN.value,
                confidence=0.0,
                needs_clarification=True,
                ambiguity_reason=err_msg,
            )

    def interpret(
        self,
        utterance: str,
        context: Optional[Union[CompactSemanticContext, Dict[str, Any]]] = None,
    ) -> CanonicalIntent:
        """Synchronous wrapper for interpret_async."""
        try:
            loop = asyncio.get_running_loop()
            # If already running inside an active event loop, run in a worker thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(self.interpret_async(utterance, context))).result()
        except RuntimeError:
            # No running loop, run directly
            return asyncio.run(self.interpret_async(utterance, context))
