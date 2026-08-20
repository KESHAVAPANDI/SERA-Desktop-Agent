from dataclasses import dataclass


@dataclass
class SecurityDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str = ""


class SecurityManager:

    def __init__(self):

        # Level 0 & Level 1: Completely safe / non-destructive actions.
        self.safe_tools = {
            # Applications & Desktop Semantic Actions
            "open_application",
            "close_application",
            "list_running_applications",
            "focus_application",
            "focus_desktop_window",
            "inspect_desktop_ui",
            "click_ui_element",
            "invoke_ui_element",
            "set_ui_input_text",
            "select_ui_tab",
            "select_ui_item",
            "scroll_ui_container",

            # System & Diagnostics
            "get_system_info",
            "get_battery_status",
            "get_current_time",
            "get_cpu_usage",
            "get_memory_usage",
            "get_disk_usage",
            "get_wifi_status",
            "wifi_status",
            "bluetooth_status",

            # Audio
            "get_volume",
            "set_volume",
            "volume_up",
            "volume_down",
            "mute",
            "unmute",

            # Display
            "get_brightness",
            "set_brightness",
            "brightness_up",
            "brightness_down",

            # Safe Power
            "lock_computer",
            "sleep_computer",
        }

        # Level 3: Destructive actions that affect user session or data.
        self.confirmation_tools = {
            "restart_computer",
            "shutdown_computer",
            "delete_file",
            "delete_folder",
            "shutdown_pc",
            "restart_pc",
            "sleep_pc",
            "hibernate_pc",
            "install_software",
            "registry_modify",
            "format_drive",
        }

    def check(
        self,
        tool_name: str,
        is_confirmed: bool = False,
    ) -> SecurityDecision:

        if is_confirmed:
            return SecurityDecision(
                allowed=True,
                requires_confirmation=False,
            )

        if tool_name in self.safe_tools:
            return SecurityDecision(
                allowed=True,
                requires_confirmation=False,
            )

        if tool_name in self.confirmation_tools:
            return SecurityDecision(
                allowed=True,
                requires_confirmation=True,
                reason=f"{tool_name} requires user confirmation before execution.",
            )

        # Allow registered custom tools with caution
        return SecurityDecision(
            allowed=False,
            requires_confirmation=True,
            reason=f"Tool '{tool_name}' is not approved by the security policy.",
        )