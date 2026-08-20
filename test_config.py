from app.utils.config import SERAConfig


def main():

    config = SERAConfig()

    print("=" * 60)
    print("SERA CONFIG TEST")
    print("=" * 60)

    print(
        "\nAssistant:",
        config.assistant_name,
    )

    for role in [
        "reasoning",
        "vision",
        "fast",
        "fallback",
        "tts",
        "stt",
    ]:

        settings = config.model_config(
            role
        )

        print(
            f"\n{role.upper()}"
        )

        print(
            f"  Provider: "
            f"{settings.get('provider')}"
        )

        print(
            f"  Model: "
            f"{settings.get('model')}"
        )

        if "device" in settings:

            print(
                f"  Device: "
                f"{settings.get('device')}"
            )


if __name__ == "__main__":
    main()