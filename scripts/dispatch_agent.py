import sys
import subprocess
import re
import os
import shutil
import json
import time

def parse_and_execute_side_effects(output):
    """
    Parses the agent output for special tags and executes the side effects.
    Supports:
    1. <<WRITE_FILE path="...">>content<<END_WRITE>>
    2. <<RUN_COMMAND>>command<<END_COMMAND>>
    """
    # Pattern for WRITE_FILE
    # Captures path in group 1, content in group 2.
    # Uses DOTALL to match newlines in content.
    write_pattern = re.compile(r'<<WRITE_FILE path="([^"]+)">>(.*?)<<END_WRITE>>', re.DOTALL)
    
    # Pattern for RUN_COMMAND
    # Captures command in group 1.
    run_pattern = re.compile(r'<<RUN_COMMAND>>(.*?)<<END_COMMAND>>', re.DOTALL)

    # Execute Writes
    for match in write_pattern.finditer(output):
        path = match.group(1)
        content = match.group(2).strip() # Remove leading/trailing newline from the tag block itself if desired, 
                                         # but keeping exact content is safer. 
                                         # Typically the tag might be on its own line, so we might want to strip first/last newline.
                                         # Let's strip one leading newline if present and one trailing.
        if content.startswith('\n'): content = content[1:]
        if content.endswith('\n'): content = content[:-1]
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[Shim] Successfully wrote to {path}")
        except Exception as e:
            print(f"[Shim] Error writing to {path}: {e}")

    # Execute Commands
    for match in run_pattern.finditer(output):
        command = match.group(1).strip()
        print(f"[Shim] Executing command: {command}")
        try:
            # Run command and print output
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            print(f"[Shim] Command Output:\n{result.stdout}")
            if result.stderr:
                print(f"[Shim] Command Error:\n{result.stderr}")
        except Exception as e:
            print(f"[Shim] Error executing command: {e}")

def get_gemini_path():
    # 1. Check env var
    path = os.environ.get("GEMINI_PATH")
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    
    # 2. Check system PATH
    path = shutil.which("gemini")
    if path:
        return path
        
    # 3. Last version fallback (Mac-specific from user context, for convenience)
    # But ideally this should just fail if not found for strict portability.
    # We will soft-fail.
    return None

def main():
    # Fix for Windows CP949 encoding issue
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python3 dispatch_agent.py <task_description> [--log-file <path>]")
        sys.exit(1)

    gemini_path = get_gemini_path()
    if not gemini_path:
        print("Error: 'gemini' executable not found.")
        print("Please resolve this by:\n1. Installing gemini CLI.\n2. Ensuring it is in your PATH.\n3. Or setting GEMINI_PATH environment variable.")
        sys.exit(1)

    # Parse arguments manually to keep it simple
    args = sys.argv[1:]
    
    log_file = None
    if "--log-file" in args:
        idx = args.index("--log-file")
        if idx + 1 < len(args):
            log_file = args[idx + 1]
            # Remove the flag and value from args so the rest is the task
            del args[idx:idx+2]

    model_name = "auto-gemini-3" # Default
    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            model_name = args[idx + 1]
            del args[idx:idx+2]
            
    log_format = "text"
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            log_format = args[idx + 1]
            del args[idx:idx+2]
    
    task = " ".join(args)

    shim_instruction = (
        "You are a sub-agent working in the Antigravity IDE. "
        "Your environment lacks native writing tools, but I have a shim layer to help you. "
        "To perform actions, you MUST use the following syntax PRECISELY:\n\n"
        "1. TO WRITE A FILE:\n"
        '<<WRITE_FILE path="path/to/file.ext">>\n'
        "File content goes here...\n"
        "<<END_WRITE>>\n\n"
        "2. TO RUN A SHELL COMMAND:\n"
        "<<RUN_COMMAND>>\n"
        "ls -la\n"
        "<<END_COMMAND>>\n\n"
        "Now, perform the following task:\n"
    )

    full_prompt = f"{shim_instruction}{task}"
    
    log_file_handle = None
    if log_file:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            log_file_handle = open(log_file, 'a', encoding='utf-8')
        except Exception as e:
            print(f"[Shim] Warning: Could not open log file: {e}")

    def log_message(msg_type, content):
        if not log_file_handle: return
        
        try:
            if log_format == "json":
                entry = {
                    "timestamp": time.time(),
                    "type": msg_type,
                    "content": content
                }
                log_file_handle.write(json.dumps(entry) + "\n")
            else:
                log_file_handle.write(f"[{msg_type.upper()}] {content}\n")
            log_file_handle.flush()
        except Exception as e:
            print(f"[Shim] Warning: Could not write to log: {e}")

    start_msg = f"Dispatching task to sub-agent ({model_name}): {task}"
    print(f"[Shim] {start_msg}")
    log_message("status", "starting")
    log_message("info", start_msg)

    try:
        cmd = [gemini_path, "chat", "--model", model_name, full_prompt]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8'
        )
        
        stdout_acc = ""
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line.strip())
                log_content = line.strip()
                stdout_acc += line
                log_message("output", log_content)
        
        # Parse side effects after completion (Shim limitation: post-execution)
        parse_and_execute_side_effects(stdout_acc)

        if process.returncode == 0:
             log_message("status", "completed")
        else:
             log_message("status", "failed")
             stderr = process.stderr.read()
             log_message("error", stderr)
             sys.exit(process.returncode)

        if log_file_handle:
            log_file_handle.close()

    except Exception as e:
        print(f"Error dispatching agent: {e}")

def run_ollama_agent(model_name, full_prompt, log_message):
    """
    Runs the agent using the local Ollama client.
    """
    try:
        import ollama_client
    except ImportError:
        # Try to import from the same directory
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            import ollama_client
        except ImportError:
            print("[Shim] Error: Could not import ollama_client.py")
            sys.exit(1)

    print(f"[Shim] connecting to Ollama...")
    
    # Accumulate output for side-effect parsing
    stdout_acc = ""
    
    # We use the chat endpoint. 
    # Note: 'model_name' from the arguments might be 'auto-gemini-3'. 
    # We should default to something reasonable if it's the default gemini model.
    if model_name == "auto-gemini-3":
        model_name = os.environ.get("OLLAMA_MODEL", "qwen3:32b")
    
    print(f"[Shim] Using model: {model_name}")

    try:
        # Get streaming response
        response_generator = ollama_client.chat(full_prompt, model=model_name, stream=True)
        
        for chunk in response_generator:
            # Check if chunk is a dict (error) or string
            if isinstance(chunk, dict):
                 # Should not happen with current ollama_client implementation but good safety
                 chunk = str(chunk)
            
            print(chunk, end="", flush=True)
            stdout_acc += chunk
            # Log roughly by lines if possible, or just chunks
            if "\n" in chunk:
                log_message("output", chunk.strip())

        print() # Newline at end
        
        # Parse side effects
        parse_and_execute_side_effects(stdout_acc)
        log_message("status", "completed")

    except Exception as e:
        print(f"[Shim] Error executing Ollama agent: {e}")
        log_message("error", str(e))
        log_message("status", "failed")
        sys.exit(1)

def main():
    # Fix for Windows CP949 encoding issue
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python3 dispatch_agent.py <task_description> [--log-file <path>]")
        sys.exit(1)

    # Load config from JSON if exists
    config_path = os.path.expanduser("~/.gemini/antigravity/swarm_config.json")
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except: pass

    # Check for Ollama mode (ENV > Config > Flag)
    # Actually, let's make Config > Env for "mode" switch to allow the toggle to work
    # But allow ENV override for specific URLs if needed?
    # The requirement is the toggle controls behavior. So Config wins for "mode".
    
    mode = config.get("mode", "cloud")
    if os.environ.get("OLLAMA_API_BASE"):
        # If env var is explicitly set, maybe we honor it? 
        # But the user wants a toggle. Let's say if config says "local", we use local.
        # If config says "cloud", we use cloud (ignoring env var? or maybe env var is for the *client* settings)
        pass

    use_ollama = (mode == "local") or ("--provider ollama" in sys.argv)
    
    # Update Client Defaults if using local
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
            print("WARNING: Could not import ollama_client. Falling back to Cloud.")
            use_ollama = False

    # Clean up args if we have our custom flag (though we check env var mostly)
    if "--provider" in sys.argv:
        try:
            p_idx = sys.argv.index("--provider")
            del sys.argv[p_idx:p_idx+2]
        except: pass

    # If NOT using Ollama, we need gemini path
    gemini_path = None
    if not use_ollama:
        gemini_path = get_gemini_path()
        if not gemini_path:
            # Fallback to checking if we should use Ollama if gemini is missing but we have ollama env?
            # For now, stick to strict logic.
            print("Error: 'gemini' executable not found.")
            print("Please resolve this by:\n1. Installing gemini CLI.\n2. Ensuring it is in your PATH.\n3. Or setting GEMINI_PATH environment variable.")
            print("OR: Set OLLAMA_API_BASE to use local Ollama.")
            sys.exit(1)

    # Parse arguments manually to keep it simple
    args = sys.argv[1:]
    
    log_file = None
    if "--log-file" in args:
        idx = args.index("--log-file")
        if idx + 1 < len(args):
            log_file = args[idx + 1]
            # Remove the flag and value from args so the rest is the task
            del args[idx:idx+2]

    model_name = "auto-gemini-3" # Default
    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 < len(args):
            model_name = args[idx + 1]
            del args[idx:idx+2]
            
    log_format = "text"
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            log_format = args[idx + 1]
            del args[idx:idx+2]
    
    task = " ".join(args)

    shim_instruction = (
        "You are a sub-agent working in the Antigravity IDE. "
        "Your environment lacks native writing tools, but I have a shim layer to help you. "
        "To perform actions, you MUST use the following syntax PRECISELY:\n\n"
        "1. TO WRITE A FILE:\n"
        '<<WRITE_FILE path="path/to/file.ext">>\n'
        "File content goes here...\n"
        "<<END_WRITE>>\n\n"
        "2. TO RUN A SHELL COMMAND:\n"
        "<<RUN_COMMAND>>\n"
        "ls -la\n"
        "<<END_COMMAND>>\n\n"
        "Now, perform the following task:\n"
    )

    full_prompt = f"{shim_instruction}{task}"
    
    log_file_handle = None
    if log_file:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            log_file_handle = open(log_file, 'a', encoding='utf-8')
        except Exception as e:
            print(f"[Shim] Warning: Could not open log file: {e}")

    def log_message(msg_type, content):
        if not log_file_handle: return
        
        try:
            if log_format == "json":
                entry = {
                    "timestamp": time.time(),
                    "type": msg_type,
                    "content": content
                }
                log_file_handle.write(json.dumps(entry) + "\n")
            else:
                log_file_handle.write(f"[{msg_type.upper()}] {content}\n")
            log_file_handle.flush()
        except Exception as e:
            print(f"[Shim] Warning: Could not write to log: {e}")

    start_msg = f"Dispatching task to sub-agent (Model: {model_name}, Backend: {'Ollama' if use_ollama else 'Gemini'}): {task}"
    print(f"[Shim] {start_msg}")
    log_message("status", "starting")
    log_message("info", start_msg)

    if use_ollama:
        run_ollama_agent(model_name, full_prompt, log_message)
        if log_file_handle:
            log_file_handle.close()
        return

    try:
        cmd = [gemini_path, "chat", "--model", model_name, full_prompt]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8'
        )
        
        stdout_acc = ""
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line.strip())
                log_content = line.strip()
                stdout_acc += line
                log_message("output", log_content)
        
        # Parse side effects after completion (Shim limitation: post-execution)
        parse_and_execute_side_effects(stdout_acc)

        if process.returncode == 0:
             log_message("status", "completed")
        else:
             log_message("status", "failed")
             stderr = process.stderr.read()
             log_message("error", stderr)
             sys.exit(process.returncode)

        if log_file_handle:
            log_file_handle.close()

    except Exception as e:
        print(f"Error dispatching agent: {e}")

if __name__ == "__main__":
    main()
