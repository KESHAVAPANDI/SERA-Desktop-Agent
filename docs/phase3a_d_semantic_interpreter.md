# Phase 3A-D: Unified Local Semantic Interpreter Architecture

## 1. Executive Summary & Mission

Prior to Phase 3A-D, SERA's natural-language understanding relied primarily on deterministic regular expressions and handcrafted lexical rules in `CommandParser`. While deterministic extraction provides near-zero latency for strict keywords, natural spoken language contains endless variations:
- Politeness wrappers (*"Hey Sarah, can you please open Chrome for me?"*)
- Semantic repetition (*"Open Chrome again"*, *"Do whatever you just did one more time"*)
- Anaphoric references (*"Open the first result"*, *"Close it"*, *"Take me back to the top result"*)
- Relative state adjustments (*"Put the brightness back where it was"*, *"Set it back to 100%"*)

Fixing each new variation by adding individual regexes is fragile and unmaintainable.

Phase 3A-D introduces a **single, unified local semantic interpretation boundary**:

```
                       USER UTTERANCE
                             +
                 COMPACT VERIFIED CONTEXT
                             +
                 AVAILABLE CAPABILITY SCHEMA
                             ↓
        LOCAL SEMANTIC INTERPRETER (Qwen3.5-4B via Ollama)
                             ↓
                   CANONICAL INTENT JSON
                             ↓
                      CONTEXT RESOLVER
                             ↓
                       GRAPH RUNTIME
                             ↓
                         EXECUTION
                             ↓
                        OBSERVATION
                             ↓
                        VERIFICATION
```

---

## 2. Architectural Boundaries & Division of Responsibilities

| Subsystem | Authoritative Responsibility | What It Must NEVER Do |
| :--- | :--- | :--- |
| **Semantic Interpreter** (`app/core/semantic/`) | Converts natural language + compact context into a typed `CanonicalIntent`. Classifies intents, targets, references, modifiers. | **Never executes actions, never controls Windows, never touches tools, never hallucinates URLs, never declares task completion.** |
| **Context Resolver** (`app/core/context.py`) | Resolves semantic references (e.g. `ordinal=1, type="search_result"`) to concrete runtime entities (e.g. `https://youtube.com/watch?v=...`). | Does not perform general language translation. |
| **Graph Runtime** (`app/core/graph/`) | Authoritative for task lifecycle, plan step construction, node transitions, and dispatch. | Does not re-parse natural language unless explicit fallback is required. |
| **Registered Tools** (`app/tools/`) | Executes real-world OS/desktop side effects via Windows APIs and browser automation. | Does not verify its own success. |
| **Verification Gate** (`app/core/verification.py`) | Authoritative empirical truth via process tables (`psutil`), window handles, and system probes. | Does not interpret user language. |

---

## 3. Local Model Selection: Qwen3.5-4B via Ollama

- **Model**: `qwen3.5:4b` (~3.4 GB weights).
- **Runtime Candidate**: Ollama on `127.0.0.1:11434`.
- **Target Hardware**: NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM, 16GB System RAM).
- **Inference Profile**:
  - `temperature: 0.0` (deterministic classification).
  - `format: "json"` (constrained schema generation).
  - `num_predict: 256` (bounded token generation, zero runaway generation).
  - Sub-5.0s safety timeout with graceful degradation.

---

## 4. Canonical Semantic Contract (`CanonicalIntent`)

All semantic interpretations conform to the strict schema defined in `app/core/semantic/schema.py`:

```json
{
  "semantic_request_id": "sem_a1b2c3d4",
  "intent": "open_application",
  "action_family": "APPLICATION",
  "target": {
    "type": "application",
    "value": "chrome",
    "attributes": {}
  },
  "reference": null,
  "modifiers": {
    "repeat": false,
    "relative": false,
    "direction": null,
    "temporal": null,
    "qualifiers": {}
  },
  "parameters": {},
  "context_resolution": {
    "resolved": false,
    "context_entity_id": null,
    "context_source": null
  },
  "confidence": 0.98,
  "needs_clarification": false,
  "ambiguity_reason": null
}
```

### Contextual Anaphora Example
Utterance: *"Open the first result."*
Context: `last_verified_action="youtube_search"`, 2 search results in context.

```json
{
  "intent": "open_reference",
  "action_family": "BROWSER",
  "target": null,
  "reference": {
    "type": "search_result",
    "scope": "previous_search_results",
    "ordinal": 1
  },
  "confidence": 0.95,
  "needs_clarification": false
}
```

The model does **not** hallucinate a URL; it cleanly outputs `reference.ordinal = 1`. The context resolver then resolves ordinal 1 to the actual URL.

---

## 5. Compact Context Strategy

The semantic interpreter never receives the complete conversation history, system logs, file trees, or the entire `GraphState`. Only language-essential context is supplied:

```json
{
  "utterance": "Open it again.",
  "context": {
    "active_application": "chrome",
    "active_browser": "chrome",
    "active_tab": "Google Search",
    "current_url": "https://www.google.com",
    "last_verified_action": "open_application",
    "relevant_entities": [{"type": "application", "name": "chrome"}],
    "recent_verified_actions": [{"action": "open_application", "target": "chrome"}],
    "available_intents": ["open_application", "close_application", ...]
  }
}
```

This bounded payload ensures ultra-fast prompt evaluation (<15ms prompt processing) on the RTX 4050 GPU.

---

## 6. Four-Stage Rollout Plan

1. **Stage 1 — Standalone Evaluation**:
   - 108 test cases across 9 categories (`tests/semantic_interpreter/benchmark_cases.json`).
   - Benchmark runner measuring cold/warm latency, p50, p95, VRAM, RAM, and semantic accuracy (`tests/semantic_interpreter/benchmark_runner.py`).
   - Zero live SERA execution.
2. **Stage 2 — Shadow Mode Integration**:
   - Legacy `CommandParser` remains 100% authoritative for execution.
   - For every user turn, `SemanticInterpreter` runs concurrently in the background.
   - Logs `SEMANTIC_SHADOW: transcript=..., legacy=..., qwen=..., agreement=...`.
3. **Stage 3 — Selective Primary Routing**:
   - Once categories demonstrate >=95% accuracy in shadow mode, routed through `SemanticInterpreter`.
   - Deterministic parser remains as instant-path (<2ms) and safety fallback.
4. **Stage 4 — Legacy Rule Deprecation**:
   - Handcrafted regexes for language variations safely deprecated.
