import yaml
#
# Inspired by "Oh-My-Opencode" (https://github.com/code-yeongyu/oh-my-opencode)
# Adopts the "Manus Protocol" for state management and TUI visualization.
#
import sys
import subprocess
import threading
import time
import os
import random
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

# Configuration
CONFIG_FILE = "subagents.yaml"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DISPATCH_SCRIPT = os.path.join(SCRIPT_DIR, "dispatch_agent.py")

# Fancy Spinner Characters (Braille or Dots)
SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
# Alternative: ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

# --- Loop Safety ---
# Max times a single agent will be auto-retried before pausing for human review.
MAX_RETRIES = 2
# Sentinel file — touch this file to trigger a graceful human-intervention pause.
HUMAN_BREAK_SENTINEL = "HUMAN_BREAK"

def check_human_break():
    """Returns True if the human break sentinel file exists, then removes it."""
    if os.path.exists(HUMAN_BREAK_SENTINEL):
        os.remove(HUMAN_BREAK_SENTINEL)
        return True
    return False

class SubAgentRunner:
    def __init__(self, name, prompt, color, model="auto-gemini-3", mode="parallel", demo_mode=False):
        self.name = name
        self.prompt = prompt
        self.color = color
        self.model = model
        self.mode = mode  # parallel, serial, validator
        self.status = "Pending"
        self.log_file = f"logs/{name.lower().replace(' ', '_')}.log"
        self.last_log = ""
        self.is_running = False
        self.log_handle = None
        self.demo_mode = demo_mode
        self.start_time = None
        self.end_time = None
        self.retry_count = 0   # Loop safety: tracks how many times this agent has been retried
        self.skipped = False   # Loop safety: marks agent as manually skipped by human
        
        # Ensure log dir exists
        os.makedirs("logs", exist_ok=True)

    def run(self):
        self.is_running = True
        self.status = "Running"
        self.start_time = time.time()
        
        if self.demo_mode:
            self._run_demo()
        else:
            self._run_real()

        self.end_time = time.time()
        self.is_running = False
        if self.log_handle:
            self.log_handle.close()

    def _run_demo(self):
        """Simulates agent execution for TUI testing."""
        steps = [
            "Initializing agent context...",
            "Reading task_plan.md...",
            "Analyzing requirements...",
            "Thinking...",
            "Generating solution code...",
            "Writing to file...",
            "Verifying output...",
            "Finalizing..."
        ]
        
        for step in steps:
            self.last_log = step
            time.sleep(random.uniform(0.5, 1.5))
            
        # 80% chance of success, 20% failure for demo realism
        if random.random() > 0.1:
            self.status = "Completed"
            self.last_log = "Task completed successfully."
        else:
            self.status = "Failed"
            self.last_log = "Error: Simulated failure."

    def _run_real(self):
        cmd = [
            sys.executable, 
            DISPATCH_SCRIPT, 
            self.prompt,
            "--log-file", 
            self.log_file,
            "--model",
            self.model
        ]
        
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            while self.process.poll() is None:
                self._read_new_logs()
                time.sleep(0.1)
                
            self.status = "Completed" if self.process.returncode == 0 else "Failed"
            self._read_new_logs() 
            
        except Exception as e:
            self.status = f"Error: {str(e)}"

    def _read_new_logs(self):
        if not self.log_handle:
            if os.path.exists(self.log_file):
                try:
                    self.log_handle = open(self.log_file, 'r', encoding='utf-8', errors='replace')
                except:
                    pass
        
        if self.log_handle:
            try:
                lines = self.log_handle.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line:
                        self.last_log = last_line
            except:
                pass

    def get_duration(self):
        if self.start_time:
            end = self.end_time if self.end_time else time.time()
            return f"{end - self.start_time:.1f}s"
        return "-"

def create_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body")
    )
    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1)
    )
    return layout

def generate_dashboard(runners, spinner_idx):
    spinner_char = SPINNERS[spinner_idx % len(SPINNERS)]
    
    # 1. Agent Table
    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("Agent", style="bold white")
    table.add_column("Model", style="dim cyan")
    table.add_column("Role", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right")
    
    active_log = "Waiting for agents..."
    active_agent = "System"

    for runner in runners:
        # Status Logic
        if runner.status == "Running":
            status_style = "bold yellow"
            status_icon = spinner_char
            active_log = runner.last_log
            active_agent = runner.name
        elif runner.status == "Completed":
            status_style = "bold green"
            status_icon = "✔"
        elif "Error" in runner.status or runner.status == "Failed":
            status_style = "bold red"
            status_icon = "✘"
        else: # Pending
            status_style = "dim"
            status_icon = "•"

        retry_suffix = f" (retry {runner.retry_count}/{MAX_RETRIES})" if runner.retry_count > 0 else ""
        status_text = ("Skipped" if runner.skipped else runner.status) + retry_suffix
        table.add_row(
            f"[{runner.color}]{runner.name}[/{runner.color}]",
            runner.model,
            runner.mode,
            f"[{status_style}]{status_icon} {status_text}[/{status_style}]",
            runner.get_duration()
        )

    # 2. Activity Panel
    log_content = Text()
    log_content.append(f"Agent: {active_agent}\n", style="bold cyan")
    log_content.append(f"Action: {active_log}", style="white")
    
    activity_panel = Panel(
        Align.center(log_content, vertical="middle"),
        title="Live Activity",
        border_style="blue",
        box=box.ROUNDED
    )

    # 3. Header
    header = Panel(
        Align.center("[bold magenta]✨ Antigravity Swarm Mission Control ✨[/bold magenta]"),
        box=box.HEAVY,
        style="white on black"
    )

    return header, table, activity_panel

def main():
    # Fix for Windows CP949 encoding issue
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    # Demo Mode Check
    demo_mode = "--demo" in sys.argv
    if demo_mode:
        print("[Orchestrator] Running in DEMO MODE (Simulated Execution)")

    if not os.path.exists(CONFIG_FILE) and not demo_mode:
        print(f"Error: {CONFIG_FILE} not found.")
        sys.exit(1)

    if demo_mode:
        # Mock config for demo
        config = {
            'subagents': [
                {'name': 'Architect', 'color': 'magenta', 'prompt': '', 'mode': 'parallel'},
                {'name': 'Engineer', 'color': 'cyan', 'prompt': '', 'mode': 'parallel'},
                {'name': 'Tester', 'color': 'yellow', 'prompt': '', 'mode': 'serial'},
                {'name': 'Quality_Validator', 'color': 'green', 'prompt': '', 'mode': 'validator'}
            ]
        }
        manus_context = ""
    else:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Manus Protocol: Context Injection
        manus_context = "\n\n[SHARED STATE]"
        for f_name in ["task_plan.md", "findings.md", "progress.md"]:
            if os.path.exists(f_name):
                with open(f_name, 'r', encoding='utf-8') as f:
                    manus_context += f"\n--- {f_name} ---\n{f.read()}"
        
        manus_context += "\n[END SHARED STATE]\n"
        manus_context += "Instructions: You must read the shared state above. Update 'findings.md' with new discoveries and 'progress.md' with your status using <<WRITE_FILE>>."

    runners = []
    parallel_runners = []
    serial_runners = []
    validator_runners = []

    for agent_cfg in config.get('subagents', []):
        full_prompt = agent_cfg['prompt'] + manus_context
        name = agent_cfg['name']
        mode = agent_cfg.get('mode', 'parallel')
        
        if name == 'Quality_Validator': mode = 'validator'
            
        runner = SubAgentRunner(
            name, 
            full_prompt, 
            agent_cfg.get('color', 'white'),
            agent_cfg.get('model', 'auto-gemini-3'),
            mode,
            demo_mode=demo_mode
        )
        
        if mode == 'validator': validator_runners.append(runner)
        elif mode == 'serial': serial_runners.append(runner)
        else: parallel_runners.append(runner)

    runners = parallel_runners + serial_runners + validator_runners

    if "--yes" not in sys.argv and not demo_mode:
        try:
            confirm = input("\n[Plan Mode] Execute this team? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("[Orchestrator] Execution cancelled.")
                return
        except EOFError:
            print("[Orchestrator] No input stream. Assuming --yes.")

    console = Console()
    layout = create_layout()
    
    spinner_idx = 0
    mission_aborted = False

    def run_agent_with_retry(runner, live_ctx):
        """Run a single agent, retrying up to MAX_RETRIES on failure.
        On exceeding retries, pauses the Live display and prompts human.
        Returns True if the mission should be aborted."""
        nonlocal mission_aborted

        while True:
            # Reset for a clean run
            runner.status = "Running"
            runner.start_time = time.time()
            runner.end_time = None
            runner.is_running = True
            runner._run_real()
            runner.end_time = time.time()
            runner.is_running = False

            if runner.status == "Completed":
                return False  # success, no abort

            # --- FAILURE PATH ---
            runner.retry_count += 1
            if runner.retry_count <= MAX_RETRIES:
                runner.status = f"Retrying ({runner.retry_count}/{MAX_RETRIES})"
                runner.last_log = f"Auto-retrying... ({runner.retry_count}/{MAX_RETRIES})"
                time.sleep(2)  # brief back-off before retry
                continue

            # Exceeded auto-retries -> pause for human
            live_ctx.stop()
            console.print(f"\n[bold yellow]⚠ HUMAN INTERVENTION REQUIRED[/bold yellow]")
            console.print(f"Agent [bold]{runner.name}[/bold] failed after {MAX_RETRIES} retries.")
            console.print("Last log: " + runner.last_log)
            console.print("\n  [r] Retry once more")
            console.print("  [s] Skip this agent and continue")
            console.print("  [a] Abort the entire mission")
            choice = input("\nYour choice [r/s/a]: ").strip().lower()
            live_ctx.start()

            if choice == 'r':
                runner.retry_count = 0  # reset counter for manual retry
                continue
            elif choice == 's':
                runner.status = "Skipped"
                runner.skipped = True
                return False
            else:  # 'a' or anything else
                mission_aborted = True
                return True

    with Live(layout, refresh_per_second=10, console=console) as live:
        
        def update_ui():
            nonlocal spinner_idx
            # Check sentinel file for manual human break
            if check_human_break():
                live.stop()
                console.print("\n[bold yellow]⚠ HUMAN BREAK TRIGGERED (HUMAN_BREAK file detected)[/bold yellow]")
                console.print("  [r] Resume mission")
                console.print("  [a] Abort mission")
                choice = input("Your choice [r/a]: ").strip().lower()
                if choice == 'a':
                    nonlocal mission_aborted
                    mission_aborted = True
                live.start()
            header, table, activity = generate_dashboard(runners, spinner_idx)
            layout["header"].update(header)
            layout["left"].update(table)
            layout["right"].update(activity)
            spinner_idx += 1

        # Phase 1: Parallel reviewers (run all at once, poll for failures)
        threads = []
        thread_map = {}
        for r in parallel_runners:
            t = threading.Thread(target=r._run_real)
            t.start()
            threads.append(t)
            thread_map[t] = r
        
        while any(t.is_alive() for t in threads):
            update_ui()
            if mission_aborted:
                break
            time.sleep(0.1)

        # Post-parallel: handle any failures that need human review
        if not mission_aborted:
            for r in parallel_runners:
                if r.status not in ("Completed", "Skipped") and r.retry_count == 0:
                    r.retry_count += 1
                    aborted = run_agent_with_retry(r, live)
                    if aborted:
                        mission_aborted = True
                        break

        # Phase 2: Serial implementers (run one at a time with retry gate)
        if not mission_aborted:
            for r in serial_runners:
                aborted = run_agent_with_retry(r, live)
                update_ui()
                if aborted or mission_aborted:
                    mission_aborted = True
                    break
                update_ui()

        # Phase 3: Validator (single agent with retry)
        if not mission_aborted:
            for r in validator_runners:
                aborted = run_agent_with_retry(r, live)
                update_ui()
                if aborted:
                    mission_aborted = True
                    break
        
        # Final State
        update_ui()

    if mission_aborted:
        console.print("\n[bold red]Mission aborted by human intervention.[/bold red]")
        sys.exit(2)

    # Exit Check
    failed = [r for r in runners if r.status not in ("Completed", "Skipped")]
    skipped = [r for r in runners if r.skipped]
    if skipped:
        console.print(f"\n[yellow]Note: {len(skipped)} agent(s) were skipped by human request.[/yellow]")
    if failed:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
