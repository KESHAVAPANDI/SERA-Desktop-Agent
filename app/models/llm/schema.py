from typing import Any


def to_openai_tools(
    tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:

    result = []
    for tool in tools:
        if "type" in tool and "function" in tool:
            result.append(tool)
        else:
            result.append({
                "type": "function",
                "function": tool,
            })
    return result


def to_gemini_tools(
    tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:

    result = []
    for tool in tools:
        if "type" in tool and "function" in tool:
            fn = tool["function"]
        else:
            fn = tool
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "parameters": fn.get("parameters", {}),
        })
    return result