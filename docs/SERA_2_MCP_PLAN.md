# SERA 2.0 — MCP Fabric & Integration Engine Architecture

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Role:** Model Context Protocol (MCP) Client Specification & Tool Registry  
> **Transports Supported:** stdio (Subprocess), SSE (HTTP Server-Sent Events), WebSocket  
> **Security Directives:** Zero Plaintext Secret Leakage, Capability Sandboxing, Live Health Probing

---

## 1. Executive Summary: SERA as an MCP Client

In SERA 2.0, the tool execution subsystem is transformed into an **MCP-Native Client Fabric**. Rather than hardcoding custom tool wrappers for every third-party service, SERA implements the standard JSON-RPC 2.0 Model Context Protocol specification. 

This empowers SERA to instantaneously connect to any external MCP server—local CLI binary or remote cloud service—discover its available tools, schemas, and prompts dynamically, and execute them under strict operator-defined permissions.

---

## 2. MCP Client Hub Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SERA MCP CLIENT HUB                             │
│                      (app/core/mcp_client.py)                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   ┌─────────────────────┐   ┌───────────────────┐   ┌───────────────┐  │
│   │   Server Registry   │   │  Transport Layer  │   │ Security Gate │  │
│   │ - Server Name       │   │ - stdio (Subproc) │   │ - Perm Levels │  │
│   │ - Capabilities      │   │ - SSE (HTTP Stream│   │ - Token Mask  │  │
│   │ - State (Active/Off)│   │ - Streamable WS   │   │ - Audit Logs  │  │
│   └──────────┬──────────┘   └─────────┬─────────┘   └───────┬───────┘  │
│              │                        │                     │          │
│              ▼                        ▼                     ▼          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                     Dynamic Tool Synthesizer                    │  │
│   │  Queries `tools/list` ──▶ Registers tools into SERA Tool Fabric │  │
│   │  Injects schemas into Fast & Reasoning LLM prompt contexts      │  │
│   └───────────────────────────────────┬─────────────────────────────┘  │
└───────────────────────────────────────┼────────────────────────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
    [ Playwright MCP ]         [ Chrome DevTools MCP ]      [ Filesystem MCP ]
    Browser Automation         Active Tab Introspection     Direct OS I/O
```

---

## 3. The Initial Curated MCP Catalog

| MCP Server | Transport | Primary Capabilities | Extension Role in SERA |
| :--- | :--- | :--- | :--- |
| **1. Playwright** | `stdio` (`npx -y @modelcontextprotocol/server-playwright`) | Browser automation, form filling, visual clicking, screenshots | Autonomous web navigation |
| **2. Chrome DevTools**| `stdio` / `SSE` | Inspect active Chrome tabs, read DOM, evaluate JS, network logs | Real-time browser companion |
| **3. Filesystem** | `stdio` (`npx -y @modelcontextprotocol/server-filesystem <dir>`) | Safe local workspace file reading, writing, directory listing | Project code & artifact storage|
| **4. Memory** | `stdio` (`npx -y @modelcontextprotocol/server-memory`) | Entity knowledge graph, semantic relations | Long-term operator memory |
| **5. Fetch** | `stdio` (`npx -y @modelcontextprotocol/server-fetch`) | Fast HTTP GET/POST, clean HTML-to-markdown conversion | High-speed web scraping |
| **6. Git** | `stdio` (`uvx mcp-server-git`) | Status, diffs, commits, branches, log inspection | Version control & coding agent |
| **7. Context7** | `SSE` (`https://mcp.context7.com/sse`) | Real-time developer documentation & library syntax search | Coding & API documentation |
| **8. Tavily / Brave** | `stdio` / `HTTPS` | Deep web search with relevance reranking and AI summaries | Primary Web Research Layer |

---

## 4. "Add Integration" Experience: Environment-Variable Style

The secondary Command Center features an intuitive **Integrations Engine** inspired by clean developer-platform secret vaults:

```
+-----------------------------------------------------------------------------+
|  + Add Integration                                                          |
+-----------------------------------------------------------------------------+
|                                                                             |
|  Select Integration Type:  [ MCP Server (stdio)  ▼ ]                        |
|                                                                             |
|  Name:       [ Playwright Browser Automation                              ] |
|  Command:    [ npx -y @modelcontextprotocol/server-playwright             ] |
|  Arguments:  [ --headless                                                 ] |
|                                                                             |
|  Environment Variables (Key-Value):                                         |
|  ┌────────────────────────┬──────────────────────────────────────────────┐  │
|  │ BRAVE_API_KEY          │ ••••••••••••••••••••••••••••••••   [Show]    │  │
|  ├────────────────────────┼──────────────────────────────────────────────┤  │
|  │ PLAYWRIGHT_TIMEOUT     │ 30000                                        │  │
|  └────────────────────────┴──────────────────────────────────────────────┘  │
|  [ + Add Variable ]                                                         |
|                                                                             |
|  Permissions: (•) Ask Operator Before Use   ( ) Auto-Execute Sandboxed      |
|                                                                             |
|  [ Test & Verify Connection ]                        [ Save Integration ]   |
+-----------------------------------------------------------------------------+
```

### Every Integration Supports:
1. **Connect:** Spawns child process or initiates SSE stream and exchanges `initialize` handshake.
2. **Verify:** Dispatches ping probe and checks `tools/list` returns valid JSON schemas.
3. **Disconnect:** Gracefully terminates child process or closes socket.
4. **Edit:** Modifies environment variables or command arguments.
5. **Disable:** Temporarily toggles tool registration off without losing configuration.
6. **Health:** Tracks latency, consecutive failures, and active tool counts.

---

## 5. Security & Secret Protection Architecture

1. **Zero Secret Leakage:**
   - Secrets are loaded into memory exclusively at process spawn time.
   - All logging streams filter environment values through regex redaction masks before hitting disk or WebSocket.
   - UI displays secrets masked (`••••••••`) by default; unmasking requires explicit operator interaction.
2. **Permission Boundary:**
   - `READ_ONLY`: Tools that read files, fetch URLs, or list processes execute automatically.
   - `DESTRUCTIVE / HIGH_PRIVILEGE`: Tools that modify system files, terminate processes, or send external emails require operator confirmation in Body 1 or Body 2.
