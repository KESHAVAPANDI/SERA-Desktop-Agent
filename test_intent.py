from app.core.intent import LocalIntentRouter


def main():

    router = LocalIntentRouter()

    tests = [
        "set my brightness to 30%",
        "make the brightness 75",
        "set my volume to 40%",
        "make the sound 20%",
        "mute my computer",
        "unmute my computer",
        "what is my battery percentage?",
        "open chrome",
    ]

    print("=" * 60)
    print("SERA LOCAL INTENT TEST")
    print("=" * 60)

    for text in tests:

        result = router.detect(text)

        print(
            f"\nUser: {text}"
        )

        print(
            f"Intent: {result}"
        )


if __name__ == "__main__":
    main()