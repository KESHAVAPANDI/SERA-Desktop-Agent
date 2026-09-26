"""
SERA 2.0 — Canonical Context Store.

Central entity authority managing session-scoped search contexts, browser tabs,
application identities, system setting histories, and replayable execution records.
Eliminates loose-string context and guarantees that pronouns/references resolve
strictly to verified entities without guessing or defaulting to result #1.
Conforms strictly to Phase 3A-F Sections 4, 5, 7, 8, 9, 13, 18, 22.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from app.core.context.entities import (
    ApplicationEntity,
    BaseEntity,
    BrowserTabEntity,
    EntityType,
    ReplayableSemanticAction,
    SearchResultEntity,
    SearchResultType,
    SearchSession,
    SystemSettingEntity,
    WindowEntity,
)

logger = logging.getLogger("sera.context.store")


class ContextStore:
    """Thread-safe central context and entity repository for SERA."""

    def __init__(self):
        self._lock = threading.RLock()

        # Entity Registry (entity_id -> BaseEntity)
        self._entities: Dict[str, BaseEntity] = {}

        # Search Sessions (session_id -> SearchSession)
        self._search_sessions: Dict[str, SearchSession] = {}
        self._active_search_session_id: Optional[str] = None

        # Active Entities by Type
        self._active_application_id: Optional[str] = None
        self._active_window_id: Optional[str] = None
        self._active_browser_tab_id: Optional[str] = None
        self._last_resolved_entity_id: Optional[str] = None

        # Browser Tabs Registry (tab_id -> BrowserTabEntity)
        self._browser_tabs: Dict[str, BrowserTabEntity] = {}

        # System Settings History (setting_type -> SystemSettingEntity)
        self._system_settings: Dict[str, SystemSettingEntity] = {
            "brightness": SystemSettingEntity(setting_type="brightness"),
            "volume": SystemSettingEntity(setting_type="volume"),
            "mute": SystemSettingEntity(setting_type="mute", unit="bool"),
        }

        # Replayable Verified Actions History (ordered list)
        self._replayable_actions: List[ReplayableSemanticAction] = []

        # Arbitrary working metadata for legacy compatibility
        self._working_metadata: Dict[str, Any] = {}

    # -------------------------------------------------------------
    # 1. ENTITY REGISTRATION & RETRIEVAL
    # -------------------------------------------------------------
    def register_entity(self, entity: BaseEntity) -> BaseEntity:
        with self._lock:
            self._entities[entity.entity_id] = entity
            return entity

    def get_entity(self, entity_id: str) -> Optional[BaseEntity]:
        with self._lock:
            return self._entities.get(entity_id)

    def get_last_resolved_entity(self) -> Optional[BaseEntity]:
        with self._lock:
            if self._last_resolved_entity_id:
                return self._entities.get(self._last_resolved_entity_id)
            return None

    def set_last_resolved_entity(self, entity_id: str) -> None:
        with self._lock:
            self._last_resolved_entity_id = entity_id

    # -------------------------------------------------------------
    # 2. SEARCH SESSION & NORMALIZED RESULT ENTITIES (Sections 6 & 7)
    # -------------------------------------------------------------
    def create_search_session(self, query: str, source: str = "YouTube") -> SearchSession:
        """Creates a fresh, session-scoped search boundary and marks it active."""
        with self._lock:
            session = SearchSession(
                query=query.strip(),
                source=source,
            )
            self._search_sessions[session.session_id] = session
            self._active_search_session_id = session.session_id
            self.register_entity(session)  # Register session as entity
            logger.info(f"[ContextStore] Created SearchSession id='{session.session_id}' query='{query}' source='{source}'")
            return session

    def get_active_search_session(self) -> Optional[SearchSession]:
        with self._lock:
            if self._active_search_session_id:
                return self._search_sessions.get(self._active_search_session_id)
            return None

    def add_search_results(
        self,
        session_id: str,
        results_data: List[Dict[str, Any]],
    ) -> List[SearchResultEntity]:
        """Normalizes and registers item-level result entities into a specific session."""
        with self._lock:
            session = self._search_sessions.get(session_id)
            if not session:
                logger.warning(f"[ContextStore] Cannot add results: session '{session_id}' not found.")
                return []

            registered_entities: List[SearchResultEntity] = []
            for idx, r in enumerate(results_data):
                raw_type = (r.get("result_type") or r.get("type") or "VIDEO").upper()
                r_type = SearchResultType.VIDEO
                if hasattr(SearchResultType, raw_type):
                    r_type = SearchResultType(raw_type)

                ent = SearchResultEntity(
                    session_id=session_id,
                    ordinal=idx + 1,
                    title=r.get("title", f"Result {idx + 1}").strip(),
                    canonical_url=r.get("url") or r.get("canonical_url", ""),
                    source=r.get("source", session.source),
                    result_type=r_type,
                    description=r.get("description", ""),
                    duration_str=r.get("duration"),
                    channel_name=r.get("channel"),
                )
                self.register_entity(ent)
                registered_entities.append(ent)

            session.results = registered_entities
            logger.info(f"[ContextStore] Added {len(registered_entities)} normalized SearchResultEntities to session '{session_id}'")
            return registered_entities

    def resolve_search_result(
        self,
        ordinal: Optional[int] = None,
        reference_str: Optional[str] = None,
    ) -> Optional[SearchResultEntity]:
        """Resolves reference strictly within active SearchSession.
        NEVER defaults to result 1 if referent is unknown (Section 8).
        """
        with self._lock:
            session = self.get_active_search_session()
            if not session or not session.results:
                logger.info("[ContextStore] resolve_search_result failed: No active search session or results")
                return None

            # Case A: Explicit Ordinal provided (e.g. "open result 2", "second video")
            if ordinal is not None and ordinal > 0:
                result = session.get_result_by_ordinal(ordinal)
                if result:
                    session.active_result_id = result.entity_id
                    session.last_resolved_result_id = result.entity_id
                    self._last_resolved_entity_id = result.entity_id
                    return result
                return None

            # Case B: Contextual Reference ("open that", "open that again", "that one")
            # Step 1: Check active_result_id from current session
            if session.active_result_id:
                res = session.get_result_by_id(session.active_result_id)
                if res:
                    self._last_resolved_entity_id = res.entity_id
                    return res

            # Step 2: Check last_resolved_entity if it belongs to this session
            if self._last_resolved_entity_id:
                res = session.get_result_by_id(self._last_resolved_entity_id)
                if res:
                    session.active_result_id = res.entity_id
                    return res

            # Step 3: Referent is unknown. Return None -> CLARIFY (Never guess result #1!)
            logger.info("[ContextStore] resolve_search_result: Unknown reference with no active referent in session. Requiring clarification.")
            return None

    def record_opened_url(self, url: str) -> Optional[SearchResultEntity]:
        """Matches an opened URL against the active SearchSession results and updates active/last resolved entity."""
        with self._lock:
            session = self.get_active_search_session()
            if session:
                url_clean = url.rstrip("/").lower()
                for r in session.results:
                    if r.canonical_url.rstrip("/").lower() == url_clean:
                        session.active_result_id = r.entity_id
                        session.last_resolved_result_id = r.entity_id
                        self._last_resolved_entity_id = r.entity_id
                        logger.info(f"[ContextStore] Matched opened URL to search result: {r.title} ({r.entity_id})")
                        return r
            return None

    def record_opened_result_by_ordinal(self, ordinal: int) -> Optional[SearchResultEntity]:
        """Updates active/last resolved entity by explicit 1-indexed ordinal."""
        with self._lock:
            session = self.get_active_search_session()
            if session:
                res = session.get_result_by_ordinal(ordinal)
                if res:
                    session.active_result_id = res.entity_id
                    session.last_resolved_result_id = res.entity_id
                    self._last_resolved_entity_id = res.entity_id
                    logger.info(f"[ContextStore] Recorded opened search result by ordinal {ordinal}: {res.title} ({res.entity_id})")
                    return res
            return None

    # -------------------------------------------------------------
    # 3. BROWSER SUBSYSTEM & TAB REGISTRY (Sections 10, 11, 12)
    # -------------------------------------------------------------
    def register_browser_tab(
        self,
        title: Optional[Union[BrowserTabEntity, str]] = None,
        canonical_url: Optional[str] = None,
        browser_name: str = "chrome",
        hwnd: Optional[int] = None,
        is_active: bool = True,
        tab: Optional[BrowserTabEntity] = None,
        **kwargs: Any,
    ) -> BrowserTabEntity:
        """Registers a canonical BrowserTabEntity without duplicate ID generation."""
        with self._lock:
            # Handle tab passed as either 'tab' kwarg or 'title' positional/kwarg
            target_tab = tab if isinstance(tab, BrowserTabEntity) else (title if isinstance(title, BrowserTabEntity) else None)
            if target_tab is not None:
                self._browser_tabs[target_tab.entity_id] = target_tab
                self.register_entity(target_tab)
                if target_tab.is_active:
                    self._active_browser_tab_id = target_tab.entity_id
                logger.info(f"[ContextStore] Registered canonical BrowserTabEntity id='{target_tab.entity_id}' title='{target_tab.title}' url='{target_tab.canonical_url}'")
                return target_tab

            title_str = str(title or kwargs.get("title_str") or "Browser Tab")
            url_str = canonical_url or ""
            # Check if tab with this canonical URL is already registered
            existing = self.find_browser_tab_by_url(url_str)
            if existing:
                existing.title = title_str
                existing.is_active = is_active
                existing.observed_at = time.time()
                if hwnd:
                    existing.hwnd = hwnd
                if is_active:
                    self._active_browser_tab_id = existing.entity_id
                return existing

            new_tab = BrowserTabEntity(
                browser_name=browser_name,
                title=title_str,
                canonical_url=url_str,
                is_active=is_active,
                hwnd=hwnd,
                tab_ordinal=len(self._browser_tabs) + 1,
            )
            self._browser_tabs[new_tab.entity_id] = new_tab
            self.register_entity(new_tab)
            if is_active:
                self._active_browser_tab_id = new_tab.entity_id
            logger.info(f"[ContextStore] Registered BrowserTabEntity id='{new_tab.entity_id}' title='{title_str}' url='{url_str}'")
            return new_tab

    def get_browser_tab(self, tab_id: str) -> Optional[BrowserTabEntity]:
        """Retrieves a registered BrowserTabEntity by its canonical ID."""
        with self._lock:
            return self._browser_tabs.get(tab_id)

    def find_browser_tab_by_url(self, url: str) -> Optional[BrowserTabEntity]:
        with self._lock:
            url_clean = url.rstrip("/").lower()
            for tab in self._browser_tabs.values():
                if tab.canonical_url.rstrip("/").lower() == url_clean:
                    return tab
            return None

    def get_active_browser_tab(self) -> Optional[BrowserTabEntity]:
        with self._lock:
            if self._active_browser_tab_id:
                return self._browser_tabs.get(self._active_browser_tab_id)
            # Fallback to any tab marked active
            for tab in self._browser_tabs.values():
                if tab.is_active:
                    return tab
            return None

    def remove_browser_tab(self, tab_id: str) -> bool:
        """Removes tab from registry and entity store when verified closed (Section 3)."""
        with self._lock:
            removed = False
            if tab_id in self._browser_tabs:
                del self._browser_tabs[tab_id]
                removed = True
            if tab_id in self._entities:
                del self._entities[tab_id]
                removed = True

            if self._active_browser_tab_id == tab_id:
                self._active_browser_tab_id = next(iter(self._browser_tabs.keys())) if self._browser_tabs else None
            if self._last_resolved_entity_id == tab_id:
                self._last_resolved_entity_id = None

            if removed:
                logger.info(f"[ContextStore] Closed and removed BrowserTabEntity id='{tab_id}'")
            return removed

    # -------------------------------------------------------------
    # 4. APPLICATION & WINDOW STATE (Section 5)
    # -------------------------------------------------------------
    def set_active_application(
        self,
        app_name: str,
        executable_path: Optional[str] = None,
        pid: Optional[int] = None,
        hwnd: Optional[int] = None,
    ) -> ApplicationEntity:
        with self._lock:
            canon = app_name.lower().strip()
            # Find existing or create new
            for ent in self._entities.values():
                if isinstance(ent, ApplicationEntity) and ent.canonical_name == canon:
                    ent.is_active = True
                    ent.observed_at = time.time()
                    if executable_path:
                        ent.executable_path = executable_path
                    if pid and pid not in ent.process_ids:
                        ent.process_ids.append(pid)
                    if hwnd and hwnd not in ent.window_handles:
                        ent.window_handles.append(hwnd)
                    self._active_application_id = ent.entity_id
                    self._last_resolved_entity_id = ent.entity_id
                    return ent

            app_ent = ApplicationEntity(
                app_name=app_name,
                canonical_name=canon,
                executable_path=executable_path,
                process_ids=[pid] if pid else [],
                window_handles=[hwnd] if hwnd else [],
                is_active=True,
            )
            self.register_entity(app_ent)
            self._active_application_id = app_ent.entity_id
            self._last_resolved_entity_id = app_ent.entity_id
            return app_ent

    def get_active_application(self) -> Optional[ApplicationEntity]:
        with self._lock:
            if self._active_application_id:
                ent = self._entities.get(self._active_application_id)
                if isinstance(ent, ApplicationEntity):
                    return ent
            return None

    # -------------------------------------------------------------
    # 5. SYSTEM SETTINGS & DETERMINISTIC CONTINUATION (Section 18)
    # -------------------------------------------------------------
    def record_setting_value(self, setting_type: str, value: Any) -> SystemSettingEntity:
        with self._lock:
            setting_type = setting_type.lower().strip()
            if setting_type not in self._system_settings:
                self._system_settings[setting_type] = SystemSettingEntity(setting_type=setting_type)
            ent = self._system_settings[setting_type]
            ent.update_value(value)
            logger.info(f"[ContextStore] Updated setting '{setting_type}' current={value} previous={ent.previous_value}")
            return ent

    record_active_application = set_active_application
    record_setting_change = record_setting_value
    remove_tab = remove_browser_tab

    def get_setting_entity(self, setting_type: str) -> Optional[SystemSettingEntity]:
        with self._lock:
            return self._system_settings.get(setting_type.lower().strip())

    def get_setting(self, setting_type: str) -> Optional[SystemSettingEntity]:
        with self._lock:
            return self._system_settings.get(setting_type.lower().strip())

    def get_previous_setting_value(self, setting_type: str) -> Optional[Any]:
        with self._lock:
            ent = self.get_setting(setting_type)
            if ent and ent.previous_value is not None:
                return ent.previous_value
            return None

    # -------------------------------------------------------------
    # 6. REPLAYABLE ACTIONS & REPETITION (Section 9)
    # -------------------------------------------------------------
    def record_verified_action(self, action: ReplayableSemanticAction) -> None:
        """Stores verified replayable action object."""
        with self._lock:
            self._replayable_actions.append(action)
            if len(self._replayable_actions) > 20:
                self._replayable_actions.pop(0)
            logger.info(f"[ContextStore] Recorded ReplayableSemanticAction intent='{action.semantic_intent}' id='{action.action_id}'")

    def get_last_replayable_action(self) -> Optional[ReplayableSemanticAction]:
        with self._lock:
            if self._replayable_actions:
                return self._replayable_actions[-1]
            return None

    record_action = record_verified_action
    get_replayable_action = get_last_replayable_action

    # -------------------------------------------------------------
    # 7. CONTEXTUAL PRONOUN RESOLUTION (Section 8 & 13)
    # -------------------------------------------------------------
    def resolve_contextual_referent(
        self,
        pronoun: str,
        expected_type: Optional[EntityType] = None,
    ) -> Optional[BaseEntity]:
        """Resolves pronouns ('that', 'it', 'this') to verified entities in order:
        1. Exact active referent (_last_resolved_entity_id)
        2. Active search result if in search session
        3. Active application / window
        Returns None if referent is ambiguous or missing (demands clarification).
        """
        with self._lock:
            # 1. Exact active referent
            last_ent = self.get_last_resolved_entity()
            if last_ent:
                if not expected_type or last_ent.entity_type == expected_type:
                    return last_ent

            # 2. Check active search session
            session = self.get_active_search_session()
            if session and session.active_result_id:
                res = session.get_result_by_id(session.active_result_id)
                if res and (not expected_type or expected_type == EntityType.SEARCH_RESULT):
                    return res

            # 3. Check active application
            active_app = self.get_active_application()
            if active_app and (not expected_type or expected_type == EntityType.APPLICATION):
                return active_app

            # 4. Check active browser tab
            active_tab = self.get_active_browser_tab()
            if active_tab and (not expected_type or expected_type == EntityType.BROWSER_TAB):
                return active_tab

            return None

    # -------------------------------------------------------------
    # 8. LEGACY DICTIONARY COMPATIBILITY LAYER
    # -------------------------------------------------------------
    def to_legacy_dict(self) -> Dict[str, Any]:
        """Projects rich entity store into backward-compatible dictionary for existing nodes."""
        with self._lock:
            active_app = self.get_active_application()
            active_session = self.get_active_search_session()
            active_tab = self.get_active_browser_tab()
            last_act = self.get_last_replayable_action()

            results_list = [r.to_dict() for r in active_session.results] if active_session else []

            bright_ent = self.get_setting("brightness")
            vol_ent = self.get_setting("volume")

            legacy = {
                **self._working_metadata,
                "context_store": self,
                "last_application": active_app.canonical_name if active_app else self._working_metadata.get("last_application"),
                "active_application": active_app.canonical_name if active_app else None,
                "last_search_query": active_session.query if active_session else self._working_metadata.get("last_search_query"),
                "search_results": results_list,
                "search_session_id": active_session.session_id if active_session else None,
                "active_browser_tab": active_tab.title if active_tab else None,
                "current_url": active_tab.canonical_url if active_tab else None,
                "last_intent": last_act.semantic_intent if last_act else self._working_metadata.get("last_intent"),
                "last_verified_action": last_act.semantic_intent if last_act else None,
                "last_brightness": bright_ent.current_value if bright_ent else None,
                "previous_brightness": bright_ent.previous_value if bright_ent else None,
                "last_volume": vol_ent.current_value if vol_ent else None,
                "previous_volume": vol_ent.previous_value if vol_ent else None,
            }
            return legacy

    def update_from_legacy_dict(self, data: Dict[str, Any]) -> None:
        """Ingests updates from legacy dictionary context into entity models."""
        with self._lock:
            self._working_metadata.update(data)
            if "last_application" in data and data["last_application"]:
                self.set_active_application(str(data["last_application"]))
            if "last_brightness" in data and data["last_brightness"] is not None:
                self.record_setting_value("brightness", data["last_brightness"])
            if "last_volume" in data and data["last_volume"] is not None:
                self.record_setting_value("volume", data["last_volume"])
