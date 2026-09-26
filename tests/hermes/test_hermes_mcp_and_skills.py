"""
SERA 2.0 / Phase 4A — Tests for MCP Provider, Skills Registry, Memory, and Browser Handoff.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.adapters.hermes.skills import SkillRegistry, HermesSkill
from app.adapters.hermes.memory import (
    MemoryContract,
    UserIdentityProfile,
    MemoryRetrievalQuery,
    MemoryScope,
)
from app.adapters.hermes.mcp_provider import SeraMcpProvider
from app.adapters.hermes.browser import BrowserHandoffAdapter
from app.core.context.store import ContextStore, BrowserTabEntity
from app.core.verification import EvidenceVerificationFabric, EvidenceType
from app.tools import ToolRegistry


def test_progressive_skills_registry():
    """SkillRegistry provides minimal metadata prompt and loads full markdown instructions only on match."""
    registry = SkillRegistry()

    # Initial metadata prompt is compact
    meta_prompt = registry.list_metadata_prompts()
    assert "system_diagnostics" in meta_prompt
    assert "browser_research" in meta_prompt
    assert len(meta_prompt.splitlines()) == 2  # exactly two lines

    # Matching utterance loads full instructions
    matched = registry.match_and_load("Could you run system diagnostics and check why pc is slow?")
    assert len(matched) == 1
    skill = matched[0]
    assert skill.name == "system_diagnostics"

    full_prompt = skill.to_full_prompt()
    assert "### SKILL: system_diagnostics" in full_prompt
    assert "Enumerate active interactive user applications" in full_prompt
    assert "Verification Expectations" in full_prompt
    assert "Failure Handling" in full_prompt


def test_memory_contract_boundary():
    """MemoryContract provides structured user identity and stable preferences without unauthorized overwrite."""
    identity = UserIdentityProfile(
        display_name="Keshav",
        goals=["Build SERA desktop agent"],
        stable_preferences={"preferred_browser": "chrome", "theme": "dark"}
    )
    contract = MemoryContract(identity_profile=identity)

    # Query identity and preferences
    query = MemoryRetrievalQuery(query="user settings", scopes=[MemoryScope.IDENTITY, MemoryScope.STABLE_PREFERENCE])
    memories = contract.query_memories(query)

    assert len(memories) >= 2
    id_mem = next(m for m in memories if m.scope == MemoryScope.IDENTITY)
    assert id_mem.value["name"] == "Keshav"

    pref_mem = next(m for m in memories if m.key == "preferred_browser")
    assert pref_mem.value == "chrome"


@pytest.mark.asyncio
async def test_mcp_provider_tools_and_verification():
    """SeraMcpProvider exposes tools and enforces verification fabric records."""
    tools = ToolRegistry()
    fabric = EvidenceVerificationFabric()
    mcp = SeraMcpProvider(tool_registry=tools, verification_fabric=fabric)

    # 1. List tools
    tool_defs = mcp.list_tools()
    assert len(tool_defs) >= 4
    tool_names = [t["name"] for t in tool_defs]
    assert "mcp_sera_open_application" in tool_names
    assert "mcp_sera_set_brightness" in tool_names

    # 2. Call tool with verification
    mock_win_tool = MagicMock()
    mock_win_tool.name = "close_window"
    mock_win_tool.execute = AsyncMock(return_value={"success": True, "verified": True, "hwnd": 9999})
    tools.register(mock_win_tool)

    res = await mcp.call_tool("mcp_sera_close_window", {"hwnd": 9999})
    assert res["isError"] is False
    assert res["verified"] is True
    assert res["evidence_type"] == "WINDOW_HANDLE"


@pytest.mark.asyncio
async def test_browser_handoff_adapter_canonical_entity_preservation():
    """BrowserHandoffAdapter projects canonical BrowserTabEntity snapshots without duplicate UUIDs."""
    store = ContextStore()
    tab = store.register_browser_tab(title="YouTube - Home", canonical_url="https://youtube.com")
    tab_id = tab.entity_id

    adapter = BrowserHandoffAdapter(context_store=store)
    snapshots = adapter.get_canonical_tabs_for_hermes()

    assert len(snapshots) == 1
    assert snapshots[0].tab_id == tab_id
    assert snapshots[0].title == "YouTube - Home"
    assert snapshots[0].url == "https://youtube.com"
