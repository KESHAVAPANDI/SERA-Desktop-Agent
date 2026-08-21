from dataclasses import dataclass
import os
import queue
import sys
import time

# Ensure CUDA and cuDNN DLL directories are accessible on Windows
if sys.platform == "win32":
    cuda_paths = [
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
    ]
    for p in cuda_paths:
        if os.path.exists(os.path.join(p, "cublas64_12.dll")):
            try:
                os.add_dll_directory(p)
            except AttributeError:
                pass
            os.environ["PATH"] = p + os.path.pathsep + os.environ["PATH"]
            break

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


@dataclass
class TranscriptionResult:
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    compression_ratio: float = 1.0
    duration: float = 0.0
    segments_count: int = 0

    def __str__(self) -> str:
        return self.text

    def __bool__(self) -> bool:
        return bool(self.text and self.text.strip())


class SERA_STT:

    def __init__(
        self,
        model_size="small",
        sample_rate=16000,
        block_duration=0.1,
        silence_duration=0.8,
        min_speech_duration_ms=250,
        max_recording_duration=15,
        energy_threshold=0.03,
    ):
        self.sample_rate = sample_rate
        self.block_size = int(sample_rate * block_duration)
        self.silence_duration = silence_duration
        self.min_speech_duration_s = max(0.1, min_speech_duration_ms / 1000.0)
        # Guard: If model_size is an API model identifier (e.g. nvidia/canary-qwen-2.5b), default Whisper to 'small'
        if "nvidia" in str(model_size).lower() or "canary" in str(model_size).lower() or "/" in str(model_size):
            model_size = "small"

        print("Loading SERA speech recognition model...")

        try:
            self.model = WhisperModel(
                model_size,
                device="cuda",
                compute_type="float16",
            )
            print("SERA STT ready (GPU - CUDA).")
        except Exception as e:
            print(f"CUDA initialization failed ({e}), falling back to CPU...")
            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
            )
            print("SERA STT ready (CPU).")

    def _calculate_energy(self, audio):
        return float(np.sqrt(np.mean(np.square(audio))))

    def listen_once(self) -> TranscriptionResult:
        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"Microphone status: {status}")
            audio_queue.put(indata[:, 0].copy())

        print("\nSERA is listening...")

        recording = []
        speech_started = False
        silence_start = None
        recording_start = None

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.block_size,
            callback=callback,
        ):
            while True:
                audio_chunk = audio_queue.get()
                energy = self._calculate_energy(audio_chunk)

                # --------------------------------
                # Waiting for speech
                # --------------------------------
                if not speech_started:
                    if energy >= self.energy_threshold:
                        speech_started = True
                        recording_start = time.time()
                        print("Speech detected.")
                        recording.append(audio_chunk)
                    continue

                # --------------------------------
                # Recording speech
                # --------------------------------
                recording.append(audio_chunk)

                if energy < self.energy_threshold:
                    if silence_start is None:
                        silence_start = time.time()

                    silence_elapsed = time.time() - silence_start
                    if silence_elapsed >= self.silence_duration:
                        break
                else:
                    silence_start = None

                # Maximum recording time
                if time.time() - recording_start >= self.max_recording_duration:
                    break

        if not recording:
            return TranscriptionResult(text="")

        total_duration = len(recording) * (self.block_size / self.sample_rate)
        if total_duration < self.min_speech_duration_s:
            return TranscriptionResult(text="", duration=total_duration)

        audio = np.concatenate(recording)
        print("Transcribing...")

        segments, info = self.model.transcribe(
            audio,
            language="en",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            temperature=0.0,
        )

        segments_list = list(segments)
        text_parts = []
        avg_logprobs = []
        no_speech_probs = []
        compression_ratios = []

        for s in segments_list:
            if s.text:
                text_parts.append(s.text.strip())
            avg_logprobs.append(s.avg_logprob)
            no_speech_probs.append(s.no_speech_prob)
            compression_ratios.append(s.compression_ratio)

        final_text = " ".join(text_parts).strip()
        mean_avg_logprob = float(np.mean(avg_logprobs)) if avg_logprobs else 0.0
        mean_no_speech = float(np.mean(no_speech_probs)) if no_speech_probs else 0.0
        mean_compression = float(np.mean(compression_ratios)) if compression_ratios else 1.0

        return TranscriptionResult(
            text=final_text,
            avg_logprob=mean_avg_logprob,
            no_speech_prob=mean_no_speech,
            compression_ratio=mean_compression,
            duration=total_duration,
            segments_count=len(segments_list),
        )


# Alias for backward compatibility
SpeechToText = SERA_STT