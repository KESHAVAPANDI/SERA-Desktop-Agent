"""
SERA 2.0 / Phase 4A — Browser Integration Architecture.

Evaluates SERA BrowserSessionManager vs Hermes CDP browser subsystem,
enforcing a single canonical entity model and preventing duplicate truth sources.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.context.entities import BrowserTabEntity
from app.core.context.store import ContextStore
from app.tools.browser.session import BrowserSessionManager

logger = logging.getLogger("sera.hermes.browser")


class BrowserIntegrationMode(str, Enum):
    """Architectural patterns for browser integration."""
    HERMES_DIRECT_CDP = "hermes_direct_cdp"        # Hermes controls browser directly via DevTools Protocol
    SERA_OWNED_SUBSTRATE = "sera_owned_substrate"  # SERA owns BSM; Hermes requests actions through SERA tools
    HYBRID_CONTROLLED = "hybrid_controlled"        # SERA owns entity lifecycle; Hermes receives read-only accessibility tree


class BrowserTabSnapshot(BaseModel):
    """Read-only projection of a canonical SERA browser tab for Hermes."""
    tab_id: str
    title: str
    url: str
    is_active: bool
    browser_type: str = "chrome"


class BrowserHandoffAdapter:
    """Bridges Hermes browser reasoning with SERA's canonical BrowserSessionManager.
    
    Prevents Hermes from inventing disconnected tab IDs by mapping all operations
    strictly to SERA's verified ContextStore and BrowserTabEntity UUIDs.
    """

    def __init__(self, session_manager: Optional[BrowserSessionManager] = None, context_store: Optional[ContextStore] = None):
        self.context_store = context_store or ContextStore()
        self.bsm = session_manager or BrowserSessionManager(context_store=self.context_store)

    def get_canonical_tabs_for_hermes(self) -> List[BrowserTabSnapshot]:
        """Provides Hermes with verified tab snapshots using SERA canonical IDs."""
        tabs: List[BrowserTabSnapshot] = []
        active_tab = self.context_store.get_active_browser_tab()
        active_id = active_tab.entity_id if active_tab else None

        for tid, tab in self.context_store._browser_tabs.items():
            tabs.append(BrowserTabSnapshot(
                tab_id=tid,
                title=tab.title,
                url=tab.canonical_url,
                is_active=(tid == active_id),
                browser_type=getattr(tab, "browser_type", "chrome")
            ))
        return tabs

    async def execute_browser_action(
        self,
        action: str,  # "open_url", "focus_tab", "close_tab"
        target_tab_id: Optional[str] = None,
        url: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a browser action requested by Hermes through SERA's verified manager."""
        if action == "open_url":
            if not url:
                return {"success": False, "error": "URL required for open_url"}
            return await self.bsm.open_url(url=url, title=title or "")

        elif action == "focus_tab":
            if not target_tab_id:
                return {"success": False, "error": "target_tab_id required for focus_tab"}
            # Empirical verification enforced
            return await self.bsm.focus_tab(tab_id=target_tab_id)

        elif action == "close_tab":
            if not target_tab_id:
                return {"success": False, "error": "target_tab_id required for close_tab"}
            return await self.bsm.close_tab(tab_id=target_tab_id)

        return {"success": False, "error": f"Unsupported browser action: {action}"}
