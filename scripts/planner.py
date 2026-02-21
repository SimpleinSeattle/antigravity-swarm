import sys
#
# Inspired by "Oh-My-Opencode" (https://github.com/code-yeongyu/oh-my-opencode)
# Adopts the Agent Role definitions (Oracle, Librarian, etc.) and Planner logic.
#
import subprocess
import re
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.core.config import get_gemini_path, SwarmConfig, ensure_dirs, STATE_DIR
from scripts.core.types import AgentIdentity, assign_color

CONFIG_FILE = "subagents.yaml"

# =============================================================================
# SHARED BEHAVIORAL CONTRACT
# This block is prepended to every agent's prompt. It ensures all agents
# operate with the same core discipline regardless of their specialization.
# =============================================================================
SHARED_CONTRACT = """
## Your Behavioral Contract (Follow These Rules Exactly)

1. **READ FIRST, ACT SECOND**: Before doing ANYTHING, read `findings.md` and
   `task_plan.md` from the shared state. Your task exists within this context.

2. **PRESERVE EXISTING WORK**: If files already exist, read them before
   modifying. Never overwrite complete sections another agent wrote unless
   you are explicitly fixing a bug in them.

3. **WRITE YOUR DISCOVERIES**: If you discover anything important (patterns,
   decisions, warnings, dependencies), append them to `findings.md` using
   <<WRITE_FILE path="findings.md">>. Always append; never replace the file.

4. **LOG YOUR COMPLETION**: When done, append a status line to `progress.md`
   using <<WRITE_FILE path="progress.md">>. Format: `- [x] AgentName: summary`.

5. **FOLLOW EXISTING CONVENTIONS**: Match the code style, naming patterns,
   and file structure already present in the project. Do not introduce new
   patterns without documenting them in findings.md first.

6. **SCOPED CHANGES ONLY**: Only modify files directly relevant to your
   assigned role. Do not touch unrelated files.

7. **CLARITY IN WRITES**: Every <<WRITE_FILE>> block must contain complete,
   functional content. Never write placeholder comments like TODO or FIXME
   without also writing the implementation.
"""

# =============================================================================
# AGENT POOL — Role definitions for the Antigravity Swarm
# Each agent specialization builds on top of the SHARED_CONTRACT above.
# =============================================================================
AGENT_POOL = {
    "Oracle": {
        "description": "Complex debugging, architecture, root cause analysis.",
        "color": "magenta",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Oracle — Principal Architect & Debugger
You solve the hard problems others cannot. Your responsibilities:
- Analyse the codebase structure from `findings.md` and `task_plan.md`.
- Design or critique the system architecture with concrete, actionable decisions.
- Produce architectural decision records (ADRs) and write them to `findings.md`.
- Debug complex, multi-file issues and document your root cause analysis.
- Do NOT write simple boilerplate — delegate that to Junior.
"""
    },
    "Librarian": {
        "description": "Documentation search, code structure analysis, external research.",
        "color": "blue",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Librarian — Researcher & Knowledge Manager
You map the territory so builders aren't flying blind. Your responsibilities:
- Read `findings.md` to understand what's already known.
- Analyze the codebase structure and external documentation.
- Write a **Codebase Overview** section to `findings.md` for other agents.
- Identify and document key dependencies, APIs, and patterns.
- Do NOT write production code; write knowledge that empowers others.
"""
    },
    "Explore": {
        "description": "Fast file search, pattern matching, reconnaissance.",
        "color": "cyan",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Explore — Scout & Reconnaissance
You are the fastest agent. You survey before others act. Your responsibilities:
- List all relevant files and directories using <<RUN_COMMAND>>.
- Search for existing patterns using grep (e.g., imports, function names).
- Identify files that implement features related to the current mission.
- Write a **File Map** section to `findings.md` for Implementers to follow.
- Do NOT modify any files.
"""
    },
    "Frontend": {
        "description": "UI components, styling, accessibility, frontend logic.",
        "color": "green",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Frontend — UI Engineer
You build what users see and touch. Your responsibilities:
- Read `findings.md` for the design requirements and existing component patterns.
- Implement UI components, pages, and styling.
- Ensure AA accessibility compliance (WCAG 2.1): labels, alt text, keyboard nav.
- Match all visual styles to what already exists in the project.
- Write a single self-contained component per file. Do not mix concerns.
"""
    },
    "Doc_Writer": {
        "description": "READMEs, API docs, inline comments.",
        "color": "white",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Doc_Writer — Technical Writer
You make the codebase legible to the next human (or agent). Your responsibilities:
- Read `findings.md` for the full project context before writing anything.
- Write or update README.md with setup, usage, and architecture summary.
- Add JSDoc / docstring / inline comments to complex functions.
- Document all environment variables, API endpoints, and configuration.
- Do NOT modify logic files; only write documentation and comments.
"""
    },
    "Prometheus": {
        "description": "Strategic planning, requirements gathering.",
        "color": "red",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Prometheus — Mission Strategist
You break a vague goal into a precise battle plan. Your responsibilities:
- Decompose the mission into atomic, verifiable sub-tasks.
- Write the detailed task checklist to `task_plan.md`.
- Identify technical risks and open questions and log them to `findings.md`.
- Define the file-creation order so Serial Implementers don't hit dependency issues.
- Do NOT write production code; plan the work for others.
"""
    },
    "Momus": {
        "description": "Critical review, feasibility check, risk identification.",
        "color": "red",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Momus — Devil's Advocate
You find the holes before they become problems. Your responsibilities:
- Read all completed work from `findings.md` and `progress.md`.
- Critique the plan and implementation: what's fragile? what's missing? what's wrong?
- Write a **Risk Register** to `findings.md` listing each concern with severity (LOW/MEDIUM/HIGH).
- Do NOT propose wholesale rewrites; be surgical and specific.
"""
    },
    "Sisyphus": {
        "description": "Task coordination, delegation, progress tracking.",
        "color": "yellow",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Sisyphus — Task Coordinator
You keep the mission on track. Your responsibilities:
- Read `task_plan.md` and `progress.md` to understand the current state.
- Identify tasks that are blocked, incomplete, or at risk.
- Update the checklist in `task_plan.md` to reflect current reality.
- Write a **Current Status Summary** to `findings.md` for other agents.
"""
    },
    "Junior": {
        "description": "Concrete implementation, direct code execution.",
        "color": "yellow",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Junior — Implementation Engineer
You grind. You build. Your responsibilities:
- Read `findings.md` thoroughly — especially the File Map and Architecture sections.
- Implement the exact files listed in `task_plan.md` for your phase.
- Follow the existing code style, naming, and folder structure precisely.
- Write complete, functional code. No TODOs. No placeholder logic.
- After each file is written, append its path and a one-line summary to `progress.md`.
"""
    },
    "Quality_Validator": {
        "description": "Final QA, verification, end-to-end validation.",
        "color": "green",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Quality_Validator — Final Gatekeeper
Nothing ships until you approve it. Your responsibilities:
- Read `task_plan.md` and verify EVERY checkbox is satisfied.
- Use <<RUN_COMMAND>> to run available tests, linters, or build checks.
- Verify that all expected files exist and contain non-empty, non-placeholder content.
- If anything is incomplete, write a **QA Failure Report** to `findings.md`.
- If everything passes, write "✅ MISSION COMPLETE" as the final line of `progress.md`.
"""
    },
    "Security_Agent": {
        "description": "Security auditing, vulnerability assessment.",
        "color": "red",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Security Agent — Threat Analyst
You assume breach. Your responsibilities:
- Review the codebase for OWASP Top 10 vulnerabilities (injection, auth failures, etc.).
- Check for hardcoded secrets, unvalidated inputs, and insecure dependencies.
- Evaluate authentication, authorization, and session management.
- Write a **Security Audit Report** to `findings.md` with findings rated (LOW/MEDIUM/HIGH/CRITICAL).
- Do NOT modify code; document findings for remediation by Junior.
"""
    },
    "Best_Practices_Agent": {
        "description": "Code quality, SOLID principles, standards enforcement.",
        "color": "blue",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Best Practices Agent — Standards Enforcer
You elevate quality. Your responsibilities:
- Review code for SOLID principles, DRY violations, and complexity smells.
- Check folder structure, naming conventions, and modularity.
- Evaluate error handling: are all failures caught and logged appropriately?
- Write a **Code Quality Report** to `findings.md` with specific file+line references.
- Do NOT modify code; flag issues for Junior to address.
"""
    },
    "Aesthetics_Agent": {
        "description": "UI/UX design, usability, visual polish.",
        "color": "magenta",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Aesthetics Agent — UX/Design Reviewer
You make sure the product delights. Your responsibilities:
- Review UI components for visual consistency, spacing, and color harmony.
- Evaluate usability heuristics: is it intuitive? Are errors communicated clearly?
- Check loading states, empty states, and edge case UX.
- Write a **UX Review Report** to `findings.md` with prioritized improvement suggestions.
- Do NOT modify code; provide actionable design feedback for Frontend.
"""
    },
    "Telemetry_Agent": {
        "description": "Observability, logging, metrics, error tracking.",
        "color": "cyan",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Telemetry Agent — Observability Engineer
If it can't be monitored, it can't be trusted. Your responsibilities:
- Review all code for structured logging (are errors logged with context? severity levels?).
- Check for performance instrumentation (timing, throughput, resource consumption).
- Verify error boundaries and crash reporting hooks exist.
- Write a **Telemetry Coverage Report** to `findings.md`.
- Optionally, write a `telemetry_setup.md` guide to `findings.md` for the team.
"""
    },
    "QA_Engineer": {
        "description": "Automated tests: unit, integration, end-to-end.",
        "color": "green",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: QA Engineer — Test Automation Specialist
Bugs that reach production are your failure. Your responsibilities:
- Read `findings.md` and `task_plan.md` to understand the features implemented.
- Write unit tests for all public functions and edge cases.
- Write integration tests for all API endpoints and data flows.
- Use the testing framework already present in the project (don't introduce new ones).
- Ensure test files are co-located next to or within a `/tests` directory.
- Never write tests that always pass; test real failure conditions.
"""
    },
    "Ops_Agent": {
        "description": "CI/CD pipelines, Dockerfiles, deployment configs, IaC.",
        "color": "blue",
        "model": "auto-gemini-3",
        "prompt": SHARED_CONTRACT + """
## Your Role: Ops Agent — DevOps & Infrastructure Engineer
You make deployments boring (in the best way). Your responsibilities:
- Read `findings.md` for the tech stack and environment requirements.
- Write a `Dockerfile` for the application using a minimal, hardened base image.
- Write a CI/CD pipeline (GitHub Actions `.github/workflows/ci.yml`) that: lints, tests, and builds.
- Write a `docker-compose.yml` for local development if multiple services are involved.
- Document all environment variables in a `.env.example` file.
"""
    }
}



def generate_prompt(mission):
    # Construct the Agent Pool description string
    pool_desc = ""
    for name, info in AGENT_POOL.items():
        pool_desc += f"- {name}: {info['description']} (Model: {info['model']})\n"

    return f"""
You are Sisyphus, the Orchestrator and Principal Architect.
Your goal is to hire a squad of specialized sub-agents from the **Oh-My-Opencode Agent Pool** to complete the following mission:
"{mission}"

**Available Agent Pool:**
{pool_desc}

**Rules for Hiring:**
1. Select 2-5 distinct roles from the Pool that best fit the mission.
2. **You MUST use the exact names** from the pool (e.g., 'Oracle', 'Frontend', 'Librarian').
3. **[CRITICAL]** The FINAL agent in the list MUST be 'Quality_Validator'.
   - Role: Verify all work done by previous agents.
   - Responsibilities: Check file existence, validate code syntax, and ensure the mission goal is met.
4. **[CRITICAL - CONCURRENCY RULES]** You MUST explicitly assign an execution mode based on the agent's role:
   - **Reviewer Agents** (Docs, Tests, Telemetry, Usability, Security, Best Practices) MUST be assigned `mode: "parallel"`. They analyze existing code concurrently.
   - **Implementer Agents** (Junior, Frontend, Oracle creating architecture) MUST be assigned `mode: "serial"`. They generate or modify code and MUST NOT run at the same time to prevent file-write conflicts.
   - **Validator** (`Quality_Validator`) is automatically assigned `mode: "validator"`.
5. Use the specific prompts provided below for each role, but **customize them** slightly to fit the specific mission context.

**Output Format:**
Please output ONE single YAML block enclosed in triple backticks (```yaml).
The YAML must follow this exact structure:

```yaml
subagents:
  - name: "Oracle" # Must match pool name
    description: "Specific role description for this mission"
    color: "magenta" # Use pool color
    model: "auto-gemini-3" # Use pool model
    mode: "parallel" # or "serial"
    prompt: |
      You are Oracle.
      [Specific instructions for this mission...]

      Additionally, agents can communicate with each other using:
      3. TO SEND A MESSAGE TO ANOTHER AGENT:
      <<SEND_MESSAGE to="agent_name">>
      Message content here...
      <<END_MESSAGE>>

      4. TO BROADCAST TO ALL AGENTS:
      <<BROADCAST>>
      Message content here...
      <<END_BROADCAST>>

  - name: "Quality_Validator"
    description: "Verifies the work"
    color: "green"
    model: "auto-gemini-3"
    mode: "validator" # Enforced by orchestrator for this name
    prompt: |
      You are Quality_Validator.
      [Specific verification instructions...]

      Additionally, agents can communicate with each other using:
      3. TO SEND A MESSAGE TO ANOTHER AGENT:
      <<SEND_MESSAGE to="agent_name">>
      Message content here...
      <<END_MESSAGE>>

      4. TO BROADCAST TO ALL AGENTS:
      <<BROADCAST>>
      Message content here...
      <<END_BROADCAST>>
```

Do not include any other text outside the YAML block.
"""

def generate_from_preset(preset, mission):
    """Generate subagents.yaml content from a preset definition."""
    agents = preset.get("agents", [])
    lines = ["subagents:"]
    for i, agent_cfg in enumerate(agents):
        name = agent_cfg.get("name", f"Agent{i}")
        mode = agent_cfg.get("mode", "parallel")
        info = AGENT_POOL.get(name, {})
        color = info.get("color", assign_color(i))
        model = info.get("model", "auto-gemini-3")
        base_prompt = info.get("prompt", f"You are {name}.")

        lines.append(f'  - name: "{name}"')
        lines.append(f'    description: "{info.get("description", name)}"')
        lines.append(f'    color: "{color}"')
        lines.append(f'    model: "{model}"')
        lines.append(f'    mode: "{mode}"')
        lines.append(f'    prompt: |')
        lines.append(f'      {base_prompt}')
        lines.append(f'      Mission: {mission}')
        lines.append('')
    return "\n".join(lines)

def _save_config_and_team(yaml_content, plan_content, mission):
    """Save subagents.yaml, task_plan.md, and generate team config."""
    import yaml as yaml_module

    # Save subagents.yaml
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    # Save task_plan.md
    with open("task_plan.md", 'w', encoding='utf-8') as f:
        f.write(plan_content)

    # Initialize other Manus Protocol files if they don't exist
    if not os.path.exists("findings.md"):
        with open("findings.md", 'w', encoding='utf-8') as f:
            f.write("# Findings & Scratchpad\n\nUse this file to store shared knowledge, research notes, and intermediate outputs.")

    if not os.path.exists("progress.md"):
        with open("progress.md", 'w', encoding='utf-8') as f:
            f.write(f"# Mission Progress\n\nMission: {mission}\n\n## Status Log\n")

    # Generate team config
    ensure_dirs()
    parsed = yaml_module.safe_load(yaml_content)
    team_name = mission.lower().replace(' ', '-')[:30] or "mission"

    team_config = {
        "name": team_name,
        "created_at": time.time(),
        "leader": "leader",
        "members": [],
        "settings": {"backend": "auto", "poll_interval_ms": 1000}
    }

    for agent in parsed.get("subagents", []):
        team_config["members"].append({
            "agent_id": f"{agent['name'].lower()}@{team_name}",
            "name": agent["name"],
            "color": agent.get("color", "white"),
            "model": agent.get("model", "auto-gemini-3"),
            "mode": agent.get("mode", "parallel"),
            "status": "pending"
        })

    config_path = os.path.join(STATE_DIR, "config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(team_config, f, indent=2)

    print(f"[Planner] Configuration saved to {CONFIG_FILE}.")
    print(f"[Planner] Created 'task_plan.md', 'findings.md', 'progress.md'.")
    print(f"[Planner] Team config saved to {config_path}")
    print("[Planner] Ready to execute. Run 'python3 scripts/orchestrator.py' to start.")

def main():
    # Fix for Windows CP949 encoding issue
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python3 scripts/planner.py <mission_description>")
        sys.exit(1)

    # Check for --preset flag
    preset_name = None
    if "--preset" in sys.argv:
        idx = sys.argv.index("--preset")
        if idx + 1 < len(sys.argv):
            preset_name = sys.argv[idx + 1]
            # Remove --preset and its value from args
            args = [a for i, a in enumerate(sys.argv[1:], 1) if i != idx and i != idx + 1]
        else:
            print("[Planner] Error: --preset flag requires a preset name")
            sys.exit(1)
    else:
        args = sys.argv[1:]

    mission = " ".join(args)
    print(f"[Planner] Analyzing mission: '{mission}'...")

    if preset_name:
        config = SwarmConfig.load()
        if preset_name in config.presets:
            print(f"[Planner] Using preset: {preset_name}")
            preset = config.presets[preset_name]
            # Generate YAML from preset instead of calling Gemini
            yaml_content = generate_from_preset(preset, mission)
            plan_content = f"# Task Plan (From Preset: {preset_name})\n\nMission: {mission}\n\n- [ ] Review Mission\n- [ ] Execute Tasks"

            # Skip to saving section
            print("\n[Planner] Proposed Plan:")
            print("------------------------------------------")
            print("[1] TASK PLAN (task_plan.md):")
            print(plan_content)
            print("\n[2] AGENT ROSTER (subagents.yaml):")
            for line in yaml_content.splitlines():
                if "name:" in line or "description:" in line:
                    print(line)
            print("------------------------------------------")

            if "--yes" not in sys.argv:
                confirm = input("\n[Plan Mode] Save this configuration? [y/N]: ").strip().lower()
                if confirm != 'y':
                    print("[Planner] Operation cancelled by user.")
                    sys.exit(0)

            # Save artifacts and generate team config (shared code path)
            _save_config_and_team(yaml_content, plan_content, mission)
            sys.exit(0)
        else:
            print(f"[Planner] Error: Preset '{preset_name}' not found in swarm-config.yaml")
            sys.exit(1)

    print("[Planner] Consulting with Supervisor Agent...")

    # Load config from JSON if exists
    config_path = os.path.expanduser("~/.gemini/antigravity/swarm_config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except: pass

    mode = config.get("mode", "cloud")
    use_ollama = (mode == "local") or ("--provider ollama" in sys.argv)

    if use_ollama:
        if config.get("ollama_url"):
            os.environ["OLLAMA_API_BASE"] = config.get("ollama_url")
        if config.get("ollama_model"):
            os.environ["OLLAMA_MODEL"] = config.get("ollama_model")

        # Fallback Check
        try:
            import ollama_client
            if not ollama_client.check_connection():
                print("WARNING: Local Ollama server is not reachable. Falling back to Cloud (Gemini).")
                use_ollama = False
        except ImportError:
             use_ollama = False
    
    gemini_path = None
    
    if not use_ollama:
        gemini_path = get_gemini_path()
        if not gemini_path:
            # Fallback check?
            if os.environ.get("OLLAMA_API_BASE"):
                use_ollama = True
            else:
                print("Error: 'gemini' executable not found.")
                print("Please resolve this by:\n1. Installing gemini CLI.\n2. Ensuring it is in your PATH.\n3. Or setting GEMINI_PATH environment variable.")
                print("OR: Set OLLAMA_API_BASE to use local Ollama.")
                sys.exit(1)

    full_prompt = generate_prompt(mission)

    try:
        output = ""
        
        if use_ollama:
            try:
                import ollama_client
            except ImportError:
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                import ollama_client
                
            # We use non-streaming or accumulate streaming
            # Generate often explicitly follows instruction better for large blocks
            # But chat is safer for context. Let's use chat.
            
            # The prompt is large, so we wait.
            # Using 'generate' might be better for single-turn instruction following if chat has a heavy system prompt bias.
            # But chat is standard.
            
            model_to_use = os.environ.get("OLLAMA_MODEL", "qwen3:32b")
            print(f"[Planner] Requesting plan from Ollama ({model_to_use})...")
            
            gen = ollama_client.chat(full_prompt, model=model_to_use, stream=True)
            for chunk in gen:
                print(chunk, end="", flush=True)
                output += chunk
            print()
            
        else:
            # Call gemini to generate layout
            process = subprocess.run(
                [gemini_path, "chat", full_prompt],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            output = process.stdout
            
            if process.returncode != 0:
                 print(f"[Planner] Error from Gemini CLI: {process.stderr}")
                 sys.exit(process.returncode)
        
        # Extract YAML block
        yaml_match = re.search(r"```yaml\n(.*?)\n```", output, re.DOTALL)
        
        # Extract Plan block
        plan_match = re.search(r"\[PLAN\]\n(.*?)\n\[/PLAN\]", output, re.DOTALL)
        
        if yaml_match:
            yaml_content = yaml_match.group(1)
            
            # --- HOTFIX: Enforce Working Model ---
            # We enforce 'auto-gemini-3' for compatibility
            if "gemini-2.0" in yaml_content or "gemini-1.5" in yaml_content or "gemini-3-flash" in yaml_content:
                print("[Planner] [WARN] Validating model availability. Switching to 'auto-gemini-3' (system default)...")
                yaml_content = re.sub(r"gemini-\d+\.\d+[-\w]*", "auto-gemini-3", yaml_content)
                yaml_content = re.sub(r"gemini-3-flash", "auto-gemini-3", yaml_content)
            # ----------------------------------

            plan_content = plan_match.group(1).strip() if plan_match else "# Task Plan (Auto-Generated)\n- [ ] Review Mission"
            
            # Plan Mode (Confirmation)
            print("\n[Planner] Proposed Plan:")
            print("------------------------------------------")
            print("[1] TASK PLAN (task_plan.md):")
            print(plan_content)
            print("\n[2] AGENT ROSTER (subagents.yaml):")
            # Print only agent names and descriptions for brevity
            for line in yaml_content.splitlines():
                if "name:" in line or "description:" in line:
                    print(line)
            print("------------------------------------------")

            if "--yes" not in sys.argv:
                confirm = input("\n[Plan Mode] Save this configuration? [y/N]: ").strip().lower()
                if confirm != 'y':
                    print("[Planner] Operation cancelled by user.")
                    sys.exit(0)

            # Save artifacts and generate team config
            _save_config_and_team(yaml_content, plan_content, mission)
        else:
            print("[Planner] Error: Could not parse YAML from agent output.")
            print("--- Raw Output (STDOUT) ---")
            print(output)
            if not use_ollama:
                print("--- Error Output (STDERR) ---")
                print(process.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"[Planner] Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
