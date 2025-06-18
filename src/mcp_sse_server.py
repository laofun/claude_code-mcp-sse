#!/usr/bin/env python3
"""
MCP SSE Server - Enhanced SSE implementation with Redis + PostgreSQL
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, AsyncGenerator, Optional
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import redis.asyncio as redis
import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages Redis and PostgreSQL connections"""
    
    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Redis connection
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            self.redis_client = await redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info(f"✅ Redis connected: {redis_url}")
            
            # PostgreSQL connection from environment
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise ValueError("DATABASE_URL environment variable not set")
            
            self.pg_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
            logger.info(f"✅ PostgreSQL connected: {db_url.split('@')[1] if '@' in db_url else 'configured'}")
            
            # Create tables
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables if not exist"""
        async with self.pg_pool.acquire() as conn:
            # Conversations table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id UUID PRIMARY KEY,
                    user_id TEXT,
                    ai_type TEXT DEFAULT 'general',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES conversations(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # SSE connections table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sse_connections (
                    client_id UUID PRIMARY KEY,
                    session_id UUID,
                    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'
                )
            """)
            
            logger.info("📊 Database tables created/verified")
    
    async def cleanup(self):
        """Cleanup database connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.pg_pool:
            await self.pg_pool.close()

class EnhancedContextStore:
    """Enhanced context storage with Redis cache + PostgreSQL persistence"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.cache_ttl = 3600  # 1 hour
        
    async def get_context(self, session_id: str, ai_type: str = "general") -> list:
        """Get conversation context with Redis cache fallback to PostgreSQL"""
        cache_key = f"context:{session_id}:{ai_type}"
        
        try:
            # Try Redis cache first
            cached = await self.db.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Fallback to PostgreSQL
            async with self.db.pg_pool.acquire() as conn:
                messages = await conn.fetch("""
                    SELECT role, content, metadata, created_at
                    FROM messages m
                    JOIN conversations c ON m.session_id = c.session_id
                    WHERE c.session_id = $1 AND c.ai_type = $2
                    ORDER BY m.created_at DESC
                    LIMIT 50
                """, uuid.UUID(session_id), ai_type)
                
                context = [
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "metadata": msg["metadata"],
                        "timestamp": msg["created_at"].isoformat()
                    }
                    for msg in reversed(messages)  # Reverse to get chronological order
                ]
                
                # Cache in Redis
                await self.db.redis_client.setex(cache_key, self.cache_ttl, json.dumps(context))
                return context
                
        except Exception as e:
            logger.error(f"Error getting context for {session_id}: {e}")
            return []
    
    async def add_message(self, session_id: str, role: str, content: str, ai_type: str = "general", metadata: dict = None):
        """Add message to context with persistence"""
        if metadata is None:
            metadata = {}
            
        try:
            session_uuid = uuid.UUID(session_id)
            
            async with self.db.pg_pool.acquire() as conn:
                # Ensure conversation exists
                await conn.execute("""
                    INSERT INTO conversations (session_id, ai_type, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (session_id) DO UPDATE SET
                        updated_at = CURRENT_TIMESTAMP
                """, session_uuid, ai_type)
                
                # Add message
                await conn.execute("""
                    INSERT INTO messages (session_id, role, content, metadata)
                    VALUES ($1, $2, $3, $4)
                """, session_uuid, role, content, json.dumps(metadata))
            
            # Invalidate cache
            cache_key = f"context:{session_id}:{ai_type}"
            await self.db.redis_client.delete(cache_key)
            
            logger.info(f"💬 Message added: {session_id}/{ai_type} - {role}")
            
        except Exception as e:
            logger.error(f"Error adding message to {session_id}: {e}")
    
    async def clear_context(self, session_id: str, ai_type: str = "general"):
        """Clear conversation context"""
        try:
            session_uuid = uuid.UUID(session_id)
            
            async with self.db.pg_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM conversations WHERE session_id = $1 AND ai_type = $2
                """, session_uuid, ai_type)
            
            # Clear cache
            cache_key = f"context:{session_id}:{ai_type}"
            await self.db.redis_client.delete(cache_key)
            
            logger.info(f"🗑️ Context cleared: {session_id}/{ai_type}")
            
        except Exception as e:
            logger.error(f"Error clearing context for {session_id}: {e}")

class MCPSSEServer:
    """Enhanced MCP Server with SSE support and database persistence"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.context_store = None  # Will be initialized after DB
        self.active_clients: Dict[str, Any] = {}
        
        # Load API keys
        self.api_keys = {
            "gemini": os.getenv("GEMINI_API_KEY", ""),
            "grok": os.getenv("GROK_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        }
        
        logger.info(f"🔑 API Keys loaded: {[k for k, v in self.api_keys.items() if v]}")
        
        # Create FastAPI app with lifespan
        self.app = FastAPI(
            title="MCP SSE Server Enhanced", 
            version="2.0.0",
            lifespan=self.lifespan
        )
        self.setup_middleware()
        self.setup_routes()
    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Manage application lifespan - startup and shutdown"""
        # Startup
        await self.startup()
        yield
        # Shutdown
        await self.shutdown()
    
    async def startup(self):
        """Initialize database connections and context store"""
        try:
            await self.db_manager.initialize()
            self.context_store = EnhancedContextStore(self.db_manager)
            logger.info("🚀 Enhanced SSE Server initialized successfully")
        except Exception as e:
            logger.error(f"❌ Startup failed: {e}")
            raise
    
    async def shutdown(self):
        """Cleanup database connections"""
        try:
            await self.db_manager.cleanup()
            logger.info("🛑 SSE Server shutdown complete")
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")
    
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
        
        # Add missing MCP dynamic registration endpoints
        @self.app.post("/register")
        async def mcp_register(request: Request):
            """OAuth dynamic client registration endpoint"""
            try:
                client_data = await request.json()
                client_id = str(uuid.uuid4())
                client_secret = str(uuid.uuid4())
                
                # Store client registration (simplified)
                logger.info(f"🔐 Client registered: {client_id}")
                
                return {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "client_id_issued_at": int(datetime.now().timestamp()),
                    "client_secret_expires_at": 0,  # Never expires
                    "registration_client_uri": f"/clients/{client_id}",
                    "registration_access_token": str(uuid.uuid4()),
                    "grant_types": ["authorization_code"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "client_secret_basic"
                }
            except Exception as e:
                logger.error(f"Registration error: {e}")
                return {
                    "error": "invalid_request",
                    "error_description": str(e)
                }
        
        @self.app.get("/.well-known/mcp-server")
        async def mcp_server_metadata():
            """MCP server discovery metadata"""
            return {
                "name": "mcp-sse-server-enhanced",
                "version": "2.0.0",
                "description": "Enhanced MCP SSE Server with Redis + PostgreSQL",
                "transport": {
                    "type": "sse",
                    "url": "/sse"
                },
                "capabilities": {
                    "tools": True,
                    "context": True,
                    "notifications": True,
                    "streaming": True,
                    "sse": True
                }
            }
        
        @self.app.get("/.well-known/oauth-authorization-server")
        async def oauth_metadata():
            """OAuth metadata endpoint (for MCP compatibility)"""
            return {
                "issuer": "mcp-sse-server",
                "authorization_endpoint": "/auth",
                "token_endpoint": "/token",
                "registration_endpoint": "/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_basic", "none"],
                "scopes_supported": ["read", "write"],
                "code_challenge_methods_supported": ["plain", "S256"],
                "registration_endpoint_supported": True,
                "dynamic_client_registration_supported": True
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
        """Handle AI tool calls with enhanced context and persistence"""
        prompt = arguments.get("prompt", "")
        temperature = arguments.get("temperature", 0.7)
        project_id = arguments.get("project_id", "default")
        
        if not self.api_keys.get(ai_name):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32600,
                    "message": f"{ai_name.upper()}_API_KEY not configured"
                }
            }
        
        # Generate session ID with project context
        session_id = str(uuid.uuid4()) if project_id == "default" else f"{project_id}_{ai_name}"
        
        try:
            # Get existing context from enhanced store
            context = await self.context_store.get_context(session_id, ai_name)
            
            # Enhanced mock response with more realistic simulation
            context_summary = f"Previous conversation: {len(context)} messages" if context else "New conversation"
            response_text = f"Enhanced {ai_name.upper()} response to: '{prompt[:100]}...' | {context_summary} | Temperature: {temperature}"
            
            # Store conversation with metadata
            await self.context_store.add_message(
                session_id, 
                "user", 
                prompt, 
                ai_name, 
                {"temperature": temperature, "project_id": project_id}
            )
            
            await self.context_store.add_message(
                session_id, 
                "assistant", 
                response_text, 
                ai_name,
                {"model": ai_name, "response_length": len(response_text)}
            )
            
            # Broadcast to connected SSE clients
            await self.broadcast_update({
                "type": "ai_response",
                "session_id": session_id,
                "ai": ai_name,
                "response": response_text,
                "context_size": len(context) + 2
            })
            
            logger.info(f"🤖 {ai_name.upper()} response generated for session {session_id}")
            
            return {
                "jsonrpc": "2.0", 
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": response_text}],
                    "metadata": {
                        "ai": ai_name,
                        "context_messages": len(context) + 2,
                        "session_id": session_id,
                        "project_id": project_id,
                        "enhanced": True
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in AI call {ai_name}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def broadcast_update(self, message: dict):
        """Broadcast update to all connected SSE clients"""
        if not self.active_clients:
            return
            
        # Store in Redis for other instances
        try:
            await self.db_manager.redis_client.publish("sse_updates", json.dumps(message))
            logger.debug(f"📡 Broadcasted update: {message.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
    
    async def handle_clear_context(self, arguments: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle enhanced context clearing"""
        ai = arguments.get("ai", "all")
        project_id = arguments.get("project_id", "default")
        
        try:
            if ai == "all":
                # Clear all contexts for project (simplified for demo)
                message = "Enhanced context clearing for all AIs"
                # In production, you'd iterate through all sessions
            else:
                session_id = f"{project_id}_{ai}" if project_id != "default" else str(uuid.uuid4())
                await self.context_store.clear_context(session_id, ai)
                message = f"Enhanced context cleared for {ai.upper()} (project: {project_id})"
            
            # Broadcast update
            await self.broadcast_update({
                "type": "context_cleared",
                "ai": ai,
                "project_id": project_id
            })
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": message}],
                    "metadata": {"enhanced": True, "project_id": project_id}
                }
            }
            
        except Exception as e:
            logger.error(f"Error clearing context: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error clearing context: {str(e)}"
                }
            }
    
    async def handle_show_context(self, arguments: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle enhanced context display"""
        ai = arguments.get("ai")
        project_id = arguments.get("project_id", "default")
        
        try:
            session_id = f"{project_id}_{ai}" if project_id != "default" else str(uuid.uuid4())
            context = await self.context_store.get_context(session_id, ai)
            
            if not context:
                text = f"No enhanced context stored for {ai.upper()} (project: {project_id})"
            else:
                text = f"Enhanced Context for {ai.upper()} - Project: {project_id}\n"
                text += f"Total messages: {len(context)}\n"
                text += f"Session ID: {session_id}\n\n"
                
                # Show last 5 messages with enhanced info
                recent_messages = context[-5:] if len(context) > 5 else context
                for i, msg in enumerate(recent_messages, 1):
                    role = "You" if msg["role"] == "user" else ai.upper()
                    content = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
                    timestamp = msg.get("timestamp", "N/A")
                    text += f"{i}. {role} ({timestamp[:19]}): {content}\n\n"
                
                if len(context) > 5:
                    text += f"... and {len(context) - 5} earlier messages"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id, 
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "metadata": {
                        "enhanced": True,
                        "ai": ai,
                        "project_id": project_id,
                        "session_id": session_id,
                        "message_count": len(context) if context else 0
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error showing context: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error showing context: {str(e)}"
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