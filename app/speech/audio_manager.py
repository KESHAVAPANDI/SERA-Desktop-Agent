import asyncio
import io
import logging
import threading
import time
from typing import AsyncIterator, Callable
import sounddevice as sd
from scipy.io.wavfile import read as read_wav

from app.speech.stt import SERA_STT
from app.speech.tts import FishTTS

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages microphone VAD listening, concurrent streaming TTS playback, and audio device state."""

    def __init__(
        self,
        stt: SERA_STT | None = None,
        tts: FishTTS | None = None,
        audio_config: dict | None = None,
        models_config: dict | None = None,
    ):
        audio_cfg = audio_config or {}
        models_cfg = models_config or {}

        stt_cfg = models_cfg.get("stt", {})
        tts_cfg = models_cfg.get("tts", {})

        self.stt = stt or SERA_STT(
            model_size=stt_cfg.get("model", "small"),
            sample_rate=audio_cfg.get("sample_rate", 16000),
            energy_threshold=audio_cfg.get("energy_threshold", 0.03),
            silence_duration=audio_cfg.get("silence_duration", 0.8),
            max_recording_duration=audio_cfg.get("max_recording_duration", 15),
        )

        self.tts = tts or FishTTS(
            model=tts_cfg.get("model", "s2.1-pro-free"),
            reference_id=tts_cfg.get("reference_id"),
        )

        self._is_speaking = False
        self._is_listening = False
        self._interrupted = False
        self._lock = threading.Lock()
        self._active_stream_tasks: list[asyncio.Task] = []

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    def stop_speaking(self) -> None:
        """Immediately halts any current TTS playback, cancels active streaming tasks, and resets speaking state."""
        with self._lock:
            self._interrupted = True
            self._is_speaking = False

            # 1. Stop audio device stream
            try:
                sd.stop()
            except Exception as e:
                logger.debug(f"[AudioManager] sd.stop error: {e}")

            # 2. Cancel active streaming tasks
            for task in self._active_stream_tasks:
                if not task.done():
                    task.cancel()
            self._active_stream_tasks.clear()

    def speak(self, text: str, on_playback_start: Callable[[], None] | None = None) -> None:
        """Plays speech output for single-sentence/short responses with immediate interruptibility."""
        if not text or not text.strip():
            return

        with self._lock:
            self._interrupted = False
            self._is_speaking = True

        try:
            cleaned_text = text.strip()
            # Generate speech audio
            audio_bytes = self.tts.client.tts.convert(
                text=cleaned_text,
                model=self.tts.model,
                reference_id=self.tts.reference_id,
                format="wav",
                config=getattr(self.tts, "config", None) or __import__("fishaudio.types.tts", fromlist=["TTSConfig"]).TTSConfig(temperature=0.3, top_p=0.7),
            )

            if self._interrupted:
                return

            rate, data = read_wav(io.BytesIO(audio_bytes))

            if on_playback_start:
                try:
                    on_playback_start()
                except Exception:
                    pass

            sd.play(data, rate)

            # Wait while audio is playing, checking for interruption flag
            while sd.get_stream() and sd.get_stream().active:
                if self._interrupted:
                    sd.stop()
                    break
                time.sleep(0.01)

        except Exception as e:
            logger.error(f"[AudioManager] Error during TTS playback: {e}")
        finally:
            with self._lock:
                self._is_speaking = False

    async def speak_stream(
        self,
        sentence_stream: AsyncIterator[str],
        metrics=None,
        on_playback_start: Callable[[], None] | None = None,
    ) -> None:
        """Plays speech output sentence-by-sentence using an asynchronous producer-consumer queue."""
        with self._lock:
            self._interrupted = False
            self._is_speaking = True

        # Bounded queue for backpressure
        audio_queue: asyncio.Queue = asyncio.Queue(maxsize=3)
        loop = asyncio.get_running_loop()

        async def _tts_producer():
            try:
                is_first = True
                async for sentence in sentence_stream:
                    if self._interrupted:
                        break

                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # Record first sentence timestamp
                    if is_first and metrics and metrics.first_sentence_at is None:
                        metrics.first_sentence_at = time.time()
                        is_first = False

                    # Generate audio chunk in thread pool
                    def _gen():
                        return self.tts.client.tts.convert(
                            text=sentence,
                            model=self.tts.model,
                            reference_id=self.tts.reference_id,
                            format="wav",
                            config=getattr(self.tts, "config", None) or __import__("fishaudio.types.tts", fromlist=["TTSConfig"]).TTSConfig(temperature=0.3, top_p=0.7),
                        )

                    audio_bytes = await loop.run_in_executor(None, _gen)

                    if self._interrupted:
                        break

                    rate, data = read_wav(io.BytesIO(audio_bytes))
                    await audio_queue.put((rate, data))

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[AudioManager] Error in TTS Producer: {e}")
            finally:
                # Sentinel to signal playback consumer completion
                await audio_queue.put(None)

        async def _playback_consumer():
            first_chunk = True
            try:
                while not self._interrupted:
                    item = await audio_queue.get()
                    if item is None:
                        audio_queue.task_done()
                        break

                    rate, data = item

                    if self._interrupted:
                        audio_queue.task_done()
                        break

                    if first_chunk:
                        first_chunk = False
                        if metrics:
                            metrics.first_audio_played_at = time.time()
                            metrics.tts_playback_started_at = time.time()
                        if on_playback_start:
                            try:
                                on_playback_start()
                            except Exception:
                                pass

                    sd.play(data, rate)

                    # Wait while audio is playing, checking for interruption flag
                    while sd.get_stream() and sd.get_stream().active:
                        if self._interrupted:
                            sd.stop()
                            break
                        await asyncio.sleep(0.01)

                    audio_queue.task_done()

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[AudioManager] Error in Playback Consumer: {e}")

        # Launch concurrent producer and consumer
        producer_task = asyncio.create_task(_tts_producer())
        consumer_task = asyncio.create_task(_playback_consumer())

        with self._lock:
            self._active_stream_tasks = [producer_task, consumer_task]

        try:
            await asyncio.gather(producer_task, consumer_task)
        finally:
            with self._lock:
                self._is_speaking = False
                self._active_stream_tasks.clear()

    def listen_once(self) -> str:
        """Listens via microphone and returns transcribed text using VAD silence detection."""
        with self._lock:
            self._is_listening = True

        try:
            return self.stt.listen_once()
        finally:
            with self._lock:
                self._is_listening = False
