#!/usr/bin/env python3
"""
MCP AI Collab - Full Implementation with Redis + PostgreSQL
Gives AI assistants persistent memory with proper database storage
"""

import json
import sys
import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import hashlib
from datetime import datetime
import asyncio
import redis
import asyncpg
from contextlib import asynccontextmanager

# Ensure unbuffered output - CRITICAL for MCP
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 1)

# Server info
__version__ = "2.0.0"

class DatabaseManager:
    """Manages Redis and PostgreSQL connections"""
    
    def __init__(self):
        self.redis_client = None
        self.pg_pool = None
        self.initialized = False
        
    async def initialize(self):
        """Initialize database connections"""
        if self.initialized:
            return
            
        try:
            # Connect to Redis
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await asyncio.to_thread(self.redis_client.ping)
            print("Redis connected", file=sys.stderr)
            
            # Connect to PostgreSQL
            self.pg_pool = await asyncpg.create_pool(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', 5432)),
                user=os.getenv('POSTGRES_USER', 'mcp_user'),
                password=os.getenv('POSTGRES_PASSWORD', 'mcp_password'),
                database=os.getenv('POSTGRES_DB', 'mcp_dev'),
                min_size=1,
                max_size=5
            )
            
            # Create tables if needed
            async with self.pg_pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS ai_sessions (
                        id SERIAL PRIMARY KEY,
                        project_id VARCHAR(32) NOT NULL,
                        ai_name VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(project_id, ai_name)
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS ai_messages (
                        id SERIAL PRIMARY KEY,
                        session_id INTEGER REFERENCES ai_sessions(id) ON DELETE CASCADE,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        tokens INTEGER DEFAULT 0
                    )
                ''')
                
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_messages_session 
                    ON ai_messages(session_id)
                ''')
                
            print("PostgreSQL connected and tables created", file=sys.stderr)
            self.initialized = True
            
        except Exception as e:
            print(f"Database initialization error: {e}", file=sys.stderr)
            # Continue without databases - fallback to memory
            self.initialized = True
    
    async def get_or_create_session(self, project_id: str, ai_name: str) -> int:
        """Get or create a session for an AI in a project"""
        async with self.pg_pool.acquire() as conn:
            # Try to get existing session
            row = await conn.fetchrow('''
                SELECT id FROM ai_sessions 
                WHERE project_id = $1 AND ai_name = $2
            ''', project_id, ai_name)
            
            if row:
                # Update last accessed time
                await conn.execute('''
                    UPDATE ai_sessions 
                    SET updated_at = CURRENT_TIMESTAMP 
                    WHERE id = $1
                ''', row['id'])
                return row['id']
            
            # Create new session
            row = await conn.fetchrow('''
                INSERT INTO ai_sessions (project_id, ai_name) 
                VALUES ($1, $2) 
                RETURNING id
            ''', project_id, ai_name)
            return row['id']
    
    async def add_message(self, session_id: int, role: str, content: str):
        """Add a message to the conversation history"""
        async with self.pg_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO ai_messages (session_id, role, content, tokens) 
                VALUES ($1, $2, $3, $4)
            ''', session_id, role, content, len(content.split()))
            
        # Also cache in Redis for fast access
        cache_key = f"session:{session_id}:latest"
        await asyncio.to_thread(
            self.redis_client.lpush, 
            cache_key, 
            json.dumps({"role": role, "content": content})
        )
        # Keep only last 10 messages in cache
        await asyncio.to_thread(self.redis_client.ltrim, cache_key, 0, 9)
        # Expire after 1 hour
        await asyncio.to_thread(self.redis_client.expire, cache_key, 3600)
    
    async def get_context(self, session_id: int, limit: int = 20) -> List[Dict]:
        """Get conversation context from cache or database"""
        # Try Redis cache first
        cache_key = f"session:{session_id}:latest"
        cached = await asyncio.to_thread(
            self.redis_client.lrange, cache_key, 0, -1
        )
        
        if cached:
            # Return cached messages (they're in reverse order)
            messages = [json.loads(msg) for msg in reversed(cached)]
            return messages
        
        # Fallback to PostgreSQL
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT role, content, timestamp 
                FROM ai_messages 
                WHERE session_id = $1 
                ORDER BY timestamp DESC 
                LIMIT $2
            ''', session_id, limit)
            
            # Return in chronological order
            return [
                {
                    "role": row['role'],
                    "content": row['content'],
                    "timestamp": row['timestamp'].isoformat()
                }
                for row in reversed(rows)
            ]
    
    async def clear_session(self, project_id: str, ai_name: str):
        """Clear all messages for a session"""
        async with self.pg_pool.acquire() as conn:
            # Get session ID
            row = await conn.fetchrow('''
                SELECT id FROM ai_sessions 
                WHERE project_id = $1 AND ai_name = $2
            ''', project_id, ai_name)
            
            if row:
                session_id = row['id']
                # Delete all messages
                await conn.execute('''
                    DELETE FROM ai_messages WHERE session_id = $1
                ''', session_id)
                
                # Clear Redis cache
                cache_key = f"session:{session_id}:latest"
                await asyncio.to_thread(self.redis_client.delete, cache_key)
    
    async def cleanup(self):
        """Cleanup database connections"""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis_client:
            self.redis_client.close()

# Global database manager
db_manager = DatabaseManager()

def get_project_id() -> str:
    """Generate project ID from current working directory"""
    cwd = os.getcwd()
    return hashlib.md5(cwd.encode()).hexdigest()[:8]

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

# Initialize AI clients
AI_CLIENTS = {}

if CREDENTIALS.get("gemini"):
    try:
        from google import genai
        AI_CLIENTS["gemini"] = genai.Client(api_key=CREDENTIALS["gemini"])
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

async def call_ai_with_context(ai_name: str, prompt: str, temperature: float = 0.7) -> str:
    """Call AI with database-backed context"""
    if ai_name not in AI_CLIENTS:
        return f"Error: {ai_name} not configured. Set {ai_name.upper()}_API_KEY"
    
    project_id = get_project_id()
    
    # Get or create session
    session_id = await db_manager.get_or_create_session(project_id, ai_name)
    
    # Get context from database
    context = await db_manager.get_context(session_id)
    
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
            
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-preview-06-05")
            response = AI_CLIENTS["gemini"].models.generate_content(
                model=model_name,
                contents=full_prompt,
                config={"temperature": temperature}
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
        
        # Save to database
        await db_manager.add_message(session_id, "user", prompt)
        await db_manager.add_message(session_id, "assistant", result)
        
        return result
        
    except Exception as e:
        return f"Error calling {ai_name}: {str(e)}"

async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP protocol request"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
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
                "description": f"Ask {ai_name.title()} (with Redis/PostgreSQL memory)",
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
            },
            {
                "name": "db_status",
                "description": "Check database connection status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
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
            
            result = await call_ai_with_context(ai_name, prompt, temperature)
            
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
            project_id = get_project_id()
            
            try:
                session_id = await db_manager.get_or_create_session(project_id, ai_name)
                context = await db_manager.get_context(session_id, limit=10)
                
                if not context:
                    text = f"No conversation history for {ai_name}"
                else:
                    text = f"Recent conversation with {ai_name} (from PostgreSQL):\n"
                    for msg in context[-6:]:  # Last 3 exchanges
                        role = "You" if msg["role"] == "user" else ai_name.title()
                        text += f"\n{role}: {msg['content'][:100]}..."
                        if len(msg['content']) > 100:
                            text += " (truncated)"
                
            except Exception as e:
                text = f"Error loading context: {str(e)}"
            
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
            project_id = get_project_id()
            
            try:
                if ai_name == "all":
                    for ai in AI_CLIENTS:
                        await db_manager.clear_session(project_id, ai)
                    text = "Cleared conversation history for all AIs (from PostgreSQL)"
                else:
                    await db_manager.clear_session(project_id, ai_name)
                    text = f"Cleared conversation history for {ai_name} (from PostgreSQL)"
            except Exception as e:
                text = f"Error clearing context: {str(e)}"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                }
            }
        
        # Handle db_status
        elif tool_name == "db_status":
            status = "Database Status:\n"
            
            # Check Redis
            try:
                await asyncio.to_thread(db_manager.redis_client.ping)
                status += "✓ Redis: Connected\n"
            except:
                status += "✗ Redis: Not connected\n"
            
            # Check PostgreSQL
            try:
                async with db_manager.pg_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                status += "✓ PostgreSQL: Connected\n"
                
                # Get session count
                async with db_manager.pg_pool.acquire() as conn:
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM ai_sessions WHERE project_id = $1",
                        get_project_id()
                    )
                    status += f"  Sessions for this project: {count}\n"
                    
                    msg_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM ai_messages"
                    )
                    status += f"  Total messages: {msg_count}"
            except Exception as e:
                status += f"✗ PostgreSQL: Error - {str(e)}"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": status}]
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

async def main_async():
    """Async main loop"""
    # Initialize database connections
    await db_manager.initialize()
    
    print(f"MCP AI Collab Server v{__version__} starting...", file=sys.stderr)
    print(f"Project ID: {get_project_id()}", file=sys.stderr)
    print(f"Available AIs: {list(AI_CLIENTS.keys())}", file=sys.stderr)
    
    loop = asyncio.get_event_loop()
    
    while True:
        try:
            # Read line from stdin (in thread to not block)
            line = await loop.run_in_executor(None, sys.stdin.readline)
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
            response = await handle_request(request)
            
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
    
    # Cleanup
    await db_manager.cleanup()

def main():
    """Main entry point"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()