import asyncio

from app.tools import create_tool_registry


async def main():

    print("=" * 60)
    print("SERA TOOL SYSTEM TEST")
    print("=" * 60)

    registry = create_tool_registry()

    print("\nRegistered tools:")

    for tool in registry.all():
        print(f"- {tool.name}")

    print("\nTool schemas:")

    for schema in registry.schemas():
        print(schema)

    print("\nExecuting test tool...")

    result = await registry.execute(
        "open_application",
        {
            "application": "notepad"
        },
    )

    print("\nResult:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
