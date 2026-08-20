import asyncio

from app.tools import create_tool_registry


async def main():

    registry = create_tool_registry()

    print("=" * 60)
    print("SERA WINDOWS TOOL TEST")
    print("=" * 60)

    print("\nRegistered tools:")

    for tool in registry.all():

        print(
            f"  [+] {tool.name}"
        )

    print("\nSystem information:")

    result = await registry.execute(
        "get_system_info",
        {},
    )

    print(result)

    print("\nBattery:")

    result = await registry.execute(
        "get_battery_status",
        {},
    )

    print(result)

    print("\nVolume:")

    result = await registry.execute(
        "get_volume",
        {},
    )

    print(result)

    print("\nBrightness:")

    result = await registry.execute(
        "get_brightness",
        {},
    )

    print(result)


if __name__ == "__main__":

    asyncio.run(main())