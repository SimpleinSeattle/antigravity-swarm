# Antigravity Swarm — Release Notes

## v1.1.0 — 2026-02-21

### Summary
This release formalizes the Antigravity Swarm as a production-quality multi-agent development framework with explicit role-based concurrency, loop safety, and hybrid local/cloud routing.

---

### New Features

#### 🆕 Telemetry Agent
A new `Telemetry_Agent` has been added to the Agent Pool. It operates as a **Parallel Reviewer** and is responsible for ensuring structured logging, metrics, and error observability are baked into every project.

#### 🆕 QA Engineer Agent
A new `QA_Engineer` has been added as a **Serial Implementer**. It writes automated tests (unit, integration, end-to-end) for the application being built.

#### 🆕 Ops Agent
A new `Ops_Agent` has been added as a **Serial Implementer**. It handles all infrastructure-as-code, including Dockerfiles, CI/CD pipelines, and deployment scripts.

#### 🔒 Loop Safety & Human Intervention
The `orchestrator.py` now includes a full loop-break and human-intervention system:
- **Automatic Retry:** Failed agents are retried up to `MAX_RETRIES` (default: 2) times automatically.
- **Human Intervention Prompt:** After retries are exhausted, the TUI pauses and prompts the user to **[r]etry**, **[s]kip**, or **[a]bort**.
- **Sentinel File Break:** Create a `HUMAN_BREAK` file in the working directory at any time to trigger an immediate human checkpoint without waiting for a failure.

#### 🖥️ Model Column in TUI
The Orchestrator TUI now displays the active **model** for each agent alongside its role and status, making it easy to see which agents are running locally vs. in the cloud.

---

### Improvements

#### ✅ Concurrency Model Enforcement
The `planner.py` prompt now contains explicit **[CRITICAL - CONCURRENCY RULES]** instructions to the Orchestrator LLM:
- **Reviewer Agents → `mode: parallel`**
- **Implementer Agents → `mode: serial`**

This ensures that generated `subagents.yaml` rosters are always safe and do not trigger file-write conflicts.

#### ☁️ Hybrid Local/Cloud Architecture
`dispatch_agent.py` and `planner.py` both now read `swarm_config.json` to dynamically route each agent to either the local Ollama instance or the cloud-based Gemini endpoint based on the active mode toggle.

#### 📄 Framework Documentation
A comprehensive [`FRAMEWORK_GUIDE.md`](file:///C:/Users/sean/.gemini/skills/antigravity-swarm/FRAMEWORK_GUIDE.md) has been created covering:
- Agent Roster and Concurrency Model
- Hybrid Local/Cloud Deployment scenarios
- Orchestration Workflow for new projects

---

### Configuration

| Setting | File | Default |
|---|---|---|
| `MAX_RETRIES` | `orchestrator.py` | 2 |
| `mode` | `swarm_config.json` | `"local"` |
| `ollama_model` | `swarm_config.json` | `"gemma2:27b"` |
| `ollama_url` | `swarm_config.json` | `"http://localhost:11434"` |

---

### Files Modified

| File | Change |
|---|---|
| `scripts/planner.py` | Added Telemetry, QA, Ops agents; updated concurrency rules |
| `scripts/orchestrator.py` | Added loop safety, retry gate, human intervention, model TUI column |
| `FRAMEWORK_GUIDE.md` | New file — complete framework usage guide |

---

## v1.0.0 — 2026-01-28 (Baseline)

Initial Antigravity Swarm framework. Includes Orchestrator, Librarian, Explore, Frontend, Doc_Writer, Prometheus, Momus, Sisyphus, Junior, Quality_Validator, Security_Agent, Best_Practices_Agent, and Aesthetics_Agent roles.
