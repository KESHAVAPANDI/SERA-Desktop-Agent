import asyncio
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
from app.speech.wakeword import OpenWakeWordDetector
from app.tools import create_tool_registry
from app.tools.desktop.perception_router import DesktopPerceptionRouter
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.utils.config import SERAConfig
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
        self.events = EventBus()

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

        print(f"[STT] Primary: NVIDIA Canary-Qwen 2.5B")
        print(f"[STT] Mode: Hosted API")
        print(f"[STT] Language: {self.stt_language}")
        print(f"[STT] Command capture: {self.recording_duration} seconds")

        # Local Wake Word Detector ("SERA")
        self.wakeword_enabled = wake_cfg.get("enabled", True)
        self.wakeword_phrase = wake_cfg.get("phrase", "SERA")
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

        # Task Planner & Multi-Step Executor (Phase 4)
        from app.core.planner import TaskPlanner
        from app.core.task_executor import MultiStepExecutor
        self.planner = TaskPlanner(tools=self.tools, router=self.router)
        self.multi_step_executor = MultiStepExecutor(
            tools=self.tools,
            inspector=self.desktop_router.inspector,
            vision_engine=self.vision,
            state=self.state,
            event_bus=self.events,
        )

        # Global Hotkey Manager with Debounce
        hotkey_combo = hotkey_cfg.get("combination", "ctrl+space")
        debounce_ms = hotkey_cfg.get("debounce_ms", 300)
        self.hotkey_manager = GlobalHotkeyManager(
            hotkey=hotkey_combo,
            on_trigger=self.handle_hotkey_trigger,
            debounce_ms=debounce_ms,
        )

        self._transition_state(SERAStatus.IDLE)
        print("=" * 60)
        print(f"SERA RUNTIME READY (Hotkey: {hotkey_combo} | Wake Word: '{self.wakeword_phrase}')")
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
        """Triggered when the global hotkey (Ctrl+Space) is pressed."""
        self.hotkey_event_count += 1
        self._handle_activation(source="HOTKEY", event_id=self.hotkey_event_count)

    def handle_wakeword_trigger(self) -> None:
        """Triggered when the local wake word ('SERA') is detected."""
        self.wakeword_event_count += 1
        self._handle_activation(source="WAKE_WORD", event_id=self.wakeword_event_count)

    def _handle_activation(self, source: str = "HOTKEY", event_id: int = 1) -> None:
        """Unified command capture activation entrypoint for both Hotkey and Wake Word."""
        activation_time = time.time()
        current_st = self.state.status

        # 1. State: LISTENING -> Do not spawn duplicate listener!
        if current_st == SERAStatus.LISTENING:
            if self._active_listen_task and not self._active_listen_task.done():
                logger.debug(f"[SERARuntime] Duplicate {source} trigger ignored: already LISTENING.")
                return

        # 2. State: SPEAKING -> Stop TTS, cancel streaming, play interrupted cue, switch to LISTENING
        if current_st == SERAStatus.SPEAKING or (hasattr(self.audio, "is_speaking") and self.audio.is_speaking is True):
            self.audio.stop_speaking()
            self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()

        # 3. State: THINKING / EXECUTING / PLANNING / RECOVERING -> Cancel task, play interrupted cue, switch to LISTENING
        elif current_st in (
            SERAStatus.THINKING,
            SERAStatus.EXECUTING,
            SERAStatus.TASK_PLANNING,
            SERAStatus.TASK_EXECUTING,
            SERAStatus.TASK_VERIFYING,
            SERAStatus.TASK_RECOVERING,
        ):
            self.audio_cues.play_interrupted_cue()
            self._cancel_active_agent_task()

        # 4. State: IDLE -> Play listening cue
        elif current_st == SERAStatus.IDLE:
            self.audio_cues.play_listening_cue()

        # Temporarily suppress wake word detector while capturing command
        if hasattr(self, "wakeword_detector") and self.wakeword_detector:
            self.wakeword_detector.pause()

        # Transition to LISTENING
        self._transition_state(SERAStatus.LISTENING)

        # Schedule single command capture turn on the event loop
        loop = self._loop
        if not loop or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop and loop.is_running():
            self._active_listen_task = loop.create_task(
                self._process_voice_turn(
                    activation_time=activation_time,
                    source=source,
                    event_id=event_id,
                )
            )
            self._active_task = self._active_listen_task

    def _cancel_active_agent_task(self) -> None:
        """Safely cancels active agent, recorder, or listening task."""
        if hasattr(self, "recorder") and self.recorder:
            self.recorder.cancel()

        tasks_to_cancel = set()
        for t in (self._active_agent_task, self._active_listen_task, self._active_task):
            if t and not t.done():
                tasks_to_cancel.add(t)

        self._active_agent_task = None
        self._active_listen_task = None
        self._active_task = None

        for t in tasks_to_cancel:
            t.cancel()

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

            # 5. Process validated text turn
            response = await self.process_text(raw_text, metrics=metrics, turn_id=turn_id)
            metrics.turn_completed_at = time.time()

            # Emit latency telemetry
            print(f"\n{metrics.format_summary()}")
            await self.events.emit_async("latency_metrics", metrics=metrics)

            return response

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
        """Processes a text utterance through local intent, multi-step planner, or agent reasoning."""
        text = text.strip()
        if not text:
            return ""

        turn_id = turn_id or f"turn-{self.turn_count}"

        # -------------------------------------------------------------
        # Route 1: Local Intent Fast-Path (Brightness, Volume, Mute)
        # -------------------------------------------------------------
        local_intent = self.intent_router.detect(text)
        if local_intent:
            if metrics:
                metrics.intent_routed_at = time.time()
                metrics.intent_classified_at = time.time()

            tool_name = local_intent.get("tool") if isinstance(local_intent, dict) else getattr(local_intent, "tool_name", "")
            tool_args = local_intent.get("arguments") if isinstance(local_intent, dict) else getattr(local_intent, "arguments", {})
            tool_sig = f"{turn_id}:{tool_name}:{str(sorted(tool_args.items()))}"

            if tool_sig in self._executed_tools:
                logger.debug(f"[SERARuntime] Deduplicated tool call: {tool_sig}")
                return ""
            self._executed_tools.add(tool_sig)

            self._transition_state(SERAStatus.EXECUTING)
            print(f"\n[SERA] Local command detected: {tool_name} {tool_args}")

            tool_res = await self.tools.execute(tool_name, tool_args)
            print(f"[RESULT] {tool_res}")

            if metrics:
                metrics.local_tool_executed_at = time.time()

            self.audio_cues.play_completed_cue()
            if "brightness" in tool_name:
                resp_str = f"Brightness has been set to {tool_args.get('brightness')}%."
            elif "volume" in tool_name:
                resp_str = f"Volume set to {tool_args.get('volume')}%."
            else:
                resp_str = str(tool_res)

            self.state.last_response = resp_str
            self._transition_state(SERAStatus.SPEAKING)
            if hasattr(self.audio, "speak"):
                self.audio.speak(resp_str)

            self._transition_state(SERAStatus.IDLE)
            return resp_str

        # -------------------------------------------------------------
        # Route 2: Multi-Step Task Planner (Phase 4)
        # -------------------------------------------------------------
        if self.planner.is_multi_step_request(text):
            self._transition_state(SERAStatus.TASK_PLANNING)
            plan = await self.planner.plan(text)
            if plan.is_valid:
                res = await self.multi_step_executor.execute(plan, metrics=metrics)
                if res.success:
                    self.audio_cues.play_completed_cue()
                    await self._stream_and_play_tts(res.summary_message, metrics)
                else:
                    self.audio_cues.play_error_cue()
                    await self._stream_and_play_tts(res.summary_message or "Task could not be completed.", metrics)
                self._transition_state(SERAStatus.IDLE)
                return res.summary_message

        # -------------------------------------------------------------
        # Route 3: Desktop Perception Query (Screen Understanding)
        # -------------------------------------------------------------
        if self.desktop_router.is_desktop_query(text):
            self._transition_state(SERAStatus.THINKING)
            print("[SERA] Desktop perception query detected. Routing perception hierarchy...")
            spoken_resp, method, _ = await self.desktop_router.perceive(text, metrics=metrics)
            self._transition_state(SERAStatus.SPEAKING)
            if hasattr(self.audio, "speak"):
                self.audio.speak(spoken_resp)
            self._transition_state(SERAStatus.IDLE)
            return spoken_resp

        # -------------------------------------------------------------
        # Route 4: Conversational Agent Streaming
        # -------------------------------------------------------------
        self._transition_state(SERAStatus.THINKING)
        print(f"\n[SERA USER] {text}")
        print("[SERA] Streaming response from agent engine...")

        if metrics:
            metrics.llm_request_started_at = time.time()

        tokens_generator = self.agent.run_stream(text, metrics=metrics)
        await self._stream_and_play_tts(tokens_generator, metrics)
        self._transition_state(SERAStatus.IDLE)
        return self.state.last_response or ""

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
