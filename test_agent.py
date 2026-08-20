import asyncio
import os

from dotenv import load_dotenv

from app.core.agent import SERAAgent
from app.core.router import ModelRouter
from app.models.llm import create_provider
from app.tools import create_tool_registry


load_dotenv()


async def main():

    print("=" * 60)
    print("SERA AGENT TEST")
    print("=" * 60)

    # -----------------------------------------
    # Create providers
    # -----------------------------------------

    reasoning = create_provider(
        provider="gemini",
        model="gemini-3-flash-preview",
    )

    router = ModelRouter(
        {
            "reasoning": reasoning,
        }
    )

    # -----------------------------------------
    # Tools
    # -----------------------------------------

    registry = create_tool_registry()

    # -----------------------------------------
    # Agent
    # -----------------------------------------

    agent = SERAAgent(
        router=router,
        tools=registry,
    )

    # -----------------------------------------
    # Test
    # -----------------------------------------

    while True:

        user_input = input("\nYou: ").strip()

        if user_input.lower() in {
            "exit",
            "quit",
        }:
            break

        response = await agent.run(
            user_input
        )

        print(
            f"\nSERA: {response}"
        )

    print("\n" + "=" * 60)
    print("SERA:")
    print(response)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())