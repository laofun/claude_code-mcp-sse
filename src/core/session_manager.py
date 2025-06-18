"""
Session Manager for project-based AI contexts
Each AI maintains separate context per project, similar to Claude Code
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Set
from pathlib import Path
import asyncio

from fastapi import WebSocket
import redis.asyncio as redis
import asyncpg

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ProjectSession:
    """Represents a session for a specific project and AI"""
    def __init__(self, project_id: str, ai_name: str, session_id: str):
        self.project_id = project_id
        self.ai_name = ai_name
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
        self.websocket: Optional[WebSocket] = None
        self.active = True


class SessionManager:
    """
    Manages project-based sessions for different AIs
    Key features:
    - Each AI has separate context per project
    - Project detection based on working directory
    - /clear command synchronization across AIs
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pg_pool: Optional[asyncpg.Pool] = None
        
        # In-memory session tracking
        self.active_sessions: Dict[str, ProjectSession] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        
        # AI names we support
        self.supported_ais = ["gemini", "grok", "openai", "deepseek"]
        
    async def initialize(self):
        """Initialize database connections and create tables"""
        try:
            # Initialize Redis
            self.redis_client = await redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("SessionManager: Redis connected")
            
            # Initialize PostgreSQL
            self.pg_pool = await asyncpg.create_pool(
                os.getenv("DATABASE_URL", "postgresql://mcp_user:mcp_password@localhost:5432/mcp_dev"),
                min_size=2,
                max_size=10
            )
            
            await self._create_tables()
            logger.info("SessionManager: PostgreSQL connected and tables created")
            
        except Exception as e:
            logger.error(f"SessionManager initialization failed: {str(e)}")
            raise
    
    async def _create_tables(self):
        """Create session management tables"""
        async with self.pg_pool.acquire() as conn:
            # Projects table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    project_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AI sessions per project
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_sessions (
                    session_id TEXT PRIMARY KEY,
                    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
                    ai_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cleared BOOLEAN DEFAULT FALSE,
                    UNIQUE(project_id, ai_name)
                )
            """)
            
            # Clear events for synchronization
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS clear_events (
                    id SERIAL PRIMARY KEY,
                    project_id TEXT REFERENCES projects(project_id) ON DELETE CASCADE,
                    ai_name TEXT,
                    cleared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cleared_by TEXT  -- which AI initiated the clear
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_sessions_project ON ai_sessions(project_id)
            """)
    
    def get_project_id(self, project_path: str) -> str:
        """
        Generate a unique project ID based on the project path
        This ensures same project always gets same ID
        """
        # Normalize the path
        normalized_path = os.path.abspath(project_path)
        
        # Create a hash of the path for consistent project ID
        project_id = hashlib.sha256(normalized_path.encode()).hexdigest()[:16]
        
        return project_id
    
    async def get_or_create_session(
        self, 
        ai_name: str, 
        project_path: str,
        create_if_missing: bool = True
    ) -> Optional[ProjectSession]:
        """
        Get or create a session for a specific AI and project
        Each AI gets its own context per project
        """
        if ai_name not in self.supported_ais:
            logger.warning(f"Unsupported AI: {ai_name}")
            return None
            
        project_id = self.get_project_id(project_path)
        session_key = f"{project_id}:{ai_name}"
        
        # Check active sessions
        if session_key in self.active_sessions:
            session = self.active_sessions[session_key]
            session.last_accessed = datetime.utcnow()
            return session
        
        # Check database
        async with self.pg_pool.acquire() as conn:
            # Ensure project exists
            project_name = os.path.basename(project_path)
            await conn.execute("""
                INSERT INTO projects (project_id, project_path, project_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id) 
                DO UPDATE SET last_accessed = CURRENT_TIMESTAMP
            """, project_id, project_path, project_name)
            
            # Get or create AI session
            row = await conn.fetchrow("""
                SELECT session_id, cleared FROM ai_sessions
                WHERE project_id = $1 AND ai_name = $2
            """, project_id, ai_name)
            
            if row and not row['cleared']:
                # Existing session found
                session_id = row['session_id']
            elif create_if_missing:
                # Create new session
                import uuid
                session_id = str(uuid.uuid4())
                
                await conn.execute("""
                    INSERT INTO ai_sessions (session_id, project_id, ai_name)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (project_id, ai_name) 
                    DO UPDATE SET 
                        session_id = $1,
                        last_accessed = CURRENT_TIMESTAMP,
                        cleared = FALSE
                """, session_id, project_id, ai_name)
            else:
                return None
        
        # Create session object
        session = ProjectSession(project_id, ai_name, session_id)
        self.active_sessions[session_key] = session
        
        logger.info(f"Session created for {ai_name} in project {project_name}")
        return session
    
    async def clear_ai_context(
        self, 
        ai_name: str, 
        project_path: str,
        cleared_by: str = "user"
    ):
        """
        Clear context for a specific AI in a project
        This is triggered when user uses /clear command
        """
        project_id = self.get_project_id(project_path)
        session_key = f"{project_id}:{ai_name}"
        
        # Remove from active sessions
        if session_key in self.active_sessions:
            del self.active_sessions[session_key]
        
        # Mark as cleared in database
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                UPDATE ai_sessions 
                SET cleared = TRUE, last_accessed = CURRENT_TIMESTAMP
                WHERE project_id = $1 AND ai_name = $2
            """, project_id, ai_name)
            
            # Record clear event
            await conn.execute("""
                INSERT INTO clear_events (project_id, ai_name, cleared_by)
                VALUES ($1, $2, $3)
            """, project_id, ai_name, cleared_by)
        
        # Clear from Redis cache
        await self.redis_client.delete(f"context:{project_id}:{ai_name}")
        
        logger.info(f"Cleared context for {ai_name} in project {project_id}")
    
    async def clear_all_ai_contexts(self, project_path: str):
        """
        Clear context for ALL AIs in a project
        This is triggered when user uses /clear in Claude
        """
        project_id = self.get_project_id(project_path)
        
        # Clear all AI sessions for this project
        for ai_name in self.supported_ais:
            await self.clear_ai_context(ai_name, project_path, cleared_by="claude_clear_command")
        
        # Remove all active sessions for this project
        keys_to_remove = [
            key for key in self.active_sessions.keys() 
            if key.startswith(f"{project_id}:")
        ]
        for key in keys_to_remove:
            del self.active_sessions[key]
        
        logger.info(f"Cleared all AI contexts for project {project_id}")
    
    async def get_active_ais_for_project(self, project_path: str) -> List[str]:
        """Get list of AIs that have active sessions for a project"""
        project_id = self.get_project_id(project_path)
        
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT ai_name FROM ai_sessions
                WHERE project_id = $1 AND NOT cleared
                ORDER BY last_accessed DESC
            """, project_id)
            
        return [row['ai_name'] for row in rows]
    
    async def get_project_info(self, project_path: str) -> Optional[Dict]:
        """Get project information and statistics"""
        project_id = self.get_project_id(project_path)
        
        async with self.pg_pool.acquire() as conn:
            # Get project info
            project = await conn.fetchrow("""
                SELECT * FROM projects WHERE project_id = $1
            """, project_id)
            
            if not project:
                return None
            
            # Get AI session stats
            ai_stats = await conn.fetch("""
                SELECT 
                    ai_name,
                    COUNT(*) as total_sessions,
                    MAX(last_accessed) as last_active,
                    SUM(CASE WHEN cleared THEN 0 ELSE 1 END) as active_sessions
                FROM ai_sessions
                WHERE project_id = $1
                GROUP BY ai_name
            """, project_id)
            
            # Get clear events
            clear_count = await conn.fetchval("""
                SELECT COUNT(*) FROM clear_events
                WHERE project_id = $1
            """, project_id)
            
        return {
            "project_id": project_id,
            "project_path": project['project_path'],
            "project_name": project['project_name'],
            "created_at": project['created_at'],
            "last_accessed": project['last_accessed'],
            "ai_sessions": [
                {
                    "ai_name": stat['ai_name'],
                    "total_sessions": stat['total_sessions'],
                    "active_sessions": stat['active_sessions'],
                    "last_active": stat['last_active']
                }
                for stat in ai_stats
            ],
            "total_clears": clear_count
        }
    
    async def register_websocket(self, session_id: str, websocket: WebSocket):
        """Register a WebSocket connection for real-time features"""
        self.websocket_connections[session_id] = websocket
        
        # Find and update the session
        for session in self.active_sessions.values():
            if session.session_id == session_id:
                session.websocket = websocket
                break
    
    async def unregister_websocket(self, session_id: str):
        """Unregister a WebSocket connection"""
        if session_id in self.websocket_connections:
            del self.websocket_connections[session_id]
        
        # Update the session
        for session in self.active_sessions.values():
            if session.session_id == session_id:
                session.websocket = None
                break
    
    async def broadcast_clear_event(self, project_path: str, initiated_by: str):
        """
        Broadcast clear event to all connected clients
        This ensures UI updates when context is cleared
        """
        project_id = self.get_project_id(project_path)
        
        message = {
            "type": "context_cleared",
            "project_id": project_id,
            "initiated_by": initiated_by,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all websockets for this project
        for session_key, session in self.active_sessions.items():
            if session.project_id == project_id and session.websocket:
                try:
                    await session.websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send clear event: {str(e)}")
    
    async def cleanup_inactive_sessions(self, hours: int = 24):
        """Clean up inactive sessions older than specified hours"""
        from datetime import timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        async with self.pg_pool.acquire() as conn:
            deleted = await conn.execute("""
                UPDATE ai_sessions 
                SET cleared = TRUE 
                WHERE last_accessed < $1 AND NOT cleared
            """, cutoff_time)
            
        logger.info(f"Cleaned up {deleted} inactive AI sessions")
    
    def is_healthy(self) -> bool:
        """Check if session manager is healthy"""
        return bool(self.redis_client and self.pg_pool)
    
    async def close(self):
        """Close all connections"""
        # Close all websockets
        for ws in self.websocket_connections.values():
            await ws.close()
        
        self.websocket_connections.clear()
        self.active_sessions.clear()
        
        if self.redis_client:
            await self.redis_client.close()
        if self.pg_pool:
            await self.pg_pool.close()