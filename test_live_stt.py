from app.speech.stt import SERA_STT


def main():

    print("=" * 60)
    print("SERA LIVE SPEECH RECOGNITION")
    print("=" * 60)

    stt = SERA_STT()

    print("\nSay something.")
    print("Stop speaking when you are finished.")
    print("Press Ctrl+C to exit.\n")

    while True:

        text = stt.listen_once()

        if text:

            print("\n" + "=" * 60)
            print("SERA HEARD:")
            print(text)
            print("=" * 60)


if __name__ == "__main__":
    main()