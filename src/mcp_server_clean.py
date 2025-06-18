#!/usr/bin/env python3
"""
MCP AI Collab - Clean Implementation with Context Memory
Based on successful multi-ai-collab pattern
"""

import json
import sys
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import hashlib
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, try to load manually
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith('#') and '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Ensure unbuffered output - CRITICAL for MCP
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

# Server info
__version__ = "1.0.0"

# Context storage directory
CONTEXT_DIR = Path.home() / ".mcp-ai-collab" / "contexts"
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

def get_project_id() -> str:
    """Generate project ID from current working directory"""
    cwd = os.getcwd()
    return hashlib.md5(cwd.encode()).hexdigest()[:8]

def get_context_path(ai_name: str) -> Path:
    """Get context file path for an AI in current project"""
    project_id = get_project_id()
    project_dir = CONTEXT_DIR / project_id
    project_dir.mkdir(exist_ok=True)
    return project_dir / f"{ai_name}_context.json"

def load_context(ai_name: str) -> List[Dict[str, str]]:
    """Load conversation context for an AI"""
    context_path = get_context_path(ai_name)
    if context_path.exists():
        try:
            with open(context_path, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_context(ai_name: str, context: List[Dict[str, str]]):
    """Save conversation context for an AI"""
    context_path = get_context_path(ai_name)
    # Keep only last 20 messages to prevent huge files
    if len(context) > 20:
        context = context[-20:]
    with open(context_path, 'w') as f:
        json.dump(context, f, indent=2)

def clear_context(ai_name: str):
    """Clear context for an AI"""
    context_path = get_context_path(ai_name)
    if context_path.exists():
        context_path.unlink()

# Load API credentials
def load_credentials() -> Dict[str, str]:
    """Load API keys from environment"""
    creds = {}
    if os.getenv("GEMINI_API_KEY"):
        creds["gemini"] = os.getenv("GEMINI_API_KEY")
    if os.getenv("GROK_API_KEY"):
        creds["grok"] = os.getenv("GROK_API_KEY")
    if os.getenv("OPENAI_API_KEY"):
        creds["openai"] = os.getenv("OPENAI_API_KEY")
    return creds

CREDENTIALS = load_credentials()

# Initialize AI clients if credentials exist
AI_CLIENTS = {}

if CREDENTIALS.get("gemini"):
    try:
        import google.generativeai as genai
        genai.configure(api_key=CREDENTIALS["gemini"])
        AI_CLIENTS["gemini"] = genai
    except Exception as e:
        print(f"Gemini init failed: {e}", file=sys.stderr)

if CREDENTIALS.get("grok") or CREDENTIALS.get("openai"):
    try:
        from openai import OpenAI
        if CREDENTIALS.get("grok"):
            AI_CLIENTS["grok"] = OpenAI(
                api_key=CREDENTIALS["grok"],
                base_url="https://api.x.ai/v1"
            )
        if CREDENTIALS.get("openai"):
            AI_CLIENTS["openai"] = OpenAI(api_key=CREDENTIALS["openai"])
    except Exception as e:
        print(f"OpenAI client init failed: {e}", file=sys.stderr)

def call_ai_with_context(ai_name: str, prompt: str, temperature: float = 0.7) -> str:
    """Call AI with injected context"""
    if ai_name not in AI_CLIENTS:
        return f"Error: {ai_name} not configured. Set {ai_name.upper()}_API_KEY"
    
    # Load context
    context = load_context(ai_name)
    
    try:
        if ai_name == "gemini":
            # Build prompt with context for Gemini
            full_prompt = ""
            if context:
                full_prompt = "Previous conversation:\n"
                for msg in context[-5:]:  # Last 5 exchanges
                    full_prompt += f"{msg['role']}: {msg['content']}\n"
                full_prompt += f"\nCurrent question: {prompt}"
            else:
                full_prompt = prompt
            
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            model = AI_CLIENTS["gemini"].GenerativeModel(model_name)
            response = model.generate_content(
                full_prompt,
                generation_config={"temperature": temperature}
            )
            result = response.text
            
        else:  # OpenAI-compatible (Grok, ChatGPT)
            # Build messages array
            messages = [
                {"role": "system", "content": f"You are {ai_name} with persistent memory. Remember our previous conversations."}
            ]
            
            # Add context
            for msg in context:
                messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Add current prompt
            messages.append({"role": "user", "content": prompt})
            
            if ai_name == "grok":
                model = os.getenv("GROK_MODEL", "grok-3")
            else:
                model = os.getenv("OPENAI_MODEL", "gpt-4o")
            response = AI_CLIENTS[ai_name].chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            result = response.choices[0].message.content
        
        # Save to context
        context.append({"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()})
        context.append({"role": "assistant", "content": result, "timestamp": datetime.now().isoformat()})
        save_context(ai_name, context)
        
        return result
        
    except Exception as e:
        return f"Error calling {ai_name}: {str(e)}"

def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP protocol request"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "0.1.0",
                "serverInfo": {
                    "name": "mcp-ai-collab",
                    "version": __version__
                },
                "capabilities": {
                    "tools": {"list": True}
                }
            }
        }
    
    elif method == "tools/list":
        tools = []
        
        # Add ask_* tools for each configured AI
        for ai_name in AI_CLIENTS:
            tools.append({
                "name": f"ask_{ai_name}",
                "description": f"Ask {ai_name.title()} (with persistent memory)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Your question or prompt"},
                        "temperature": {"type": "number", "default": 0.7, "description": "Response creativity (0-1)"}
                    },
                    "required": ["prompt"]
                }
            })
        
        # Add context management tools
        tools.extend([
            {
                "name": "show_context",
                "description": "Show conversation history for an AI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ai": {"type": "string", "enum": list(AI_CLIENTS.keys()), "description": "Which AI's context to show"}
                    },
                    "required": ["ai"]
                }
            },
            {
                "name": "clear_context",
                "description": "Clear conversation history",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ai": {"type": "string", "enum": list(AI_CLIENTS.keys()) + ["all"], "description": "Which AI's context to clear (or 'all')"}
                    },
                    "required": ["ai"]
                }
            }
        ])
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools}
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # Handle ask_* tools
        if tool_name.startswith("ask_"):
            ai_name = tool_name.replace("ask_", "")
            prompt = arguments.get("prompt")
            temperature = arguments.get("temperature", 0.7)
            
            result = call_ai_with_context(ai_name, prompt, temperature)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        
        # Handle show_context
        elif tool_name == "show_context":
            ai_name = arguments.get("ai")
            context = load_context(ai_name)
            
            if not context:
                text = f"No conversation history for {ai_name}"
            else:
                text = f"Recent conversation with {ai_name}:\n"
                for msg in context[-6:]:  # Last 3 exchanges
                    role = "You" if msg["role"] == "user" else ai_name.title()
                    text += f"\n{role}: {msg['content'][:100]}..."
                    if len(msg['content']) > 100:
                        text += " (truncated)"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        
        # Handle clear_context
        elif tool_name == "clear_context":
            ai_name = arguments.get("ai")
            
            if ai_name == "all":
                for ai in AI_CLIENTS:
                    clear_context(ai)
                text = "Cleared conversation history for all AIs"
            else:
                clear_context(ai_name)
                text = f"Cleared conversation history for {ai_name}"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Unknown method: {method}"
            }
        }

def main():
    """Main MCP server loop"""
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        print(f"MCP AI Collab Server v{__version__} - Test Mode", file=sys.stderr)
        print(f"Context directory: {CONTEXT_DIR}", file=sys.stderr)
        print(f"Project ID: {get_project_id()}", file=sys.stderr)
        print(f"Available AIs: {list(AI_CLIENTS.keys())}", file=sys.stderr)
        print("✓ Server test passed", file=sys.stderr)
        return
    
    print(f"MCP AI Collab Server v{__version__} starting...", file=sys.stderr)
    print(f"Context directory: {CONTEXT_DIR}", file=sys.stderr)
    print(f"Project ID: {get_project_id()}", file=sys.stderr)
    print(f"Available AIs: {list(AI_CLIENTS.keys())}", file=sys.stderr)
    
    while True:
        try:
            # Read line from stdin
            line = sys.stdin.readline()
            if not line:
                break
            
            # Parse JSON request
            try:
                request = json.loads(line.strip())
            except json.JSONDecodeError as e:
                error = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error), flush=True)
                continue
            
            # Handle request
            response = handle_request(request)
            
            # Send response
            print(json.dumps(response), flush=True)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)
            error = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error), flush=True)

if __name__ == "__main__":
    main()