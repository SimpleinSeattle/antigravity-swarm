# Antigravity Swarm: Multi-Agent Framework Guide

This guide details how to leverage the Antigravity Swarm for complex project development using defined agent roles, engineered shared memory, and scalable hybrid orchestration.

## The Core Concept
When you are building a new feature or application within the Antigravity IDE, you shouldn't just ask one LLM to "do it all." Instead, dispatch a *squad* of specialized sub-agents.

By adhering to the **Manus Protocol**, agents communicate with each other asynchronously by reading and writing to three core files in your project root:
1. `task_plan.md`: The single source of truth for the mission goals.
2. `findings.md`: The shared scratchpad where agents leave notes and research for each other.
3. `progress.md`: The unified log of completed steps.

## The Roster & Concurrency Model

Agents are strictly divided into two types of execution: **Serial Implementers** and **Parallel Reviewers**.

### 1. Serial Implementers
These agents write or modify actual project code. To prevent Git conflicts or file-write collisions, they **MUST run sequentially (`mode: serial`)**.

*   **Oracle:** Complex debugging, architecture, root cause analysis.
*   **Junior:** Concrete implementation, direct execution of the heavy lifting.
*   **Frontend:** UI components, styling, accessibility, frontend logic.
*   **Prometheus:** Strategic planning, requirements gathering.
*   **QA_Engineer:** Automated testing development (unit, integration, e2e).
*   **Ops_Agent:** Deployment configurations, CI/CD pipelines, Dockerfiles, Infrastructure-as-Code.

### 2. Parallel Reviewers
These agents read existing code and provide analysis, updates to shared memory, or non-conflicting documentation. Because they don't modify the core logic files, they **MUST run concurrently (`mode: parallel`)** to save time.

*   **Security_Agent:** Security auditing, vulnerability assessment, devil's advocate.
*   **Aesthetics_Agent:** UI/UX design review, usability heuristics.
*   **Best_Practices_Agent:** Code quality, standards enforcement, SOLID principles check.
*   **Telemetry_Agent:** Observability, ensuring structured logging and metrics are present.
*   **Doc_Writer:** Internal documentation, inline comments.
*   **Librarian:** External research, code structure analysis.

### 3. The Gatekeeper
*   **Quality_Validator (`mode: validator`):** The final agent that runs only after all others finish. It verifies the mission is complete and the code is unbroken.

---

## Strategic Hybrid Deployments (Cost Optimization)

When your mission is massive, dispatching 5 cloud-based agents can burn through API tokens quickly. You can optimize this by mixing Cloud (Gemini) and Local (Ollama) execution using your AI Control Panel!

### Scenario 1: The Heavy Architectural Lift (Cloud Mode)
When starting a brand new, complex feature from scratch.
1. Set the AI Control Panel to **Cloud**.
2. Run the mission: `run_mission "Architect the backend for a real-time chat application."`
3. The system will hire `Prometheus`, `Oracle`, and `Quality_Validator`—all running on **Gemini 3.1 Pro** to handle the heavy reasoning phase.

### Scenario 2: The Grinding Implementation Phase (Local Mode)
Once the architecture is decided and `findings.md` is populated, you need to grind out the actual files.
1. Set the AI Control Panel to **Local**.
2. Run the mission: `run_mission "Implement the chat backend following the architecture in findings.md. Add telemetry and security reviews."`
3. The system will hire `Junior`, `Telemetry_Agent`, and `Security_Agent`. These will spin up entirely on your local **gemma2:27b**, utilizing your RTX 3090. The Junior will write the code (serial), while the Reviewers analyze it (parallel)—all at ZERO token cost.

## Orchestration Workflow

Whenever you start a new complex requirement, follow these steps with me (Antigravity):

1. **Ask for a Plan:** "Let's use the Swarm to build X."
2. **Review the Team:** The Planner (`scripts/planner.py`) will automatically select the perfect roster from the Agent Pool and define their serial/parallel modes in `subagents.yaml`.
3. **Execute:** The Orchestrator will spin up the TUI in your terminal and you can watch your agents build the project!

---

## Loop Safety & Human Intervention

Agent failures in a chain can cause unproductive retry loops. The Orchestrator includes three layers of protection:

### Layer 1: Automatic Retry (Transparent)
Any agent that fails will auto-retry up to **2 times** (configurable via `MAX_RETRIES` in `orchestrator.py`) before escalating.

### Layer 2: Human Intervention Prompt (On Exhaustion)
After all auto-retries fail, the TUI **pauses** and asks you:
```
⚠ HUMAN INTERVENTION REQUIRED
Agent [Junior] failed after 2 retries.
Last log: Error: syntax error in output file.

  [r] Retry once more
  [s] Skip this agent and continue
  [a] Abort the entire mission
```

### Layer 3: Sentinel File Break (Emergency Stop)
You can trigger a human checkpoint **at ANY time** — even mid-execution — by creating a file called `HUMAN_BREAK` in the directory where you ran the Orchestrator:
```powershell
New-Item -Path ".\HUMAN_BREAK" -ItemType File
```
Within 100ms, the TUI will pause and present a **Resume / Abort** choice, giving you full control without needing to kill the process.

---

## Reference Documentation

| Document | Description |
|---|---|
| [FRAMEWORK_GUIDE.md](./FRAMEWORK_GUIDE.md) | This document |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, component map, data flow |
| [RELEASE_NOTES.md](./RELEASE_NOTES.md) | Changelog and version history |

