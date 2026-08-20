# SERA — Desktop AI Agent

SERA (**S**emantic **E**xecution & **R**untime **A**ssistant) is a next-generation, voice-first Windows desktop AI agent engineered for low-latency voice interaction, multimodal screen perception, bounded multi-step computer automation, and role-based model routing.

---

## 🌟 Key Capabilities

- **Voice Perception & Activation**:
  - Primary **NVIDIA Canary-Qwen 2.5B STT** (~210ms) with local **Faster-Whisper GPU FP16** failover.
  - Fixed 5-second acoustic command capture window.
  - Local **"SERA"** wake word detection + global **`Ctrl+Space`** hotkey.
- **Acoustic Streaming & Interruption**:
  - **Fish Audio S2.1** streaming TTS with instant voice interruption on speech detection.
- **Role-Based Model Architecture & Health-Aware Routing**:
  - **Reasoning**: Groq GPT-OSS 120B ➔ Mistral Large ➔ Mistral Medium 3.5 ➔ OpenRouter.
  - **Fast Text**: Mistral Small ➔ Gemini 3.5 Flash Lite ➔ OpenRouter.
  - **Desktop Tool Calling**: Mistral Codestral ➔ Groq GPT-OSS 120B ➔ OpenRouter.
  - **Vision & Screen Perception**: Groq Qwen 3.6 27B ➔ Gemini 3 Flash Preview ➔ OpenRouter.
  - **OCR & Embeddings**: Mistral OCR & Mistral Embed.
  - **Model-Level Health Isolation**: Rate limits (HTTP 429) on one model isolate only that model's role into cooldown without impacting other models on the same provider.
- **Safe Desktop Automation**:
  - Native Windows UI Automation (`uiautomation` + `pywin32`) with zero hallucinated coordinates.
  - `TargetResolver` with 4-tier confidence matching.
  - Closed-loop **Observe ➔ Act ➔ Verify** cycle.
  - Multi-step bounded agent engine with `SecurityManager`, 5-step limits, and 10s action chain timeouts.
- **Temporal Command Center UI (Phase 5A Foundation)**:
  - Futuristic dark AI OS command center inspired by Temporal Aura.
  - Decoupled asynchronous WebSocket/HTTP gateway server (`http://127.0.0.1:8765`).
  - 7 First-Class View Scaffolds: `WORKFLOW`, `LIVE`, `AGENTS`, `MEMORY`, `PROVIDERS`, `HISTORY`, `DEBUG`.

---

## 🚦 Current Status & Roadmap

| Phase | Milestone | Status |
|:---|:---|:---:|
| **Phase 1** | Core Runtime Architecture, State Machine & EventBus | **COMPLETE** |
| **Phase 2** | Voice Reliability, Real-time Streaming & Audio Interruption | **COMPLETE** |
| **Phase 3** | Multimodal Vision & Native Windows UI Automation | **COMPLETE** |
| **Phase 4** | Multi-Step Bounded Agent, Provider Expansion & Role Routing | **COMPLETE** |
| **Phase 5A** | UI/UX Foundation, Temporal Aura Tokens & Application Shell | **COMPLETE** |
| **Phase 5B** | UI Implementation (Workflow Canvas Editor, Live Orb & RAG) | *NEXT* |

> *Note: Phase 5A establishes the application shell and design architecture. Interactive drag-and-drop workflow editing and complex multi-agent animations will be implemented in subsequent UI phases.*

---

## 🏛️ System Architecture

```
SERA System Architecture
├── Speech & Voice Pipeline
│   ├── Hotkey & Wake Word (Ctrl+Space / "SERA")
│   ├── STT Engine (NVIDIA Canary-Qwen 2.5B ➔ Faster-Whisper Fallback)
│   └── TTS Engine (Fish Audio S2.1 Streaming)
├── Core Engine & Orchestration
│   ├── SERARuntime & State Machine (IDLE, LISTENING, THINKING, EXECUTING, SPEAKING)
│   ├── ModelRouter (Role Chains, Model Health Registry, Quota Cooldowns)
│   └── Agent Engine (Multi-Step Planner, SecurityManager, Verification Loop)
├── Desktop Perception & Tools
│   ├── UI Automation Perception (Native Windows Controls & Properties)
│   ├── Screen Capture & Multimodal Vision (Groq Qwen 3.6 27B / Gemini)
│   └── System Tools (Application Launcher, Volume, Brightness, Navigation)
└── Command Center UI (Decoupled Client Layer)
    ├── Asynchronous WebSocket Gateway (127.0.0.1:8765)
    └── 7-View Temporal Aura SPA
```

---

## 📁 Repository Structure

```
Sera/
├── app/
│   ├── core/           # Runtime, State Machine, EventBus, Planner, Router
│   ├── memory/         # Short-term session context & long-term vector store
│   ├── models/         # Multi-model LLM/Vision/Embedding/STT/TTS Providers & Health
│   ├── speech/         # Voice capture, Canary STT, Whisper, Wake Word, TTS
│   ├── tools/          # Windows UI Automation, System, Screen, Security
│   ├── ui/             # Command Center Server & Temporal Aura SPA Assets
│   └── utils/          # Configuration loader, logging & system telemetry
├── config/             # YAML configuration files
├── docs/               # Architecture, UI Design System, Navigation & Contracts
├── reports/            # Performance benchmarks & validation telemetry
├── tests/              # Full unit & integration regression test suite
├── .env.example        # Environment variables template
├── main.py             # CLI / Voice Agent main entry point
├── requirements.txt    # Python package dependencies
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **OS**: Windows 10 / 11 (64-bit)
- **Python**: Python 3.11+ (Python 3.12 / 3.13 / 3.14 compatible)
- **NVIDIA GPU**: CUDA-capable GPU recommended for local STT fallback

### 2. Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/KESHAVAPANDI/SERA-Desktop-Agent.git
   cd SERA-Desktop-Agent
   ```

2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### 3. Environment Configuration

Copy the template environment file and add your API keys:
```powershell
copy .env.example .env
```

Edit `.env` with your preferred provider keys:
```ini
NVIDIA_API_KEY=your_nvidia_build_key
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
FISH_API_KEY=your_fish_audio_key
MISTRAL_API_KEY=your_mistral_api_key
OPENROUTER_API_KEY=your_openrouter_key
```

> ⚠️ **SECURITY WARNING**: Never commit your `.env` file or expose private API keys. Ensure `.env` remains in `.gitignore` at all times.

---

## 💻 Running SERA

### Headless Voice Agent (CLI Mode)
```powershell
python main.py
```
- Press **`Ctrl+Space`** or say **"SERA"** to activate voice capture.
- Speak commands such as *"Set brightness to 50%"*, *"Open Chrome and search RTX 5090"*, or ask questions.

### Running Automated Unit Tests
```powershell
python -m unittest discover tests
```
*Current test suite: 89/89 tests passing (100% OK).*

---

## 🔒 Security & Safety

SERA enforces strict safety boundaries:
- **No Unrestricted Computer Control**: Raw cursor movement and unconstrained key injection are strictly isolated.
- **Observe ➔ Act ➔ Verify**: Every interaction checks state before and after execution.
- **Budget Limits**: Max 5 steps per task execution and 10-second action chain timeouts.
