import asyncio
import os

from dotenv import load_dotenv

from app.models.llm import create_provider


load_dotenv()


async def main():

    print("=" * 60)
    print("SERA MODEL PROVIDER TEST")
    print("=" * 60)

    provider = create_provider(
        provider="gemini",
        model="gemini-3-flash-preview",
    )

    print("\nProvider:")
    print("Gemini")

    print("\nCapabilities:")

    for name, supported in (
        provider.capabilities().items()
    ):
        print(
            f"  {name}: {supported}"
        )

    print("\nSending message...")

    response = await provider.generate(
        messages=[
            {
                "role": "user",
                "content": (
                    "You are SERA. "
                    "Reply with a short greeting."
                ),
            }
        ]
    )

    print("\nSERA:")
    print(response.text)

    print("\nProvider:")
    print(response.provider)

    print("Model:")
    print(response.model)


if __name__ == "__main__":
    asyncio.run(main())