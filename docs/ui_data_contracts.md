# SERA 1.0 UI Data Contracts & Schemas

## 1. Workflow Graph Contracts

```json
{
  "WorkflowNode": {
    "id": "string",
    "label": "string",
    "role": "reasoning | fast | desktop | vision | ocr | stt | tts | tool | verification",
    "provider": "string | null",
    "model": "string | null",
    "status": "WAITING | ACTIVE | COMPLETED | FAILED | SKIPPED | FALLBACK_TAKEN",
    "latency_ms": "number | null",
    "metadata": {
      "tool_name": "string | null",
      "error_message": "string | null",
      "is_fallback": "boolean"
    }
  },
  "WorkflowEdge": {
    "id": "string",
    "source_id": "string",
    "target_id": "string",
    "type": "PRIMARY | FALLBACK | RETRY | VERIFICATION",
    "status": "INACTIVE | FLOWING | COMPLETED | FAILED"
  }
}
```

---

## 2. Runtime & Agent State Contracts

```json
{
  "RuntimeState": {
    "status": "IDLE | LISTENING | TRANSCRIBING | THINKING | EXECUTING | SPEAKING | CONFIRMING | ERROR",
    "active_turn_id": "string | null",
    "active_task": "string | null",
    "active_role": "string | null",
    "active_provider": "string | null",
    "active_model": "string | null",
    "active_tool": "string | null",
    "gpu_usage_pct": "number | null",
    "system_memory_mb": "number | null",
    "latency_ttft_ms": "number | null",
    "latency_ttfa_ms": "number | null"
  },
  "AgentState": {
    "agent_id": "string",
    "name": "Planner | Researcher | Vision | Desktop | Memory | Verifier | Synthesizer",
    "avatar": "string",
    "role": "string",
    "status": "IDLE | ASSIGNED | WORKING | COMPLETED | FAILED",
    "current_task": "string | null",
    "assigned_model": "string | null",
    "latency_ms": "number | null"
  }
}
```

---

## 3. Providers & Quota Telemetry Contracts

```json
{
  "ProviderCard": {
    "provider_name": "groq | mistral | gemini | openrouter | cerebras | zai | nvidia | fish",
    "display_name": "string",
    "status": "HEALTHY | RATE_LIMITED | UNAVAILABLE | AUTH_ERROR | DEGRADED | DISABLED",
    "models": ["ModelCard"]
  },
  "ModelCard": {
    "model_id": "string",
    "display_name": "string",
    "role": "string",
    "is_primary": "boolean",
    "fallback_rank": "number",
    "health_status": "HEALTHY | RATE_LIMITED | UNAVAILABLE | AUTH_ERROR",
    "cooldown_remaining_s": "number",
    "capabilities": {
      "text": "boolean",
      "vision": "boolean",
      "tool_calling": "boolean",
      "structured_output": "boolean",
      "streaming": "boolean",
      "embeddings": "boolean"
    },
    "quota": {
      "requests_used": "number | null",
      "requests_limit": "number | null",
      "tokens_used": "number | null",
      "tokens_limit": "number | null",
      "reset_time_str": "string | null",
      "is_unknown": "boolean"
    },
    "recent_avg_latency_ms": "number | null",
    "recent_avg_ttft_ms": "number | null"
  }
}
```

---

## 4. History & Memory Contracts

```json
{
  "HistorySession": {
    "session_id": "string",
    "timestamp_str": "string",
    "title": "string",
    "turn_count": "number",
    "total_duration_ms": "number",
    "success": "boolean",
    "turns": ["HistoryTurn"]
  },
  "HistoryTurn": {
    "turn_id": "string",
    "timestamp": "string",
    "user_transcript": "string",
    "assistant_reply": "string",
    "execution_graph": {
      "nodes": ["WorkflowNode"],
      "edges": ["WorkflowEdge"]
    },
    "models_used": ["string"],
    "tools_executed": ["string"],
    "total_latency_ms": "number"
  },
  "MemoryItem": {
    "id": "string",
    "content": "string",
    "category": "PROFILE | PREFERENCE | FACT | PROJECT | TASK | DOCUMENT",
    "source": "CONVERSATION | EXPLICIT | SYSTEM",
    "confidence": "HIGH | MEDIUM | LOW",
    "created_at": "string",
    "usage_count": "number"
  }
}
```
