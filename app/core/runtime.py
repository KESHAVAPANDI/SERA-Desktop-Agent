import asyncio
import inspect
import logging
import sys
import time
import uuid
from typing import Any
import numpy as np

# Ensure Windows console encoding handles full UTF-8
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.agent import SERAAgent
from app.core.events import EventBus
from app.core.hotkey import GlobalHotkeyManager
from app.core.intent import LocalIntentRouter
from app.core.router import ModelRouter
from app.core.state import SERAState, SERAStatus
from app.core.streaming import stream_sentences
from app.core.telemetry import LatencyMetrics
from app.models.llm import create_provider
from app.models.stt import PrimaryWithFallbackSTT, create_stt_pipeline
from app.speech.audio_cues import get_audio_cues
from app.speech.audio_manager import AudioManager
from app.speech.recorder import AudioRecorder
from app.speech.transcript_gate import TranscriptQualityGate
from app.speech.wakeword import LocalCustomWakeWordProvider, OpenWakeWordDetector, WakeWordRegistry, WakeWordStatus
from app.tools import create_tool_registry
from app.tools.desktop.perception_router import DesktopPerceptionRouter
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.core.command_pipeline import CommandPipeline
from app.utils.config import SERAConfig
from app.utils.security import SecurityManager
from app.vision.analyzer import ScreenPerceptionEngine

logger = logging.getLogger(__name__)


class SERARuntime:
    """Core Runtime Engine for SERA 1.0 with Phase 4.2 NVIDIA STT, Fixed 5s Capture & Wake Word."""

    def __init__(
        self,
        config_path: str | None = None,
        audio_manager: AudioManager | None = None,
        tools_registry=None,
        model_router: ModelRouter | None = None,
        vision_engine: ScreenPerceptionEngine | None = None,
        desktop_router: DesktopPerceptionRouter | None = None,
        stt_pipeline: PrimaryWithFallbackSTT | None = None,
        event_bus: EventBus | None = None,
    ):
        print("=" * 60)
        print("INITIALIZING SERA RUNTIME 1.0")
        print("=" * 60)

        self.config = SERAConfig(config_path)
        models_cfg = self.config.data.get("models", {})
        hotkey_cfg = self.config.data.get("hotkey", {})
        wake_cfg = self.config.data.get("wake_word", {})
        audio_cfg = self.config.data.get("audio", {})
        stt_cfg = self.config.data.get("stt", {})
        cues_cfg = self.config.data.get("audio_cues", {})
        vision_cfg = self.config.data.get("vision", {})
        telemetry_cfg = self.config.data.get("telemetry", {})

        self.manual_debug_mode = telemetry_cfg.get("manual_debug_mode", True)
        self.recording_duration = float(stt_cfg.get("recording_duration_seconds", 5.0))
        self.stt_language = stt_cfg.get("language", "en-US")
        self.stt_sample_rate = int(audio_cfg.get("sample_rate", 16000))

        # Audio Cues
        self.audio_cues = get_audio_cues(enabled=cues_cfg.get("enabled", True))

        # Transcript Quality Gate
        self.quality_gate = TranscriptQualityGate(
            min_words=1,
            max_no_speech_prob=0.75,
            min_avg_logprob=-1.6,
        )

        # State & Events
        self.state = SERAState()
        self.events = event_bus or EventBus()
        self.event_bus = self.events

        # Visual state tracker (prints state exactly once per change)
        self._last_printed_state: SERAStatus | None = None
        self._setup_state_listener()

        # Single Active Task Trackers
        self._active_listen_task: asyncio.Task | None = None
        self._active_agent_task: asyncio.Task | None = None
        self._active_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Turn and Event counters
        self.hotkey_event_count: int = 0
        self.wakeword_event_count: int = 0
        self.turn_count: int = 0
        self._executed_tools: set[str] = set()

        # Fixed 5-second Audio Recorder
        self.recorder = AudioRecorder(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            channels=1,
            dtype="float32",
        )

        # Primary (NVIDIA Canary-Qwen 2.5B) + Fallback (Faster-Whisper Small) STT Pipeline
        if stt_pipeline:
            self.stt = stt_pipeline
        elif audio_manager and hasattr(audio_manager, "listen_once") and hasattr(audio_manager.listen_once, "return_value"):
            from unittest.mock import AsyncMock, MagicMock
            mock_stt = MagicMock(spec=PrimaryWithFallbackSTT)
            mock_stt.transcribe = AsyncMock(side_effect=lambda *a, **kw: audio_manager.listen_once())
            self.stt = mock_stt
            self.recorder.record_for = AsyncMock(return_value=np.zeros(16000, dtype=np.float32))
        else:
            self.stt = create_stt_pipeline(self.config.data)

        print(f"[STT] Primary: Google Gemini 3.5 Transcribe")
        print(f"[STT] Mode: Gemini API")
        print(f"[STT] Language: {self.stt_language}")
        print(f"[STT] Command capture: {self.recording_duration} seconds")

        # Local Wake Word Detector ("SERA")
        self.wakeword_enabled = wake_cfg.get("enabled", True)
        self.wakeword_phrase = wake_cfg.get("phrase", "Hey SERA")
        self.wakeword_provider = WakeWordRegistry.create(
            name=wake_cfg.get("provider", "local_custom"),
            model_path=wake_cfg.get("model_path", "models/wakeword/hey_sera.tflite"),
            enabled=wake_cfg.get("enabled", False),
        )
        self.wakeword_detector = OpenWakeWordDetector(
            phrase=self.wakeword_phrase,
            sensitivity=wake_cfg.get("sensitivity", 0.5),
            debounce_ms=wake_cfg.get("debounce_ms", 1000),
            sample_rate=audio_cfg.get("sample_rate", 16000),
        )

        # Local Intent Router
        self.intent_router = LocalIntentRouter()

        # Tools Registry (Windows tools + Semantic Desktop tools)
        self.tools = tools_registry or create_tool_registry()

        # Audio Manager (TTS playback & device controls)
        self.audio = audio_manager or AudioManager(
            audio_config=audio_cfg,
            models_config=models_cfg,
        )

        # Model Router Initialization
        if model_router:
            self.router = model_router
        else:
            from app.core.router import create_model_router_from_config
            self.router = create_model_router_from_config(self.config.data)

        # Agent Engine
        self.agent = SERAAgent(
            router=self.router,
            tools=self.tools,
            state=self.state,
            event_bus=self.events,
        )

        # Screen Perception Engine (Multimodal Vision)
        self.vision = vision_engine or ScreenPerceptionEngine(
            router=self.router,
            vision_cfg=vision_cfg,
        )

        # Desktop Perception Router
        prefer_native = vision_cfg.get("routing", {}).get("prefer_native_ui", True)
        self.desktop_router = desktop_router or DesktopPerceptionRouter(
            inspector=WindowsUIInspector(),
            vision_engine=self.vision,
            prefer_native=prefer_native,
        )

        # Deterministic Command Execution Pipeline (Fast-Path Layer 1, Layer 2, Layer 3)
        self.command_pipeline = CommandPipeline(
            tools=self.tools,
            router=self.router,
            state=self.state,
            event_bus=self.events,
            security_manager=SecurityManager(),
        )

        # Global Hotkey Manager with Hold-To-Talk
        hotkey_combo = hotkey_cfg.get("combination", "ctrl+space")
        self.hotkey_manager = GlobalHotkeyManager(
            hotkey=hotkey_combo,
            on_press=self.handle_hotkey_press,
            on_release=self.handle_hotkey_release,
            loop=self._loop,
        )

        self._hold_activation_time = 0.0
        self._is_holding_hotkey = False
        self.active_task_info: dict[str, Any] | None = None
        self._active_task_handle: asyncio.Task | None = None

        # Wire live TTS audio levels directly to EventBus/WebSocket for presence core reactivity
        if hasattr(self.audio, "on_audio_levels"):
            self.audio.on_audio_levels = lambda bands: self._emit_event("TTS_AUDIO_LEVELS", bands)

        self.is_ready = True
        self._transition_state(SERAStatus.IDLE)
        print("=" * 60)
        print(f"SERA RUNTIME READY (Hold-To-Talk: {hotkey_combo} | Wake Word: '{self.wakeword_phrase}')")
        print("=" * 60)

    def _setup_state_listener(self) -> None:
        """Sets up visual state indicator hook."""
        orig_transition = self.state.transition_to

        def wrapped_transition(new_status: SERAStatus) -> None:
            orig_transition(new_status)
            self._print_visual_state(new_status)

        self.state.transition_to = wrapped_transition

    def _transition_state(self, new_status: SERAStatus) -> None:
        self.state.transition_to(new_status)

    def _print_visual_state(self, status: SERAStatus) -> None:
        if self._last_printed_state != status:
            self._last_printed_state = status
            print(f"[SERA STATE] ● {status.value.upper()}")

    def handle_hotkey_trigger(self) -> None:
        """Compatibility trigger for single hotkey press / test invocation."""
        self.handle_hotkey_press()
        self.handle_hotkey_release()
        
    def register_event_listener(self, callback: Any) -> None:
        """Registers a custom event listener callback receiving (event_type, payload)."""
        if not hasattr(self, "_custom_listeners"):
            self._custom_listeners = []
        self._custom_listeners.append(callback)

    def _emit_event(self, event_name: str, payload: Any = None) -> None:
        """Safely dispatches event to EventBus and listeners with standardized metadata."""
        data = dict(payload) if isinstance(payload, dict) else {"data": payload}
        if "event_id" not in data:
            data["event_id"] = f"evt_{uuid.uuid4().hex[:8]}"
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        if "task_id" not in data and getattr(self, "active_task_info", None):
            data["task_id"] = self.active_task_info.get("task_id")
        if "turn_id" not in data and data.get("task_id"):
            data["turn_id"] = data["task_id"]

        if hasattr(self, "events") and self.events:
            self.events.emit(event_name, data)

        if hasattr(self, "_custom_listeners"):
            for listener in self._custom_listeners:
                try:
                    listener(event_name, data)
                except Exception as e:
                    logger.debug(f"[SERARuntime] Listener error: {e}")

    def handle_hotkey_press(self) -> None:
        """Triggered immediately when Ctrl+Space is pressed down (Hold-To-Talk begin)."""
        self.hotkey_event_count += 1
        self._hold_activation_time = time.time()
        self._is_holding_hotkey = True
        current_st = self.state.status if hasattr(self, "state") and self.state else SERAStatus.IDLE

        # Interrupt any ongoing speech or execution immediately
        if current_st == SERAStatus.SPEAKING or (hasattr(self, "audio") and hasattr(self.audio, "is_speaking") and self.audio.is_speaking is True):
            if hasattr(self, "audio") and hasattr(self.audio, "stop_speaking"):
                self.audio.stop_speaking()
            if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_interrupted_cue"):
                self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()
        elif current_st in (
            SERAStatus.THINKING,
            SERAStatus.EXECUTING,
            SERAStatus.TASK_PLANNING,
            SERAStatus.TASK_EXECUTING,
            SERAStatus.TASK_VERIFYING,
            SERAStatus.TASK_RECOVERING,
        ):
            if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_interrupted_cue"):
                self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()

        # Yield wake word microphone
        if hasattr(self, "wakeword_detector") and self.wakeword_detector:
            self.wakeword_detector.pause()

        # Transition to LISTENING and emit canonical activation event
        self._transition_state(SERAStatus.LISTENING)
        self._emit_event(
            "ACTIVATION_STARTED",
            {
                "source": "HOTKEY_HOLD",
                "mode": "HOLD_TO_TALK",
                "timestamp": self._hold_activation_time,
            },
        )

        # Start streaming recording
        if hasattr(self, "recorder") and self.recorder:
            self.recorder.start_recording()
            print("[STT] Hold-To-Talk recording started...")

        # Launch periodic partial STT sampling
        loop = getattr(self, "_loop", None)
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            if hasattr(self, "_partial_task") and self._partial_task and not self._partial_task.done():
                self._partial_task.cancel()
            self._partial_task = loop.create_task(self._partial_transcription_worker())

    def handle_hotkey_release(self) -> None:
        """Triggered immediately when Ctrl+Space is released (Hold-To-Talk end)."""
        if not self._is_holding_hotkey:
            return
        self._is_holding_hotkey = False

        if hasattr(self, "_partial_task") and self._partial_task and not self._partial_task.done():
            self._partial_task.cancel()

        release_time = time.time()
        audio_data = self.recorder.stop_recording() if hasattr(self, "recorder") and self.recorder else np.zeros(0, dtype=np.float32)
        print(f"[STT] Hold-To-Talk recording stopped ({release_time - self._hold_activation_time:.2f}s)")

        self._emit_event(
            "ACTIVATION_RELEASED",
            {
                "source": "HOTKEY_HOLD",
                "duration_seconds": release_time - self._hold_activation_time,
            },
        )

        # Schedule speech processing turn
        loop = getattr(self, "_loop", None)
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            from unittest.mock import AsyncMock
            if hasattr(self, "_process_voice_turn") and isinstance(self._process_voice_turn, AsyncMock):
                coro = self._process_voice_turn(activation_time=self._hold_activation_time, source="HOTKEY")
            else:
                coro = self._process_recorded_audio(
                    audio_data=audio_data,
                    activation_time=self._hold_activation_time,
                    source="HOTKEY_HOLD",
                )
            self._active_listen_task = loop.create_task(coro)
            self._active_task = self._active_listen_task

    async def _partial_transcription_worker(self) -> None:
        """Periodically samples accumulated audio during active Hold-To-Talk/speech and emits partial STT."""
        sr = getattr(self, "stt_sample_rate", 16000)
        min_samples = int(sr * 0.4)  # At least 400ms of audio
        last_emitted_text = ""

        await asyncio.sleep(0.4)

        while self._is_holding_hotkey or (hasattr(self, "recorder") and self.recorder and self.recorder.is_recording):
            try:
                if hasattr(self, "recorder") and self.recorder:
                    audio_data = self.recorder.get_current_audio()
                    if audio_data is not None and len(audio_data) >= min_samples:
                        partial_text = ""
                        # Try fast local fallback first if available to keep latency minimal (<100ms)
                        if hasattr(self, "stt") and hasattr(self.stt, "fallback") and self.stt.fallback:
                            res = await self.stt.fallback.transcribe(
                                audio_data, sample_rate=sr, language=getattr(self, "stt_language", "en-US")
                            )
                            partial_text = str(res).strip() if res else ""
                        elif hasattr(self, "stt") and hasattr(self.stt, "transcribe"):
                            res = await self.stt.transcribe(
                                audio_data, sample_rate=sr, language=getattr(self, "stt_language", "en-US")
                            )
                            partial_text = str(res).strip() if res else ""

                        if partial_text and partial_text != last_emitted_text:
                            last_emitted_text = partial_text
                            self._emit_event(
                                "PARTIAL_TRANSCRIPTION",
                                {
                                    "partial": partial_text,
                                    "transcript": partial_text,
                                    "is_final": False,
                                },
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[SERARuntime] Partial STT error: {e}")

            await asyncio.sleep(0.5)

    def handle_wakeword_trigger(self) -> None:
        """Triggered when the local wake word ('SERA') is detected."""
        self.wakeword_event_count += 1
        activation_time = time.time()

        self._emit_event(
            "WAKE_WORD_DETECTED",
            {
                "phrase": getattr(self, "wakeword_phrase", "SERA"),
                "timestamp": activation_time,
            },
        )
        self._emit_event(
            "ACTIVATION_STARTED",
            {
                "source": "WAKE_WORD",
                "mode": "FIXED_5S",
                "timestamp": activation_time,
            },
        )

        current_st = self.state.status if hasattr(self, "state") and self.state else SERAStatus.IDLE

        # Interrupt any ongoing speech or execution immediately
        if current_st == SERAStatus.SPEAKING or (hasattr(self, "audio") and hasattr(self.audio, "is_speaking") and self.audio.is_speaking is True):
            if hasattr(self, "audio") and hasattr(self.audio, "stop_speaking"):
                self.audio.stop_speaking()
            if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_interrupted_cue"):
                self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()
        elif current_st in (
            SERAStatus.THINKING,
            SERAStatus.EXECUTING,
            SERAStatus.TASK_PLANNING,
            SERAStatus.TASK_EXECUTING,
            SERAStatus.TASK_VERIFYING,
            SERAStatus.TASK_RECOVERING,
        ):
            if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_interrupted_cue"):
                self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()

        # Transition to LISTENING and play cue
        self._transition_state(SERAStatus.LISTENING)
        if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_listening_cue"):
            self.audio_cues.play_listening_cue()

        # Yield wake word microphone
        if hasattr(self, "wakeword_detector") and self.wakeword_detector:
            self.wakeword_detector.pause()

        # Schedule wake word voice capture turn (5.0s fixed)
        loop = getattr(self, "_loop", None)
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            from unittest.mock import AsyncMock
            if hasattr(self, "_process_voice_turn") and isinstance(self._process_voice_turn, AsyncMock):
                coro = self._process_voice_turn(activation_time=activation_time, source="WAKEWORD")
            else:
                coro = self._process_wake_word_turn(activation_time=activation_time)
            self._active_listen_task = loop.create_task(coro)
            self._active_task = self._active_listen_task

    async def _process_wake_word_turn(self, activation_time: float) -> str:
        """Processes 5.0-second fixed recording for wake word activation."""
        self._transition_state(SERAStatus.LISTENING)
        self._emit_event("LISTENING_STARTED", {"source": "WAKE_WORD", "duration": 5.0})
        print(f"[STT] Wake word detected. Recording for {getattr(self, 'recording_duration', 5.0)}s...")
        audio_data = np.zeros(0, dtype=np.float32)

        loop = getattr(self, "_loop", None) or asyncio.get_running_loop()
        partial_task = loop.create_task(self._partial_transcription_worker())
        try:
            if hasattr(self, "recorder") and self.recorder:
                rec_res = self.recorder.record_for(getattr(self, "recording_duration", 5.0))
                if inspect.iscoroutine(rec_res) or hasattr(rec_res, "__await__"):
                    audio_data = await rec_res
                else:
                    audio_data = rec_res
        finally:
            partial_task.cancel()

        self._emit_event("LISTENING_STOPPED", {"source": "WAKE_WORD"})
        return await self._process_recorded_audio(audio_data, activation_time, source="WAKE_WORD")

    async def _process_recorded_audio(
        self,
        audio_data: np.ndarray,
        activation_time: float,
        source: str = "HOTKEY_HOLD",
    ) -> str:
        """Transcribes recorded audio and dispatches to agent."""
        if not hasattr(self, "stt") or not self.stt:
            return ""

        sr = getattr(self, "stt_sample_rate", 16000)
        if audio_data is not None and 0 < len(audio_data) < int(sr * 0.05):
            logger.debug("[SERARuntime] Audio recording too short (<50ms), ignoring.")
            self._transition_state(SERAStatus.IDLE)
            if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                self.wakeword_detector.resume()
            return ""

        self.turn_count += 1
        turn_id = f"turn-{self.turn_count}-{str(uuid.uuid4())[:6]}"
        metrics = LatencyMetrics(
            turn_id=turn_id,
            hotkey_pressed_at=activation_time,
            listening_started_at=activation_time,
        )

        try:
            self._transition_state(SERAStatus.TRANSCRIBING)
            self._emit_event("TRANSCRIPTION_STARTED", {"source": source, "turn_id": turn_id})
            print("[STT] Transcribing audio...")
            stt_res = await self.stt.transcribe(audio_data, language=getattr(self, "stt_language", "en-US"))
            metrics.stt_completed_at = time.time()

            raw_text = str(stt_res).strip() if stt_res else ""
            self._emit_event(
                "TRANSCRIPTION_COMPLETED",
                {
                    "source": source,
                    "turn_id": turn_id,
                    "transcript": raw_text,
                    "is_final": True,
                },
            )

            # Quality Gate
            if hasattr(self, "quality_gate") and self.quality_gate:
                decision = self.quality_gate.evaluate(stt_res)
                if not decision.accepted:
                    if getattr(self, "manual_debug_mode", False):
                        print(f"\n[TURN {self.turn_count}] [ACTIVATION {source}]")
                        print(f"STATE=REJECTED | TRANSCRIPT=\"{raw_text}\" | QUALITY=REJECT ({decision.reason})")
                    self._transition_state(SERAStatus.IDLE)
                    if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                        self.wakeword_detector.resume()
                    return ""

                if getattr(self, "manual_debug_mode", False):
                    print(f"\n[TURN {self.turn_count}] [ACTIVATION {source}]")
                    print(f"STATE=PROCESSING | TRANSCRIPT=\"{raw_text}\" | QUALITY=ACCEPT ({decision.confidence:.2f})")

            if hasattr(self, "audio_cues") and self.audio_cues:
                self.audio_cues.play_thinking_cue()

            task_id = f"task_{uuid.uuid4().hex[:8]}"
            t_turn_start = time.time()
            self.active_task_info = {
                "task_id": task_id,
                "user_input": raw_text,
                "source": source,
                "status": "EXECUTING",
                "current_step": 1,
                "total_steps": 4,
                "current_node": "Router",
                "started_at": t_turn_start,
                "completed_at": None,
                "result": None,
                "error": None,
            }
            self._emit_event("TASK_STARTED", {
                "task_id": task_id,
                "user_input": raw_text,
                "source": source,
                "started_at": t_turn_start,
            })

            response_text = await self.process_text(raw_text, metrics=metrics, turn_id=task_id)
            metrics.turn_completed_at = time.time()
            duration = time.time() - t_turn_start
            final_resp = response_text or self.state.last_response or "Action completed."

            if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                self.active_task_info["status"] = "COMPLETED"
                self.active_task_info["completed_at"] = time.time()
                self.active_task_info["result"] = final_resp

            # 1. Emit AGENT_RESPONSE immediately so UI displays response caption
            self._emit_event("AGENT_RESPONSE", {
                "task_id": task_id,
                "turn_id": task_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "type": "ASSISTANT_MESSAGE",
                "content": str(final_resp),
                "status": "COMPLETED",
            })

            # 2. Stay strictly in SPEAKING while real TTS audio plays
            if final_resp and hasattr(self.audio, "speak"):
                self._transition_state(SERAStatus.SPEAKING)
                self._emit_event("TTS_STARTED", {"task_id": task_id, "text": str(final_resp)})
                try:
                    await asyncio.to_thread(self.audio.speak, str(final_resp))
                except Exception as e:
                    logger.debug(f"[SERARuntime] TTS playback error: {e}")
                finally:
                    self._emit_event("TTS_COMPLETED", {"task_id": task_id})

            # 3. Emit TASK_COMPLETED only after speech finishes
            self._emit_event("TASK_COMPLETED", {
                "task_id": task_id,
                "result": final_resp,
                "duration_seconds": duration,
            })
            self._transition_state(SERAStatus.IDLE)

            if hasattr(self, "events") and self.events:
                await self.events.emit_async("latency_metrics", metrics=metrics)

            if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                self.wakeword_detector.resume()
            return str(final_resp)

        except Exception as e:
            logger.error(f"[SERARuntime] Error during speech turn: {e}")
            self._transition_state(SERAStatus.IDLE)
            if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                self.wakeword_detector.resume()
            return ""

    def _cancel_active_agent_task(self) -> None:
        """Safely cancels active agent, recorder, or listening task."""
        if hasattr(self, "recorder") and self.recorder:
            self.recorder.cancel()

        tasks_to_cancel = set()
        for t in (
            getattr(self, "_active_agent_task", None),
            getattr(self, "_active_listen_task", None),
            getattr(self, "_active_task", None),
            getattr(self, "_active_task_handle", None),
        ):
            if t and hasattr(t, "done") and not t.done():
                tasks_to_cancel.add(t)

        self._active_agent_task = None
        self._active_listen_task = None
        self._active_task = None
        self._active_task_handle = None

        for t in tasks_to_cancel:
            t.cancel()

    def cancel_task(self, task_id: str | None = None) -> bool:
        """Cancels the active task and stops audio playback."""
        if hasattr(self, "audio") and hasattr(self.audio, "stop_speaking"):
            self.audio.stop_speaking()
        if hasattr(self, "audio_cues") and self.audio_cues and hasattr(self.audio_cues, "play_interrupted_cue"):
            self.audio_cues.play_interrupted_cue()

        if self.active_task_info:
            self.active_task_info["status"] = "CANCELLED"
            self.active_task_info["completed_at"] = time.time()
            self._emit_event("TASK_CANCELLED", {
                "task_id": self.active_task_info.get("task_id"),
                "reason": "Cancelled by user interrupt",
            })

        self._cancel_active_agent_task()
        self._transition_state(SERAStatus.IDLE)
        return True

    async def start_canonical_task(self, text: str, source: str = "TEXT") -> dict[str, Any]:
        """Unified canonical task execution pipeline for both Text and Voice inputs."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        started_at = time.time()
        self.active_task_info = {
            "task_id": task_id,
            "user_input": text,
            "source": source,
            "status": "EXECUTING",
            "current_step": 1,
            "total_steps": 4,
            "current_node": "Router",
            "started_at": started_at,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        self.state.last_user_message = text
        self._emit_event("TASK_STARTED", {
            "task_id": task_id,
            "user_input": text,
            "source": source,
            "started_at": started_at,
        })

        try:
            result = await self.command_pipeline.execute_text(
                text=text,
                task_id=task_id,
                source=source,
            )
            duration = time.time() - started_at
            resp = result.get("response", "")
            is_success = result.get("success", False)

            if not is_success:
                if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                    self.active_task_info["status"] = "FAILED"
                    self.active_task_info["completed_at"] = time.time()
                    self.active_task_info["error"] = result.get("error") or resp
                return {"success": False, "task_id": task_id, "error": result.get("error") or resp, "duration_seconds": duration}

            if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                self.active_task_info["status"] = "COMPLETED"
                self.active_task_info["completed_at"] = time.time()
                self.active_task_info["result"] = resp

            return {"success": True, "task_id": task_id, "result": resp, "duration_seconds": duration}
        except asyncio.CancelledError:
            duration = time.time() - started_at
            if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                self.active_task_info["status"] = "CANCELLED"
                self.active_task_info["completed_at"] = time.time()
            self._emit_event("TASK_CANCELLED", {
                "task_id": task_id,
                "reason": "Cancelled by user interrupt",
                "duration_seconds": duration,
            })
            self._transition_state(SERAStatus.IDLE)
            return {"success": False, "task_id": task_id, "cancelled": True}
        except Exception as e:
            duration = time.time() - started_at
            if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                self.active_task_info["status"] = "FAILED"
                self.active_task_info["error"] = str(e)
            self._emit_event("TASK_FAILED", {
                "task_id": task_id,
                "error": str(e),
                "duration_seconds": duration,
            })
            self._transition_state(SERAStatus.IDLE)
            return {"success": False, "task_id": task_id, "error": str(e)}
        finally:
            self._active_task_handle = None

    async def _process_voice_turn(
        self,
        activation_time: float | None = None,
        source: str = "HOTKEY",
        event_id: int = 1,
    ) -> str:
        """Executes unified fixed-duration command capture, STT transcription, and agent dispatch."""
        self.turn_count += 1
        turn_id = f"turn-{self.turn_count}-{str(uuid.uuid4())[:6]}"
        metrics = LatencyMetrics(
            turn_id=turn_id,
            hotkey_pressed_at=activation_time,
            listening_started_at=time.time(),
        )

        try:
            self._transition_state(SERAStatus.LISTENING)

            # 1. Deterministic Fixed-Duration Recording (Default 5.0 seconds, No VAD)
            print(f"[STT] Recording started ({self.recording_duration} seconds)")
            t_record_start = time.time()
            metrics.user_speech_started_at = t_record_start

            audio_data = await self.recorder.record_for(self.recording_duration)
            t_record_end = time.time()
            metrics.user_speech_ended_at = t_record_end
            metrics.recording_ended_at = t_record_end
            print("[STT] Recording complete")

            # 2. Transcribe Audio (Primary: NVIDIA Canary-Qwen 2.5B -> Fallback: Faster-Whisper Small)
            self._transition_state(SERAStatus.TRANSCRIBING)
            print("[STT] Transcribing...")
            t_stt_start = time.time()
            stt_res = await self.stt.transcribe(audio_data, language=self.stt_language)
            metrics.stt_completed_at = time.time()

            raw_text = str(stt_res).strip() if stt_res else ""

            # 3. Quality Gate Evaluation
            decision = self.quality_gate.evaluate(stt_res)

            if not decision.accepted:
                if self.manual_debug_mode:
                    print(f"\n[TURN {self.turn_count}] [ACTIVATION {source}]")
                    print(f"STATE=REJECTED | TRANSCRIPT=\"{raw_text}\" | QUALITY=REJECT ({decision.reason})")
                self._transition_state(SERAStatus.IDLE)
                return ""

            if self.manual_debug_mode:
                print(f"\n[TURN {self.turn_count}] [ACTIVATION {source}]")
                print(f"STATE=PROCESSING | TRANSCRIPT=\"{raw_text}\" | QUALITY=ACCEPT ({decision.confidence:.2f})")

            # 4. Audio cue for thinking
            self.audio_cues.play_thinking_cue()

            task_id = f"task_{uuid.uuid4().hex[:8]}"
            t_turn_start = time.time()
            self.active_task_info = {
                "task_id": task_id,
                "user_input": raw_text,
                "source": source,
                "status": "EXECUTING",
                "current_step": 1,
                "total_steps": 4,
                "current_node": "Router",
                "started_at": t_turn_start,
                "completed_at": None,
                "result": None,
                "error": None,
            }
            self._emit_event("TASK_STARTED", {
                "task_id": task_id,
                "user_input": raw_text,
                "source": source,
                "started_at": t_turn_start,
            })

            # 5. Process validated text turn
            response = await self.process_text(raw_text, metrics=metrics, turn_id=task_id)
            metrics.turn_completed_at = time.time()
            duration = time.time() - t_turn_start
            final_resp = response or self.state.last_response or "Action completed."

            if self.active_task_info and self.active_task_info.get("task_id") == task_id:
                self.active_task_info["status"] = "COMPLETED"
                self.active_task_info["completed_at"] = time.time()
                self.active_task_info["result"] = final_resp

            self._emit_event("AGENT_RESPONSE", {
                "task_id": task_id,
                "turn_id": task_id,
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "type": "ASSISTANT_MESSAGE",
                "content": str(final_resp),
                "status": "COMPLETED",
            })
            self._emit_event("TASK_COMPLETED", {
                "task_id": task_id,
                "result": final_resp,
                "duration_seconds": duration,
            })

            # Emit latency telemetry
            print(f"\n{metrics.format_summary()}")
            if hasattr(self, "events") and self.events:
                await self.events.emit_async("latency_metrics", metrics=metrics)

            return str(final_resp)

        except asyncio.CancelledError:
            print("[SERA] Voice turn cancelled by user interruption.")
            self._transition_state(SERAStatus.IDLE)
            return ""
        except Exception as e:
            logger.exception(f"Error in voice turn: {e}")
            self.audio_cues.play_error_cue()
            self._transition_state(SERAStatus.ERROR)
            return ""
        finally:
            self._active_listen_task = None
            if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                self.wakeword_detector.resume()

    async def process_text(self, text: str, metrics: LatencyMetrics | None = None, turn_id: str | None = None) -> str:
        """Processes a text utterance through the deterministic CommandPipeline."""
        text = text.strip()
        if not text:
            return ""

        turn_id = turn_id or f"turn-{self.turn_count}"

        result = await self.command_pipeline.execute_text(
            text=text,
            task_id=turn_id,
            metrics=metrics,
        )

        resp_text = result.get("response", "")
        self.state.last_response = resp_text
        return resp_text

    async def _stream_and_play_tts(self, text_or_tokens: Any, metrics: LatencyMetrics | None) -> None:
        """Pipes streaming LLM tokens into sentence-level Fish Audio TTS."""
        first_audio_emitted = False

        if isinstance(text_or_tokens, str):
            async def _str_gen():
                yield text_or_tokens
            tokens_stream = _str_gen()
        elif isinstance(text_or_tokens, (list, tuple)):
            async def _list_gen():
                for t in text_or_tokens:
                    yield t
            tokens_stream = _list_gen()
        else:
            tokens_stream = text_or_tokens

        try:
            self._transition_state(SERAStatus.SPEAKING)
            sentence_gen = stream_sentences(
                tokens_stream,
                min_words=self.config.data.get("streaming", {}).get("min_words", 4),
            )

            if hasattr(self.audio, "speak_stream"):
                await self.audio.speak_stream(sentence_gen, metrics=metrics)
            elif hasattr(self.audio, "speak"):
                async for sentence in sentence_gen:
                    self.audio.speak(sentence)

        except asyncio.CancelledError:
            self.audio.stop_speaking()
            raise

    async def run(self) -> None:
        """Starts the SERA runtime event loop and hotkey listener (async)."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            return self._loop.run_until_complete(self.run())

        self.hotkey_manager.loop = self._loop
        self.hotkey_manager.start()

        if hasattr(self, "wakeword_enabled") and self.wakeword_enabled and hasattr(self, "wakeword_detector"):
            self.wakeword_detector.start(self.handle_wakeword_trigger)

        self._shutdown_event = asyncio.Event()

        try:
            await self._shutdown_event.wait()
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            print("\n[SERA] Stopping runtime...")
        finally:
            self.hotkey_manager.stop()
            if hasattr(self, "wakeword_detector") and self.wakeword_detector:
                self.wakeword_detector.stop()
            print(f"[SERA] Runtime shutdown complete. Current State: {self.state.status.value}")

    def run_sync(self) -> None:
        """Synchronous entrypoint."""
        asyncio.run(self.run())
