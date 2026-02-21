import json
import urllib.request
import urllib.error
import os
import sys

# Default to localhost if not set
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:32b")

def chat(prompt, model=None, stream=True):
    """
    sends a chat request to the local ollama instance.
    yields lines of text content from the response.
    """
    if model is None:
        model = DEFAULT_MODEL
        
    url = f"{OLLAMA_API_BASE}/api/chat"
    
    # Simple message structure for a one-shot prompt
    messages = [{"role": "user", "content": prompt}]
    
    data = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    encoded_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, 
        data=encoded_data, 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if stream:
                for line in response:
                    if line:
                        decoded_line = line.decode("utf-8").strip()
                        if decoded_line:
                            try:
                                json_obj = json.loads(decoded_line)
                                msg_content = json_obj.get("message", {}).get("content", "")
                                if msg_content:
                                    # We yield the content directly. 
                                    # Note: output might need newline handling depending on consumer.
                                    # But looking at Swarm's dispatch_agent, it expects lines.
                                    # Ollama might stream partial tokens. 
                                    # We'll buffer appropriately or just yield chunks.
                                    # Actually, let's yield the raw text chunks to be flexible.
                                    yield msg_content
                                if json_obj.get("done"):
                                    break
                            except json.JSONDecodeError:
                                pass
            else:
                # Non-streaming
                body = response.read().decode("utf-8")
                json_obj = json.loads(body)
                yield json_obj.get("message", {}).get("content", "")
                
    except urllib.error.URLError as e:
        yield f"Error connecting to Ollama: {e}"
        print(f"Error connecting to Ollama at {url}: {e}", file=sys.stderr)

def generate(prompt, model=None, stream=True):
    """
    Sends a generate request (raw completion) to Ollama.
    """
    if model is None:
        model = DEFAULT_MODEL
        
    url = f"{OLLAMA_API_BASE}/api/generate"
    data = {"model": model, "prompt": prompt, "stream": stream}
    
    encoded_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, 
        data=encoded_data, 
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if stream:
                for line in response:
                    if line:
                        decoded_line = line.decode("utf-8").strip()
                        if decoded_line:
                            try:
                                json_obj = json.loads(decoded_line)
                                content = json_obj.get("response", "")
                                if content:
                                    yield content
                                if json_obj.get("done"):
                                    break
                            except:
                                pass
            else:
                body = response.read().decode("utf-8")
                json_obj = json.loads(body)
                yield json_obj.get("response", "")
    except Exception as e:
         yield f"Error: {e}"

def check_connection(base_url=None):
    if base_url is None:
        base_url = OLLAMA_API_BASE
    
    try:
        # We can just check the version endpoint or tag list. 
        # But root / usually returns 'Ollama is running'
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except:
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        p = " ".join(sys.argv[1:])
        print(f"Asking Ollama ({OLLAMA_API_BASE}): {p}")
        full_resp = ""
        for chunk in chat(p, model=DEFAULT_MODEL):
            print(chunk, end="", flush=True)
            full_resp += chunk
        print("\n--- Done ---")
    else:
        print(f"Ollama running? {check_connection()}")
