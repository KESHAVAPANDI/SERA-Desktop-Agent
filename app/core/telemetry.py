import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LatencyMetrics:
    """Telemetry tracking latency milestones across a single SERA interaction turn."""
    turn_id: str = ""
    hotkey_pressed_at: float | None = None
    listening_started_at: float | None = None
    user_speech_started_at: float | None = None
    user_speech_ended_at: float | None = None
    recording_ended_at: float | None = None
    stt_completed_at: float | None = None
    intent_classified_at: float | None = None
    llm_request_started_at: float | None = None
    llm_first_token_at: float | None = None
    first_sentence_at: float | None = None
    llm_completed_at: float | None = None
    tool_completed_at: float | None = None

    # Desktop & Vision perception metrics
    ui_inspection_ms: float | None = None
    native_target_lookup_ms: float | None = None
    ocr_ms: float | None = None
    perception_method: str | None = None  # "native" | "ocr" | "vision_qwen" | "vision_gemini" | "vision_openrouter"
    screen_capture_ms: float | None = None
    image_preparation_ms: float | None = None
    vision_request_ms: float | None = None
    vision_parse_ms: float | None = None
    screen_context_cache_hit: bool | None = None
    total_screen_analysis_ms: float | None = None

    # Semantic action metrics
    action_resolution_ms: float | None = None
    security_check_ms: float | None = None
    action_execution_ms: float | None = None
    verification_ms: float | None = None
    action_success: bool | None = None
    action_verified: bool | None = None

    # Multi-Step Computer-Use Metrics (Phase 4)
    planning_ms: float | None = None
    step_observe_ms: float | None = None
    step_resolve_ms: float | None = None
    step_action_ms: float | None = None
    step_verify_ms: float | None = None
    step_recovery_ms: float | None = None
    task_total_ms: float | None = None
    steps_completed: int = 0
    steps_failed: int = 0
    retries: int = 0
    task_success: bool | None = None

    # TTS & playback metrics
    tts_request_started_at: float | None = None
    tts_generated_at: float | None = None
    first_audio_played_at: float | None = None
    tts_playback_started_at: float | None = None
    turn_completed_at: float | None = None

    @property
    def hotkey_to_listening_ms(self) -> float | None:
        if self.hotkey_pressed_at and self.listening_started_at:
            return round((self.listening_started_at - self.hotkey_pressed_at) * 1000, 2)
        return None

    @property
    def user_utterance_duration_ms(self) -> float | None:
        start = self.user_speech_started_at or self.listening_started_at
        end = self.user_speech_ended_at or self.recording_ended_at
        if start and end:
            return round((end - start) * 1000, 2)
        return None

    @property
    def recording_duration_ms(self) -> float | None:
        if self.listening_started_at and self.recording_ended_at:
            return round((self.recording_ended_at - self.listening_started_at) * 1000, 2)
        return None

    @property
    def stt_duration_ms(self) -> float | None:
        start = self.user_speech_ended_at or self.recording_ended_at
        if start and self.stt_completed_at:
            return round((self.stt_completed_at - start) * 1000, 2)
        return None

    @property
    def intent_duration_ms(self) -> float | None:
        if self.stt_completed_at and self.intent_classified_at:
            return round((self.intent_classified_at - self.stt_completed_at) * 1000, 2)
        return None

    @property
    def llm_first_token_ms(self) -> float | None:
        start = self.llm_request_started_at or self.intent_classified_at
        if start and self.llm_first_token_at:
            return round((self.llm_first_token_at - start) * 1000, 2)
        return None

    @property
    def first_sentence_ms(self) -> float | None:
        start = self.llm_request_started_at or self.intent_classified_at
        if start and self.first_sentence_at:
            return round((self.first_sentence_at - start) * 1000, 2)
        return None

    @property
    def llm_duration_ms(self) -> float | None:
        start = self.llm_request_started_at or self.intent_classified_at
        if start and self.llm_completed_at:
            return round((self.llm_completed_at - start) * 1000, 2)
        return None

    @property
    def tool_duration_ms(self) -> float | None:
        if self.llm_completed_at and self.tool_completed_at:
            return round((self.tool_completed_at - self.llm_completed_at) * 1000, 2)
        return None

    @property
    def tts_generation_ms(self) -> float | None:
        start = self.tool_completed_at or self.first_sentence_at or self.llm_completed_at or self.intent_classified_at
        if start and self.tts_generated_at:
            return round((self.tts_generated_at - start) * 1000, 2)
        return None

    @property
    def time_to_first_audio_ms(self) -> float | None:
        speech_end = self.user_speech_ended_at or self.recording_ended_at
        first_play = self.first_audio_played_at or self.tts_playback_started_at
        if speech_end and first_play:
            return round((first_play - speech_end) * 1000, 2)
        return None

    @property
    def total_post_speech_latency_ms(self) -> float | None:
        speech_end = self.user_speech_ended_at or self.recording_ended_at
        turn_end = self.turn_completed_at or self.tts_playback_started_at
        if speech_end and turn_end:
            return round((turn_end - speech_end) * 1000, 2)
        return None

    @property
    def total_turn_latency_ms(self) -> float | None:
        start = self.hotkey_pressed_at or self.listening_started_at
        end = self.turn_completed_at or self.tts_playback_started_at
        if start and end:
            return round((end - start) * 1000, 2)
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "hotkey_to_listening_ms": self.hotkey_to_listening_ms,
            "user_utterance_duration_ms": self.user_utterance_duration_ms,
            "recording_duration_ms": self.recording_duration_ms,
            "stt_duration_ms": self.stt_duration_ms,
            "intent_duration_ms": self.intent_duration_ms,
            "perception_method": self.perception_method,
            "ui_inspection_ms": self.ui_inspection_ms,
            "native_target_lookup_ms": self.native_target_lookup_ms,
            "screen_capture_ms": self.screen_capture_ms,
            "vision_request_ms": self.vision_request_ms,
            "vision_parse_ms": self.vision_parse_ms,
            "screen_context_cache_hit": self.screen_context_cache_hit,
            "total_screen_analysis_ms": self.total_screen_analysis_ms,
            "action_resolution_ms": self.action_resolution_ms,
            "security_check_ms": self.security_check_ms,
            "action_execution_ms": self.action_execution_ms,
            "verification_ms": self.verification_ms,
            "action_success": self.action_success,
            "action_verified": self.action_verified,
            "planning_ms": self.planning_ms,
            "task_total_ms": self.task_total_ms,
            "steps_completed": self.steps_completed,
            "retries": self.retries,
            "task_success": self.task_success,
            "llm_first_token_ms": self.llm_first_token_ms,
            "first_sentence_ms": self.first_sentence_ms,
            "llm_duration_ms": self.llm_duration_ms,
            "tool_duration_ms": self.tool_duration_ms,
            "tts_generation_ms": self.tts_generation_ms,
            "time_to_first_audio_ms": self.time_to_first_audio_ms,
            "total_post_speech_latency_ms": self.total_post_speech_latency_ms,
            "total_turn_latency_ms": self.total_turn_latency_ms,
        }

    def format_summary(self) -> str:
        parts = ["[LATENCY TELEMETRY]"]
        if self.planning_ms is not None:
            parts.append(f"Plan: {self.planning_ms}ms")
        if self.perception_method:
            parts.append(f"Perception: {self.perception_method}")
        if self.ui_inspection_ms is not None:
            parts.append(f"Native UI: {self.ui_inspection_ms}ms")
        if self.total_screen_analysis_ms is not None:
            parts.append(f"Screen Total: {self.total_screen_analysis_ms}ms")
        if self.action_execution_ms is not None:
            parts.append(f"Action: {self.action_execution_ms}ms (Verified: {self.action_verified})")
        if self.task_total_ms is not None:
            parts.append(f"Task Total: {self.task_total_ms}ms (Steps: {self.steps_completed})")
        if self.time_to_first_audio_ms is not None:
            parts.append(f"TTFA: {self.time_to_first_audio_ms}ms")
        return " | ".join(parts)
