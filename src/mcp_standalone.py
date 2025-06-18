#!/usr/bin/env python3
"""
MCP AI Collab - Standalone MCP Server with Context Persistence
Gives Gemini, Grok, ChatGPT persistent memory across conversations
"""

import sys
import json
import asyncio
import os
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import hashlib

# Simple file-based storage for immediate functionality
class SimpleContextStore:
    """File-based context storage - no Redis/PostgreSQL needed"""
    
    def __init__(self):
        self.base_dir = Path.home() / ".mcp-ai-collab" / "contexts"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_project_id(self, project_path: str) -> str:
        """Generate project ID from path"""
        return hashlib.md5(project_path.encode()).hexdigest()[:8]
    
    def _get_context_file(self, ai_name: str, project_path: str) -> Path:
        """Get context file path for AI and project"""
        project_id = self._get_project_id(project_path)
        return self.base_dir / project_id / f"{ai_name}_context.json"
    
    async def get_context(self, ai_name: str, project_path: str) -> List[Dict]:
        """Get context for AI in project"""
        context_file = self._get_context_file(ai_name, project_path)
        if context_file.exists():
            try:
                with open(context_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    async def add_to_context(self, ai_name: str, project_path: str, 
                           role: str, content: str):
        """Add message to context"""
        context_file = self._get_context_file(ai_name, project_path)
        context_file.parent.mkdir(parents=True, exist_ok=True)
        
        context = await self.get_context(ai_name, project_path)
        context.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep last 20 messages
        if len(context) > 20:
            context = context[-20:]
        
        with open(context_file, 'w') as f:
            json.dump(context, f, indent=2)
    
    async def clear_context(self, ai_name: str, project_path: str):
        """Clear context for AI"""
        context_file = self._get_context_file(ai_name, project_path)
        if context_file.exists():
            context_file.unlink()

class MCPAICollab:
    """Standalone MCP server with context persistence"""
    
    def __init__(self):
        self.context_store = SimpleContextStore()
        self.project_path = os.getcwd()
        
        # Load API keys from environment
        self.api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY", ""),
            "grok": os.getenv("GROK_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", "")
        }
        
        # API endpoints
        self.endpoints = {
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "grok": "https://api.x.ai/v1/chat/completions",
            "openai": "https://api.openai.com/v1/chat/completions",
            "deepseek": "https://api.deepseek.com/chat/completions"
        }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request"""
        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})
        
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "0.1.0",
                        "serverInfo": {
                            "name": "mcp-ai-collab",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": {"list": True}
                        }
                    }
                }
            
            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "ask_gemini",
                                "description": "Ask Gemini (with context memory)",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "temperature": {"type": "number", "default": 0.7}
                                    },
                                    "required": ["prompt"]
                                }
                            },
                            {
                                "name": "ask_grok",
                                "description": "Ask Grok (with context memory)",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "temperature": {"type": "number", "default": 0.7}
                                    },
                                    "required": ["prompt"]
                                }
                            },
                            {
                                "name": "ask_openai",
                                "description": "Ask ChatGPT (with context memory)",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "temperature": {"type": "number", "default": 0.7}
                                    },
                                    "required": ["prompt"]
                                }
                            },
                            {
                                "name": "clear_ai_context",
                                "description": "Clear context for specific AI",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "ai": {"type": "string", "enum": ["gemini", "grok", "openai", "all"]}
                                    },
                                    "required": ["ai"]
                                }
                            },
                            {
                                "name": "show_ai_context",
                                "description": "Show context for specific AI",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "ai": {"type": "string", "enum": ["gemini", "grok", "openai"]}
                                    },
                                    "required": ["ai"]
                                }
                            }
                        ]
                    }
                }
            
            elif method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                
                if tool_name in ["ask_gemini", "ask_grok", "ask_openai"]:
                    ai_name = tool_name.replace("ask_", "")
                    prompt = args.get("prompt")
                    temperature = args.get("temperature", 0.7)
                    
                    # Get context
                    context = await self.context_store.get_context(ai_name, self.project_path)
                    
                    # Call AI with context
                    response = await self._call_ai_with_context(
                        ai_name, prompt, context, temperature
                    )
                    
                    # Store in context
                    await self.context_store.add_to_context(
                        ai_name, self.project_path, "user", prompt
                    )
                    await self.context_store.add_to_context(
                        ai_name, self.project_path, "assistant", response
                    )
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": response}]
                        }
                    }
                
                elif tool_name == "clear_ai_context":
                    ai = args.get("ai")
                    if ai == "all":
                        for ai_name in ["gemini", "grok", "openai"]:
                            await self.context_store.clear_context(ai_name, self.project_path)
                        message = "Cleared context for all AIs"
                    else:
                        await self.context_store.clear_context(ai, self.project_path)
                        message = f"Cleared context for {ai}"
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": message}]
                        }
                    }
                
                elif tool_name == "show_ai_context":
                    ai = args.get("ai")
                    context = await self.context_store.get_context(ai, self.project_path)
                    
                    if not context:
                        text = f"No context stored for {ai}"
                    else:
                        text = f"Context for {ai}:\n"
                        for msg in context[-5:]:  # Show last 5 messages
                            text += f"\n{msg['role']}: {msg['content'][:100]}..."
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": text}]
                        }
                    }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
    
    async def _call_ai_with_context(self, ai_name: str, prompt: str, 
                                  context: List[Dict], temperature: float) -> str:
        """Call AI with injected context"""
        api_key = self.api_keys.get(ai_name)
        if not api_key:
            return f"API key not found for {ai_name}. Please set {ai_name.upper()}_API_KEY"
        
        # Build messages with context
        messages = []
        
        # Add system message
        messages.append({
            "role": "system",
            "content": f"You are {ai_name} with persistent memory. You remember all previous conversations in this project."
        })
        
        # Add context
        for msg in context:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            async with aiohttp.ClientSession() as session:
                if ai_name == "gemini":
                    # Gemini API format
                    url = f"{self.endpoints['gemini']}?key={api_key}"
                    data = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": temperature}
                    }
                    
                    # Include context in prompt for Gemini
                    if context:
                        context_text = "\n".join([
                            f"{msg['role']}: {msg['content']}" 
                            for msg in context[-5:]
                        ])
                        data["contents"][0]["parts"][0]["text"] = (
                            f"Previous conversation:\n{context_text}\n\nCurrent question: {prompt}"
                        )
                    
                    async with session.post(url, json=data) as resp:
                        result = await resp.json()
                        return result["candidates"][0]["content"]["parts"][0]["text"]
                
                else:
                    # OpenAI-compatible format (Grok, ChatGPT, DeepSeek)
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    data = {
                        "model": {
                            "grok": "grok-3",
                            "openai": "gpt-4o-mini",
                            "deepseek": "deepseek-chat"
                        }.get(ai_name),
                        "messages": messages,
                        "temperature": temperature
                    }
                    
                    async with session.post(
                        self.endpoints[ai_name], 
                        headers=headers, 
                        json=data
                    ) as resp:
                        result = await resp.json()
                        return result["choices"][0]["message"]["content"]
                        
        except Exception as e:
            return f"Error calling {ai_name}: {str(e)}"
    
    async def run(self):
        """Main stdio loop"""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                request = json.loads(line.strip())
                response = await self.handle_request(request)
                
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        server = MCPAICollab()
        asyncio.run(server.run())
    else:
        print("MCP AI Collab - Standalone Server with Context Memory")
        print("Usage: python mcp_standalone.py --stdio")
        sys.exit(1)

if __name__ == "__main__":
    main()