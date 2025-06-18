#!/usr/bin/env python3
"""
MCP SSE Server - Dedicated SSE implementation cho Claude Code
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleContextStore:
    """Simple file-based context storage"""
    
    def __init__(self):
        self.contexts = {}
        
    async def get_context(self, session_id: str) -> list:
        return self.contexts.get(session_id, [])
    
    async def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.contexts:
            self.contexts[session_id] = []
        
        self.contexts[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 20 messages
        if len(self.contexts[session_id]) > 20:
            self.contexts[session_id] = self.contexts[session_id][-20:]
    
    async def clear_context(self, session_id: str):
        if session_id in self.contexts:
            del self.contexts[session_id]

class MCPSSEServer:
    """MCP Server với SSE support cho Claude Code"""
    
    def __init__(self):
        self.app = FastAPI(title="MCP SSE Server", version="1.0.0")
        self.setup_middleware()
        self.setup_routes()
        
        # Simple context storage
        self.context_store = SimpleContextStore()
        
        # Client management
        self.active_clients: Dict[str, Any] = {}
        
        # Load API keys
        self.api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY", ""),
            "grok": os.getenv("GROK_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
        }
        
        logger.info(f"API Keys loaded: {[k for k, v in self.api_keys.items() if v]}")
    
    def setup_middleware(self):
        """Setup CORS middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Setup SSE routes"""
        
        @self.app.get("/")
        async def root():
            return {
                "name": "MCP SSE Server",
                "version": "1.0.0",
                "transport": "sse",
                "status": "running",
                "endpoints": {
                    "sse": "/sse",
                    "message": "/message"
                },
                "active_clients": len(self.active_clients),
                "configured_ais": [k for k, v in self.api_keys.items() if v]
            }
        
        @self.app.get("/sse")
        async def sse_stream(request: Request):
            """Main SSE endpoint cho MCP communication"""
            return StreamingResponse(
                self.sse_generator(request),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",  
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )
        
        @self.app.post("/message")
        async def handle_message(request: Request):
            """Handle incoming MCP messages"""
            try:
                data = await request.json()
                logger.info(f"Received MCP message: {data.get('method', 'unknown')}")
                
                response = await self.process_mcp_message(data)
                return response
                
            except Exception as e:
                logger.error(f"Message handling error: {str(e)}")
                return {
                    "jsonrpc": "2.0",
                    "id": data.get("id") if 'data' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
    
    async def sse_generator(self, request: Request) -> AsyncGenerator[str, None]:
        """Generate SSE events"""
        client_id = str(uuid.uuid4())
        self.active_clients[client_id] = {
            "connected_at": datetime.utcnow(),
            "last_ping": datetime.utcnow()
        }
        
        logger.info(f"New SSE client connected: {client_id}")
        
        try:
            # Send connection established
            yield f"event: connected\n"
            yield f"data: {json.dumps({'client_id': client_id, 'status': 'connected'})}\n\n"
            
            # Send server capabilities
            capabilities = {
                "jsonrpc": "2.0",
                "method": "server/info",
                "params": {
                    "serverInfo": {
                        "name": "mcp-ai-collab-sse",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": True,
                        "context": True,
                        "notifications": True,
                        "streaming": True
                    },
                    "available_ais": [k for k, v in self.api_keys.items() if v]
                }
            }
            
            yield f"event: capabilities\n"
            yield f"data: {json.dumps(capabilities)}\n\n"
            
            # Keep connection alive
            while True:
                if await request.is_disconnected():
                    logger.info(f"Client {client_id} disconnected")
                    break
                
                # Send periodic ping
                ping_data = {
                    "jsonrpc": "2.0",
                    "method": "ping",
                    "params": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "client_id": client_id
                    }
                }
                
                yield f"event: ping\n"
                yield f"data: {json.dumps(ping_data)}\n\n"
                
                # Update last ping
                self.active_clients[client_id]["last_ping"] = datetime.utcnow()
                
                await asyncio.sleep(30)  # Ping every 30 seconds
                
        except Exception as e:
            logger.error(f"SSE error for client {client_id}: {str(e)}")
        finally:
            # Cleanup
            if client_id in self.active_clients:
                del self.active_clients[client_id]
            logger.info(f"SSE client {client_id} cleaned up")
    
    async def process_mcp_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming MCP message"""
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "1.0",
                        "serverInfo": {
                            "name": "mcp-ai-collab-sse", 
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "tools": True,
                            "context": True,
                            "notifications": True
                        }
                    }
                }
            
            elif method == "tools/list":
                tools = []
                
                # Add tools for each configured AI
                for ai_name, api_key in self.api_keys.items():
                    if api_key:
                        tools.append({
                            "name": f"ask_{ai_name}",
                            "description": f"Ask {ai_name.title()} with persistent context memory",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {
                                        "type": "string", 
                                        "description": "Your question or request"
                                    },
                                    "temperature": {
                                        "type": "number", 
                                        "default": 0.7,
                                        "description": "Response creativity (0-1)"
                                    }
                                },
                                "required": ["prompt"]
                            }
                        })
                
                # Add utility tools
                tools.extend([
                    {
                        "name": "clear_context",
                        "description": "Clear conversation context for an AI",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ai": {
                                    "type": "string",
                                    "enum": list(self.api_keys.keys()) + ["all"],
                                    "description": "Which AI to clear (or 'all')"
                                }
                            },
                            "required": ["ai"]
                        }
                    },
                    {
                        "name": "show_context",
                        "description": "Show current context for an AI",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "ai": {
                                    "type": "string",
                                    "enum": list(self.api_keys.keys()),
                                    "description": "Which AI's context to show"
                                }
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
                
                # Handle AI calls
                if tool_name.startswith("ask_"):
                    ai_name = tool_name.replace("ask_", "")
                    return await self.handle_ai_call(ai_name, arguments, request_id)
                
                # Handle utility calls
                elif tool_name == "clear_context":
                    return await self.handle_clear_context(arguments, request_id)
                
                elif tool_name == "show_context":
                    return await self.handle_show_context(arguments, request_id)
                
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
                
        except Exception as e:
            logger.error(f"MCP processing error: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def handle_ai_call(self, ai_name: str, arguments: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle AI tool calls with context"""
        prompt = arguments.get("prompt", "")
        temperature = arguments.get("temperature", 0.7)
        
        if not self.api_keys.get(ai_name):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32600,
                    "message": f"{ai_name.upper()}_API_KEY not configured"
                }
            }
        
        # Get project-based session ID (simple approach)
        session_id = f"project_default_{ai_name}"
        
        # Get existing context
        context = await self.context_store.get_context(session_id)
        
        # Call AI with context (placeholder - you'll implement actual AI calls)
        response_text = f"Mock response from {ai_name.upper()}: {prompt[:50]}... (with {len(context)} previous messages)"
        
        # Store conversation
        await self.context_store.add_message(session_id, "user", prompt)
        await self.context_store.add_message(session_id, "assistant", response_text)
        
        return {
            "jsonrpc": "2.0", 
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": response_text}],
                "metadata": {
                    "ai": ai_name,
                    "context_messages": len(context) + 2,
                    "session_id": session_id
                }
            }
        }
    
    async def handle_clear_context(self, arguments: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle context clearing"""
        ai = arguments.get("ai", "all")
        
        if ai == "all":
            # Clear all contexts
            self.context_store.contexts.clear()
            message = "Cleared context for all AIs"
        else:
            session_id = f"project_default_{ai}"
            await self.context_store.clear_context(session_id)
            message = f"Cleared context for {ai.upper()}"
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": message}]
            }
        }
    
    async def handle_show_context(self, arguments: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle context display"""
        ai = arguments.get("ai")
        session_id = f"project_default_{ai}"
        
        context = await self.context_store.get_context(session_id)
        
        if not context:
            text = f"No context stored for {ai.upper()}"
        else:
            text = f"Context for {ai.upper()} ({len(context)} messages):\n\n"
            for msg in context[-5:]:  # Show last 5 messages
                role = "You" if msg["role"] == "user" else ai.upper()
                content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                text += f"{role}: {content}\n\n"
        
        return {
            "jsonrpc": "2.0",
            "id": request_id, 
            "result": {
                "content": [{"type": "text", "text": text}]
            }
        }

def main():
    """Main entry point"""
    
    # Basic setup
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8001))
    
    logger.info(f"Starting MCP SSE Server on {host}:{port}")
    
    server = MCPSSEServer()
    
    # Start server
    config = uvicorn.Config(
        server.app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
    
    uvicorn_server = uvicorn.Server(config)
    asyncio.run(uvicorn_server.serve())

if __name__ == "__main__":
    main()