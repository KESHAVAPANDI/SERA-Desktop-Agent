import asyncio

from dotenv import load_dotenv

from app.models.llm import create_provider


load_dotenv()


async def main():

    print("=" * 60)
    print("SERA GROQ TEST")
    print("=" * 60)

    provider = create_provider(
        provider="groq",
        model="openai/gpt-oss-120b",
    )

    print("\nProvider: Groq")
    print("Model: openai/gpt-oss-120b")

    print("\nCapabilities:")

    for name, value in (
        provider.capabilities().items()
    ):
        print(
            f"  {name}: {value}"
        )

    print("\nSending request...")

    response = await provider.generate(
        messages=[
            {
                "role": "user",
                "content": (
                    "You are SERA, a desktop "
                    "AI assistant. "
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