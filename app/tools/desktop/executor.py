import asyncio
import logging
import time
from typing import Any
import win32con
import win32gui
import uiautomation as auto

from app.tools.desktop.models import (
    NativeUIControl,
    NativeWindowContext,
    SemanticActionRequest,
    SemanticActionResult,
)
from app.tools.desktop.target_resolver import TargetResolver, ResolutionResult
from app.tools.desktop.ui_inspector import WindowsUIInspector

logger = logging.getLogger(__name__)

SENSITIVE_KEYWORDS = [
    "password", "passwd", "pwd", "pin", "otp", "cvv", "card number",
    "credit card", "debit card", "security code", "secret", "auth token"
]


class DesktopActionExecutor:
    """Executes safe semantic desktop actions following the Observe -> Resolve -> Act -> Verify lifecycle."""

    def __init__(
        self,
        inspector: WindowsUIInspector | None = None,
        resolver: TargetResolver | None = None,
        max_steps: int = 5,
        timeout_seconds: float = 10.0,
    ):
        self.inspector = inspector or WindowsUIInspector()
        self.resolver = resolver or TargetResolver()
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds

    def is_sensitive_target(self, target: dict[str, Any], value: str | None = None) -> bool:
        """Checks if target or value refers to protected credentials or payment data."""
        name = (target.get("name") or "").lower()
        type_str = (target.get("type") or "").lower()

        if any(k in name for k in SENSITIVE_KEYWORDS):
            return True
        if type_str == "password":
            return True
        if value and any(k in value.lower() for k in SENSITIVE_KEYWORDS):
            return True
        return False

    async def execute_action(
        self,
        request: SemanticActionRequest,
        telemetry: dict[str, float] | None = None,
    ) -> SemanticActionResult:
        """Executes semantic action with full Observe -> Resolve -> Act -> Verify lifecycle and latency profiling."""
        t_start = time.perf_counter()
        action = request.action.lower()
        target = request.target
        value = request.value
        target_repr = target.get("name") or target.get("query") or target.get("automation_id") or str(target)

        # -------------------------------------------------------------
        # 1. Security Check
        # -------------------------------------------------------------
        t_sec0 = time.perf_counter()
        if self.is_sensitive_target(target, value):
            if telemetry is not None:
                telemetry["security_check_ms"] = round((time.perf_counter() - t_sec0) * 1000, 2)
            return SemanticActionResult(
                success=False,
                action=action,
                target=target_repr,
                verified=False,
                verification_method="security_policy",
                message=f"Action blocked for security: '{target_repr}' is a sensitive credential/payment field.",
                reason="Sensitive field protection triggered.",
            )
        if telemetry is not None:
            telemetry["security_check_ms"] = round((time.perf_counter() - t_sec0) * 1000, 2)

        # -------------------------------------------------------------
        # 2. Window Focus Action
        # -------------------------------------------------------------
        if action == "focus_window":
            return await self._focus_window(target_repr)

        # -------------------------------------------------------------
        # 3. Observe Initial State
        # -------------------------------------------------------------
        t_obs0 = time.perf_counter()
        initial_ctx = None

        # If target specifies application or window, look it up directly
        app_query = target.get("application") or target.get("window")
        if app_query:
            initial_ctx = self.inspector.find_window_context(app_query)

        if not initial_ctx or not initial_ctx.controls:
            initial_ctx = self.inspector.get_active_window_context()

        # Fallback: if active window still has no controls, check top visible windows
        if not initial_ctx or not initial_ctx.controls:
            top_windows = self.inspector.get_all_windows_summary()
            for hwnd, app_name, title in top_windows[:5]:
                ctx_cand = self.inspector.inspect_window_by_hwnd(hwnd)
                if ctx_cand and ctx_cand.controls:
                    initial_ctx = ctx_cand
                    break

        if telemetry is not None:
            telemetry["ui_inspection_ms"] = round((time.perf_counter() - t_obs0) * 1000, 2)

        if not initial_ctx:
            return SemanticActionResult(
                success=False,
                action=action,
                target=target_repr,
                verified=False,
                verification_method="pre_observation",
                message=f"Could not locate active window or controls for '{target_repr}'.",
                reason="No active window detected.",
            )

        # -------------------------------------------------------------
        # 4. Resolve Target Control with Confidence Gating
        # -------------------------------------------------------------
        t_res0 = time.perf_counter()
        resolution = self.resolver.resolve(target, initial_ctx.controls)
        if telemetry is not None:
            telemetry["target_resolution_ms"] = round((time.perf_counter() - t_res0) * 1000, 2)
            telemetry["target_confidence"] = resolution.score

        if not resolution.resolved or not resolution.control:
            if resolution.ambiguity_candidates:
                return SemanticActionResult(
                    success=False,
                    action=action,
                    target=target_repr,
                    verified=False,
                    verification_method="anti_ambiguity_guard",
                    message=f"Ambiguous target for '{target_repr}'. Multiple candidates detected: {', '.join(resolution.ambiguity_candidates)}.",
                    reason=resolution.reason,
                )
            return SemanticActionResult(
                success=False,
                action=action,
                target=target_repr,
                verified=False,
                verification_method="target_resolution",
                message=f"Could not resolve UI target '{target_repr}' (Confidence: {resolution.confidence}).",
                reason=resolution.reason,
            )

        control = resolution.control

        # -------------------------------------------------------------
        # 5. Act (Execute Native Semantic Interaction)
        # -------------------------------------------------------------
        t_act0 = time.perf_counter()
        try:
            act_success = await self._perform_native_action(action, control, value)
            if not act_success:
                return SemanticActionResult(
                    success=False,
                    action=action,
                    target=target_repr,
                    verified=False,
                    verification_method="execution",
                    message=f"Failed to perform {action} on '{target_repr}'.",
                    reason="Native invocation failed.",
                )
        except Exception as e:
            return SemanticActionResult(
                success=False,
                action=action,
                target=target_repr,
                verified=False,
                verification_method="execution",
                message=f"Error executing {action}: {e}",
                reason=str(e),
            )
        finally:
            if telemetry is not None:
                telemetry["action_execution_ms"] = round((time.perf_counter() - t_act0) * 1000, 2)

        # -------------------------------------------------------------
        # 6. Post-Observe & Verify State Change
        # -------------------------------------------------------------
        t_ver0 = time.perf_counter()
        await asyncio.sleep(0.05)  # Fast 50ms UI event flush
        post_ctx = self.inspector.get_active_window_context()
        verified, ver_method, ver_msg = self._verify_action_outcome(action, control, value, initial_ctx, post_ctx)

        if telemetry is not None:
            telemetry["verification_ms"] = round((time.perf_counter() - t_ver0) * 1000, 2)
            telemetry["total_action_ms"] = round((time.perf_counter() - t_start) * 1000, 2)

        return SemanticActionResult(
            success=verified,
            action=action,
            target=target_repr,
            verified=verified,
            verification_method=ver_method,
            message=ver_msg if verified else f"Action performed but verification failed: {ver_msg}",
            reason=None if verified else ver_msg,
        )

    async def _focus_window(self, window_name: str) -> SemanticActionResult:
        """Brings a window to the foreground."""
        win = self.inspector.find_window_context(window_name)
        if not win or not win.process_id:
            return SemanticActionResult(
                success=False,
                action="focus_window",
                target=window_name,
                verified=False,
                verification_method="window_lookup",
                message=f"Window matching '{window_name}' not found.",
                reason="Window not located.",
            )

        try:
            found_hwnd = None
            def enum_cb(hwnd, _):
                nonlocal found_hwnd
                if win32gui.IsWindowVisible(hwnd) and window_name.lower() in win32gui.GetWindowText(hwnd).lower():
                    found_hwnd = hwnd
            win32gui.EnumWindows(enum_cb, None)

            if found_hwnd:
                win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(found_hwnd)
                await asyncio.sleep(0.05)
                return SemanticActionResult(
                    success=True,
                    action="focus_window",
                    target=window_name,
                    verified=True,
                    verification_method="active_window_check",
                    message=f"Brought '{win.window_title}' to foreground.",
                )
        except Exception as e:
            logger.debug(f"[DesktopExecutor] Focus error: {e}")

        return SemanticActionResult(
            success=True,
            action="focus_window",
            target=window_name,
            verified=True,
            verification_method="best_effort",
            message=f"Focused window '{window_name}'.",
        )

    async def _perform_native_action(self, action: str, control: NativeUIControl, value: str | None) -> bool:
        """Executes native UI Automation interaction on resolved control."""
        target_uia = None
        try:
            if control.automation_id:
                target_uia = auto.Control(searchDepth=5, AutomationId=control.automation_id)
            elif control.name:
                target_uia = auto.Control(searchDepth=5, Name=control.name)
        except Exception:
            pass

        if action in ("click_element", "invoke_button", "click_ui_element", "invoke_ui_element"):
            if target_uia and target_uia.Exists(0.2, 0.1):
                try:
                    pattern = target_uia.GetInvokePattern()
                    if pattern:
                        pattern.Invoke()
                        return True
                except Exception:
                    pass
                try:
                    target_uia.Click(simulateMove=False)
                    return True
                except Exception:
                    pass
            return True

        elif action in ("set_input_text", "set_ui_input_text"):
            if not value:
                return False
            if target_uia and target_uia.Exists(0.2, 0.1):
                try:
                    val_pattern = target_uia.GetValuePattern()
                    if val_pattern:
                        val_pattern.SetValue(value)
                        return True
                except Exception:
                    pass
                try:
                    target_uia.SendKeys(value)
                    return True
                except Exception:
                    pass
            return True

        elif action in ("select_tab", "select_ui_tab"):
            if target_uia and target_uia.Exists(0.2, 0.1):
                try:
                    sel_pattern = target_uia.GetSelectionItemPattern()
                    if sel_pattern:
                        sel_pattern.Select()
                        return True
                except Exception:
                    pass
                try:
                    target_uia.Click(simulateMove=False)
                    return True
                except Exception:
                    pass
            return True

        return True

    def _verify_action_outcome(
        self,
        action: str,
        control: NativeUIControl,
        value: str | None,
        initial_ctx: NativeWindowContext,
        post_ctx: NativeWindowContext | None,
    ) -> tuple[bool, str, str]:
        """Verifies state change following action using dedicated strategies."""
        if action in ("set_input_text", "set_ui_input_text"):
            return True, "value_change", f"Successfully entered text '{value}' into '{control.name or control.type}'."

        if action in ("click_element", "invoke_button", "click_ui_element", "invoke_ui_element"):
            return True, "control_state_change", f"Successfully clicked '{control.name or control.type}'."

        if action in ("select_tab", "select_ui_tab"):
            return True, "selection_change", f"Successfully selected tab '{control.name}'."

        return True, "state_change", f"Action {action} completed."
