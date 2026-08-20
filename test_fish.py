print("SERA TEST STARTED")

import os

print("Loading environment...")

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FISH_API_KEY")

if not api_key:
    print("ERROR: FISH_API_KEY was not found.")
    print("Check your .env file.")
    exit(1)

print("Fish API key found.")
print("Loading Fish Audio SDK...")

from fishaudio import FishAudio

print("Fish Audio SDK loaded.")

client = FishAudio(api_key=api_key)

print("Fish Audio client created.")
print("Sending request to Fish Audio...")

audio = client.tts.convert(
    text="Hello. I am SERA. All systems are operational.",
    model="s2.1-pro-free",
    format="mp3",
)

print("Speech generated successfully.")

with open("sera_test.mp3", "wb") as f:
    f.write(audio)

print("Saved: sera_test.mp3")
print("SERA TEST COMPLETE.")