"""SERA 2.0 — Evidence Verification Fabric.

Mandate: Real-world side-effect verification as a mandatory completion gate.
Zero false passes. Tasks only reach COMPLETED when verifiable evidence of
execution is empirically confirmed.
"""

from enum import Enum
import logging
import os
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import psutil

logger = logging.getLogger(__name__)


class EvidenceType(str, Enum):
    PROCESS_RUNNING = "PROCESS_RUNNING"
    WINDOW_HANDLE = "WINDOW_HANDLE"
    STRUCTURED_DATA = "STRUCTURED_DATA"
    FILE_SYSTEM = "FILE_SYSTEM"
    IMAGE_BUFFER = "IMAGE_BUFFER"
    AUDIO_STREAM = "AUDIO_STREAM"
    GENERIC = "GENERIC"


class EvidenceRecord(BaseModel):
    """Structured empirical record proving real-world side effect or execution outcome."""
    evidence_type: EvidenceType
    verified: bool
    source: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "verified": self.verified,
            "source": self.source,
            "details": self.details,
            "timestamp": self.timestamp,
            "failure_reason": self.failure_reason,
        }


class EvidenceVerificationFabric:
    """Core verification engine asserting real-world observable side-effects."""

    def __init__(self):
        self._verification_history: List[EvidenceRecord] = []

    def record_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        self._verification_history.append(evidence)
        return evidence

    def verify_process(self, process_name: str, min_pids: int = 1) -> EvidenceRecord:
        """Verifies that an operating system process is actively running in the OS process table."""
        target = process_name.lower().replace(".exe", "")
        matching_pids = []

        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if target in pname and proc.info.get("status") != psutil.STATUS_ZOMBIE:
                    matching_pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        verified = len(matching_pids) >= min_pids
        reason = None if verified else f"No active process matching '{target}' found in OS process table."

        rec = EvidenceRecord(
            evidence_type=EvidenceType.PROCESS_RUNNING,
            verified=verified,
            source="windows_kernel_psutil",
            details={
                "target_process": target,
                "pids": matching_pids,
                "count": len(matching_pids),
            },
            failure_reason=reason,
        )
        return self.record_evidence(rec)

    def verify_web_search_results(self, results: Any, min_count: int = 1) -> EvidenceRecord:
        """Verifies that web search results contain valid, non-empty structured data records."""
        if not isinstance(results, list):
            rec = EvidenceRecord(
                evidence_type=EvidenceType.STRUCTURED_DATA,
                verified=False,
                source="web_search_engine",
                details={"raw_type": type(results).__name__},
                failure_reason="Web search did not return a structured results list.",
            )
            return self.record_evidence(rec)

        valid_items = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            if title and url and url.startswith("http"):
                valid_items.append(item)

        verified = len(valid_items) >= min_count
        reason = None if verified else f"Expected at least {min_count} valid search results, but found {len(valid_items)}."

        rec = EvidenceRecord(
            evidence_type=EvidenceType.STRUCTURED_DATA,
            verified=verified,
            source="duckduckgo_html_parser",
            details={
                "total_results": len(results),
                "valid_results_count": len(valid_items),
                "first_title": valid_items[0].get("title") if valid_items else None,
                "first_url": valid_items[0].get("url") if valid_items else None,
            },
            failure_reason=reason,
        )
        return self.record_evidence(rec)

    def verify_file_system(self, file_path: str, check_exists: bool = True, min_bytes: int = 0) -> EvidenceRecord:
        """Verifies that a file exists on disk and meets size constraints."""
        norm_path = os.path.abspath(file_path)
        exists = os.path.exists(norm_path)

        if not exists:
            verified = not check_exists
            reason = None if verified else f"File does not exist: {norm_path}"
            rec = EvidenceRecord(
                evidence_type=EvidenceType.FILE_SYSTEM,
                verified=verified,
                source="os_filesystem",
                details={"path": norm_path, "exists": False},
                failure_reason=reason,
            )
            return self.record_evidence(rec)

        size = os.path.getsize(norm_path) if os.path.isfile(norm_path) else 0
        verified = size >= min_bytes
        reason = None if verified else f"File size ({size}B) is less than required minimum ({min_bytes}B)."

        rec = EvidenceRecord(
            evidence_type=EvidenceType.FILE_SYSTEM,
            verified=verified,
            source="os_filesystem",
            details={"path": norm_path, "exists": True, "size_bytes": size},
            failure_reason=reason,
        )
        return self.record_evidence(rec)

    def verify_screen_capture(self, capture_result: Any) -> EvidenceRecord:
        """Verifies that a screen capture contains valid image buffer data."""
        if not isinstance(capture_result, dict):
            rec = EvidenceRecord(
                evidence_type=EvidenceType.IMAGE_BUFFER,
                verified=False,
                source="screen_capture_engine",
                details={},
                failure_reason="Screen capture output is not a valid dictionary payload.",
            )
            return self.record_evidence(rec)

        has_image = bool(capture_result.get("image") or capture_result.get("buffer") or capture_result.get("image_path") or capture_result.get("dimensions"))
        dim = capture_result.get("dimensions") or "valid"

        rec = EvidenceRecord(
            evidence_type=EvidenceType.IMAGE_BUFFER,
            verified=has_image,
            source="screen_capture_engine",
            details={"dimensions": dim, "has_image": has_image},
            failure_reason=None if has_image else "Screen capture payload contains no valid image data.",
        )
        return self.record_evidence(rec)

    def verify_tool_execution(self, tool_name: str, tool_result: Any) -> EvidenceRecord:
        """Unified entry point inspecting any tool execution and synthesizing an EvidenceRecord."""
        # 1. Inspect explicit 'verified' flag in tool result
        if isinstance(tool_result, dict):
            if "verified" in tool_result and not tool_result["verified"]:
                reason = tool_result.get("error") or f"Tool '{tool_name}' reported verification failure."
                rec = EvidenceRecord(
                    evidence_type=EvidenceType.GENERIC,
                    verified=False,
                    source=tool_name,
                    details=tool_result,
                    failure_reason=reason,
                )
                return self.record_evidence(rec)

        # 2. Domain-specific evidence validation
        if tool_name in ("open_application", "launch_application"):
            app_name = "chrome"
            if isinstance(tool_result, dict):
                app_name = tool_result.get("application") or tool_result.get("name") or "chrome"
            # If tool claimed success, verify process table directly
            if isinstance(tool_result, dict) and tool_result.get("success"):
                return self.verify_process(app_name)

        elif tool_name in ("web_search", "search_web"):
            if isinstance(tool_result, dict):
                results_list = tool_result.get("results") or tool_result.get("data") or []
                return self.verify_web_search_results(results_list, min_count=1)

        elif tool_name in ("capture_screen", "take_screenshot"):
            return self.verify_screen_capture(tool_result)

        elif tool_name in ("read_file", "write_file"):
            if isinstance(tool_result, dict) and tool_result.get("file_path"):
                return self.verify_file_system(tool_result["file_path"])

        elif tool_name == "close_window":
            is_closed = isinstance(tool_result, dict) and bool(tool_result.get("verified"))
            return self.record_evidence(EvidenceRecord(
                evidence_type=EvidenceType.WINDOW_HANDLE,
                verified=is_closed,
                source="close_window",
                details=tool_result if isinstance(tool_result, dict) else {},
                failure_reason=None if is_closed else (tool_result.get("error") if isinstance(tool_result, dict) else "Window close verification failed."),
            ))

        elif tool_name == "focus_browser_tab":
            is_focused = isinstance(tool_result, dict) and bool(tool_result.get("verified"))
            return self.record_evidence(EvidenceRecord(
                evidence_type=EvidenceType.WINDOW_HANDLE,
                verified=is_focused,
                source="focus_browser_tab",
                details=tool_result if isinstance(tool_result, dict) else {},
                failure_reason=None if is_focused else (tool_result.get("error") if isinstance(tool_result, dict) else "Browser tab focus verification failed."),
            ))

        elif tool_name == "close_browser_tab":
            is_tab_closed = isinstance(tool_result, dict) and bool(tool_result.get("verified"))
            return self.record_evidence(EvidenceRecord(
                evidence_type=EvidenceType.WINDOW_HANDLE,
                verified=is_tab_closed,
                source="close_browser_tab",
                details=tool_result if isinstance(tool_result, dict) else {},
                failure_reason=None if is_tab_closed else (tool_result.get("error") if isinstance(tool_result, dict) else "Browser tab close verification failed."),
            ))

        # 3. Generic tool fallback
        is_success = isinstance(tool_result, dict) and tool_result.get("success", False)
        if not isinstance(tool_result, dict):
            is_success = bool(tool_result)

        rec = EvidenceRecord(
            evidence_type=EvidenceType.GENERIC,
            verified=is_success,
            source=tool_name,
            details=tool_result if isinstance(tool_result, dict) else {"raw": str(tool_result)},
            failure_reason=None if is_success else f"Generic execution of {tool_name} failed.",
        )
        return self.record_evidence(rec)
