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


print("=" * 50)
print("SERA WHISPER TEST")
print("=" * 50)

print("\nLoading Whisper model...")

model = WhisperModel(
    "small",
    device="cuda",
    compute_type="float16"
)

print("Whisper model loaded successfully.")
print("GPU inference is working.")