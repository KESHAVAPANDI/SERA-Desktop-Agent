import sounddevice as sd
from scipy.io.wavfile import write


SAMPLE_RATE = 16000
DURATION = 5


print("=" * 50)
print("SERA MICROPHONE RECORDING TEST")
print("=" * 50)

print("\nRecording for 5 seconds...")
print("Say:")
print('"Hello SERA, this is a microphone test."')

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16"
)

sd.wait()

print("Recording finished.")

write(
    "sera_test.wav",
    SAMPLE_RATE,
    audio
)

print("Saved: sera_test.wav")