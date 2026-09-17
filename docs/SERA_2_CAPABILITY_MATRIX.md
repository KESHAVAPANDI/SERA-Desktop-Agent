# SERA 2.0 — System Capability Matrix & Extension Architecture

> **Purpose:** Exhaustive capability mapping across all operational dimensions of SERA 2.0.  
> **Philosophy:** Clean extension points, strict verification gates, zero fabricated capabilities.

---

## 1. Comprehensive Capability Breakdown

```
┌─────────────────────────┬──────────────┬──────────────────────────────────┬─────────────────────────────┐
│ Capability Dimension    │ Status       │ Existing File / Subsystem        │ SERA 2.0 Implementation Spec│
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 1. Desktop Automation   │ OPERATIONAL  │ app/tools/windows/application.py │ Process verification & win- │
│                         │ (Verified)   │ app/tools/desktop/               │ dow title verification gate │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 2. Browser Automation   │ EXTENSION PT │ tests/e2e/                       │ Playwright MCP client +     │
│                         │ (Ready)      │                                  │ Chrome DevTools MCP client  │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 3. Web Research         │ OPERATIONAL  │ app/tools/browser/web_search.py  │ DuckDuckGo ad-filtered      │
│                         │ (Verified)   │                                  │ parser with real live cards │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 4. Vision & Perception  │ PARTIAL      │ app/vision/analyzer.py           │ Dual-mode: Full perception  │
│                         │ (Operational)│ app/tools/screen/capture.py      │ + bounding box crop OCR     │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 5. Filesystem           │ OPERATIONAL  │ app/tools/filesystem/            │ Sandboxed workspace read/   │
│                         │              │                                  │ write/list with diff logs   │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 6. Clipboard            │ EXTENSION PT │ app/tools/desktop/clipboard.py   │ Win32 clipboard monitor &   │
│                         │              │                                  │ sanitized paste injection   │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 7. Notifications        │ OPERATIONAL  │ app/speech/audio_cues.py         │ Spatial audio chimes +      │
│                         │              │                                  │ kinetic morphing HUD text   │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 8. System Controls      │ EXTENSION PT │ app/tools/windows/               │ Audio volume, power state,  │
│                         │              │                                  │ process tree kill via Win32 │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 9. Memory Subsystem     │ EXTENSION PT │ app/memory/long_term.py          │ 6-tier partitioned memory   │
│                         │ (Needs Rework│ app/memory/short_term.py         │ with SQLite/vector backend  │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 10. Local RAG Engine    │ EXTENSION PT │ app/models/llm/embeddings.py     │ Embedded LanceDB + chunker  │
│                         │              │                                  │ with source citation checks │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 11. Multi-Agent Fabric  │ EXTENSION PT │ app/core/agent.py                │ BaseAgent interface for     │
│                         │              │                                  │ 8 specialized sub-agents    │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 12. MCP Client Hub      │ EXTENSION PT │ docs/SERA_2_MCP_PLAN.md          │ Native JSON-RPC stdio/SSE   │
│                         │              │                                  │ client with secret masking  │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 13. Deep Research       │ EXTENSION PT │ app/tools/browser/web_search.py  │ Recursive multi-site fetch  │
│                         │              │                                  │ & cross-reference synthesis │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 14. Code Execution      │ OPERATIONAL  │ app/tools/filesystem/            │ Terminal sandbox with       │
│                         │              │ tests/                           │ verified subprocess outputs │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 15. Integrations Engine │ EXTENSION PT │ app/ui/static/js/views/          │ Env-var credential vault &  │
│                         │              │ providers.js (Reworking)         │ live verification probes    │
├─────────────────────────┼──────────────┼──────────────────────────────────┼─────────────────────────────┤
│ 16. Schedules & Cron    │ EXTENSION PT │ app/core/runtime.py              │ Recurring cron tasks &      │
│                         │              │                                  │ one-shot reminders engine   │
└─────────────────────────┴──────────────┴──────────────────────────────────┴─────────────────────────────┘
```

---

## 2. Core Extension Points & Interface Specifications

### 2.1 Tool Execution Extension Point
Every tool in SERA 2.0 must inherit from `BaseTool` and guarantee real-world verification:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel

class ToolResult(BaseModel):
    success: bool
    verified: bool            # True ONLY if real external side-effect confirmed
    output: Any               # Human/Model consumable payload
    artifacts: list[str] = [] # Paths to screenshots, logs, or saved files
    error: str | None = None

class BaseTool(ABC):
    name: str
    description: str
    parameters_schema: dict

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Executes tool and performs real-world side effect verification."""
        pass
```

### 2.2 Memory Partitioning Architecture
The 6 discrete memory tiers ensure contextual clarity without token bloat:

1. **Conversation Memory (`app/memory/conversation.py`):**
   - Active turn-by-turn rolling context with dynamic summarization.
   - Clears gracefully on session reset; persists to `scratch/session_transcript.jsonl`.
2. **Preference Memory (`app/memory/preferences.py`):**
   - User traits, preferred IDEs, speech rate, theme, default browser.
   - Stored in persistent `config/preferences.json`.
3. **Task History (`app/memory/task_history.py`):**
   - Chronological ledger of all objectives executed, step results, and artifacts.
   - Accessible via the `TASKS` tab in the Command Center.
4. **Project Memory (`app/memory/project.py`):**
   - Workspace-specific knowledge: file maps, test commands, conventions.
   - Scoped to the active project root directory.
5. **Document Knowledge (`app/memory/knowledge.py`):**
   - Embedded vectors for user-provided manuals, documentation, and reference files.
6. **Web Research Cache (`app/memory/web_cache.py`):**
   - TTL-governed key-value cache of parsed search results to eliminate redundant web queries.

### 2.3 Verification & Safety Gates
- **Process Verification Gate:** No application launch task reports `COMPLETED` unless the OS process ID exists and the window handle is confirmed.
- **Web Result Gate:** No search task completes on zero results. If zero results return, the state transitions to `BROKEN` with actionable diagnostics.
- **Credential Protection Gate:** All API keys and environment variables in the Integrations view are masked (`••••••••`), never echoed in logs, and stored in secure local `.env`.
