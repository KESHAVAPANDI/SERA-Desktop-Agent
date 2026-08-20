from dotenv import load_dotenv

from app.speech.tts import FishTTS


load_dotenv()


def main():

    tts = FishTTS(
        model="s2.1-pro-free"
    )

    texts = [
        "Hello. I am SERA.",
        "The brightness has been set to thirty percent.",
        "I've opened Notepad for you.",
        "Your computer is currently connected to Wi-Fi.",
    ]

    for text in texts:

        print(
            f"\nGenerating: {text}"
        )

        tts.speak(text)


if __name__ == "__main__":
    main()