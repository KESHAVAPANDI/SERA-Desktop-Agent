import asyncio
from app.tools import create_tool_registry


async def main():
    print("=" * 60)
    print("SERA 1.0 WINDOWS CONTROL SUITE TEST")
    print("=" * 60)

    registry = create_tool_registry()

    # 1. System Info Test
    print("\n[1] Testing get_system_info...")
    res = await registry.execute("get_system_info", {})
    print("Result:", res)

    # 2. Battery Status Test
    print("\n[2] Testing get_battery_status...")
    res = await registry.execute("get_battery_status", {})
    print("Result:", res)

    # 3. Wi-Fi Status Test
    print("\n[3] Testing get_wifi_status...")
    res = await registry.execute("get_wifi_status", {})
    print("Result:", res)

    # 4. Current Time Test
    print("\n[4] Testing get_current_time...")
    res = await registry.execute("get_current_time", {})
    print("Result:", res)

    # 5. List Running Applications Test
    print("\n[5] Testing list_running_applications...")
    res = await registry.execute("list_running_applications", {})
    print(f"Result (Total apps found: {res.get('count', 0)}):")
    for app in res.get("applications", [])[:5]:
        title_str = f" - {app['title']}" if 'title' in app and app['title'] else ""
        print(f"  • {app['name']} (PID {app['pid']}){title_str}")

    # 6. Safety Confirmation Verification
    print("\n[6] Testing Safety Confirmation Flag on Restart / Shutdown...")
    restart_tool = registry.get("restart_computer")
    shutdown_tool = registry.get("shutdown_computer")

    print(f"Restart requires confirmation: {getattr(restart_tool, 'requires_confirmation', False)}")
    print(f"Restart prompt: {getattr(restart_tool, 'confirmation_prompt', '')}")
    print(f"Shutdown requires confirmation: {getattr(shutdown_tool, 'requires_confirmation', False)}")
    print(f"Shutdown prompt: {getattr(shutdown_tool, 'confirmation_prompt', '')}")

    print("\n=" * 60)
    print("WINDOWS CONTROL SUITE TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
