import os
import sys

# Ensure CUDA and cuDNN DLLs are found on Windows
if sys.platform == "win32":
    cuda_paths = [
        r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
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

from faster_whisper import WhisperModel
import time


AUDIO_FILE = "sera_test.wav"


print("=" * 50)
print("SERA SPEECH RECOGNITION TEST")
print("=" * 50)

print("\nLoading Whisper...")

try:
    model = WhisperModel(
        "small",
        device="cuda",
        compute_type="float16"
    )
    print("Whisper loaded (GPU - CUDA).")
except Exception as e:
    print(f"CUDA initialization failed ({e}), falling back to CPU...")
    model = WhisperModel(
        "small",
        device="cpu",
        compute_type="int8"
    )
    print("Whisper loaded (CPU).")

print("\nTranscribing...")

start_time = time.time()

segments, info = model.transcribe(
    AUDIO_FILE,
    beam_size=5,
    vad_filter=True
)

text = ""

for segment in segments:
    text += segment.text

elapsed = time.time() - start_time

print("\n" + "=" * 50)
print("TRANSCRIPTION")
print("=" * 50)

print(text.strip())

print("\n" + "=" * 50)
print(f"Processing time: {elapsed:.2f} seconds")
print(f"Detected language: {info.language}")
print("=" * 50)