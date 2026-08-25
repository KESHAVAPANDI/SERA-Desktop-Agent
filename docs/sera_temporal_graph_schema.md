# SERA 1.0 — Temporal Workflow Graph Schema

## 1. Schema Overview
The Structured Temporal Graph defines the data contract for SERA's runtime workflow representation and canvas layout.

---

## 2. Graph Definition (`workflow.graph.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SERATemporalWorkflowGraph",
  "type": "object",
  "properties": {
    "version": { "type": "integer", "default": 1 },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "label": { "type": "string" },
          "kind": { 
            "type": "string", 
            "enum": ["entry", "router", "agent", "model", "tool", "service", "store", "external", "verification", "output"] 
          },
          "sub": { "type": "string" },
          "provider": { "type": "string" },
          "model": { "type": "string" },
          "role": { 
            "type": "string",
            "enum": ["stt", "fast", "reasoning", "desktop", "vision", "ocr", "embeddings", "tts"]
          },
          "capabilities": {
            "type": "array",
            "items": { "type": "string" }
          },
          "health": {
            "type": "string",
            "enum": ["HEALTHY", "DEGRADED", "RATE_LIMITED", "UNAVAILABLE", "NOT_CONFIGURED"]
          },
          "status": {
            "type": "string",
            "enum": ["WAITING", "ACTIVE", "COMPLETED", "FAILED", "RATE_LIMITED", "BROKEN", "CANCELLED"]
          },
          "x": { "type": "number" },
          "y": { "type": "number" },
          "width": { "type": "number" },
          "height": { "type": "number" },
          "group": { "type": "string" },
          "active": { "type": "boolean" },
          "detail": { "type": "string" }
        },
        "required": ["id", "label", "kind", "status", "x", "y"]
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "from": { "type": "string" },
          "to": { "type": "string" },
          "kind": { 
            "type": "string", 
            "enum": ["calls", "reads", "writes", "triggers", "fallback"] 
          },
          "label": { "type": "string" },
          "active": { "type": "boolean" },
          "fallback": { "type": "boolean" },
          "status": { 
            "type": "string", 
            "enum": ["WAITING", "ACTIVE", "COMPLETED", "FAILED", "BROKEN"] 
          },
          "progress": { "type": "number" }
        },
        "required": ["id", "from", "to", "kind"]
      }
    },
    "roles": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "mode": { "type": "string", "enum": ["PRIMARY_ONLY", "FALLBACK_ORDER", "CUSTOM"] },
          "candidates": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "provider": { "type": "string" },
                "model": { "type": "string" },
                "priority": { "type": "integer" }
              }
            }
          }
        }
      }
    },
    "layout": {
      "type": "object",
      "properties": {
        "zoom": { "type": "number" },
        "panX": { "type": "number" },
        "panY": { "type": "number" },
        "gridSnap": { "type": "boolean" },
        "gridSize": { "type": "number" }
      }
    }
  },
  "required": ["version", "nodes", "edges", "roles"]
}
```

---

## 3. Spatial Position vs. Semantic Order
- Visual coordinates `(x, y)` represent only the user's canvas organization and are persisted in `config/workflow_layout.json`.
- Candidate execution priority is strictly determined by `roles[role_name].candidates` order and is persisted independently.
