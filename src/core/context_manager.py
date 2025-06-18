"""
Context Manager for persistent conversation history
Implements hybrid storage with Redis cache and PostgreSQL persistence
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4, UUID

import redis.asyncio as redis
import asyncpg
from pydantic import BaseModel

from utils.logger import setup_logger

logger = setup_logger(__name__)


class Message(BaseModel):
    """Message model for conversation history"""
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = {}


class ConversationContext(BaseModel):
    """Conversation context model"""
    session_id: str
    user_id: Optional[str] = None
    messages: List[Message] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    project_context: Optional[Dict[str, Any]] = None


class ContextManager:
    """
    Manages conversation context with hybrid storage
    - Redis for fast active session access
    - PostgreSQL for long-term persistence
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.cache_ttl = 3600  # 1 hour default TTL
        
    async def initialize(self):
        """Initialize database connections"""
        try:
            # Initialize Redis
            self.redis_client = await redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connection established")
            
            # Initialize PostgreSQL
            self.pg_pool = await asyncpg.create_pool(
                os.getenv("DATABASE_URL", "postgresql://mcp_user:mcp_password@localhost:5432/mcp_dev"),
                min_size=5,
                max_size=20
            )
            
            # Create tables if not exist
            await self._create_tables()
            logger.info("PostgreSQL connection established")
            
        except Exception as e:
            logger.error(f"Failed to initialize ContextManager: {str(e)}")
            raise
    
    async def _create_tables(self):
        """Create necessary database tables"""
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id UUID PRIMARY KEY,
                    user_id TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY,
                    session_id UUID REFERENCES conversations(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS project_contexts (
                    session_id UUID PRIMARY KEY REFERENCES conversations(session_id) ON DELETE CASCADE,
                    project_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    async def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """
        Get conversation context for a session
        First checks Redis cache, then PostgreSQL
        """
        # Try cache first
        cached = await self._get_from_cache(session_id)
        if cached:
            logger.debug(f"Context retrieved from cache for session {session_id}")
            return cached
        
        # Fallback to database
        context = await self._get_from_database(session_id)
        if context:
            # Populate cache
            await self._save_to_cache(session_id, context)
            logger.debug(f"Context retrieved from database for session {session_id}")
        
        return context
    
    async def save_context(self, context: ConversationContext):
        """Save context to both cache and database"""
        # Save to cache for fast access
        await self._save_to_cache(context.session_id, context)
        
        # Save to database asynchronously
        asyncio.create_task(self._save_to_database(context))
        
        logger.debug(f"Context saved for session {context.session_id}")
    
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add a message to the conversation"""
        # Get or create context
        context = await self.get_context(session_id)
        if not context:
            context = ConversationContext(
                session_id=session_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        # Create message
        message = Message(
            id=str(uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Add to context
        context.messages.append(message)
        context.updated_at = datetime.utcnow()
        
        # Save context
        await self.save_context(context)
        
        return message
    
    async def update_project_context(
        self, 
        session_id: str, 
        project_data: Dict[str, Any]
    ):
        """Update project-specific context for a session"""
        context = await self.get_context(session_id)
        if not context:
            raise ValueError(f"Session {session_id} not found")
        
        context.project_context = project_data
        context.updated_at = datetime.utcnow()
        
        await self.save_context(context)
    
    async def search_messages(
        self, 
        session_id: str, 
        query: str, 
        limit: int = 10
    ) -> List[Message]:
        """Search messages in a conversation"""
        context = await self.get_context(session_id)
        if not context:
            return []
        
        # Simple text search (can be enhanced with full-text search)
        results = []
        for message in reversed(context.messages):
            if query.lower() in message.content.lower():
                results.append(message)
                if len(results) >= limit:
                    break
        
        return results
    
    async def get_recent_sessions(
        self, 
        user_id: Optional[str] = None, 
        limit: int = 10
    ) -> List[str]:
        """Get recent session IDs"""
        async with self.pg_pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch("""
                    SELECT session_id FROM conversations
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                    LIMIT $2
                """, user_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT session_id FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT $1
                """, limit)
            
            return [str(row['session_id']) for row in rows]
    
    async def _get_from_cache(self, session_id: str) -> Optional[ConversationContext]:
        """Get context from Redis cache"""
        try:
            data = await self.redis_client.get(f"context:{session_id}")
            if data:
                return ConversationContext(**json.loads(data))
        except Exception as e:
            logger.error(f"Cache retrieval error: {str(e)}")
        return None
    
    async def _save_to_cache(self, session_id: str, context: ConversationContext):
        """Save context to Redis cache"""
        try:
            await self.redis_client.setex(
                f"context:{session_id}",
                self.cache_ttl,
                json.dumps(context.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Cache save error: {str(e)}")
    
    async def _get_from_database(self, session_id: str) -> Optional[ConversationContext]:
        """Get context from PostgreSQL"""
        try:
            async with self.pg_pool.acquire() as conn:
                # Get conversation
                conv_row = await conn.fetchrow("""
                    SELECT * FROM conversations WHERE session_id = $1
                """, UUID(session_id))
                
                if not conv_row:
                    return None
                
                # Get messages
                message_rows = await conn.fetch("""
                    SELECT * FROM messages 
                    WHERE session_id = $1 
                    ORDER BY timestamp ASC
                """, UUID(session_id))
                
                # Get project context
                proj_row = await conn.fetchrow("""
                    SELECT project_data FROM project_contexts
                    WHERE session_id = $1
                """, UUID(session_id))
                
                # Build context
                messages = [
                    Message(
                        id=str(row['id']),
                        role=row['role'],
                        content=row['content'],
                        timestamp=row['timestamp'],
                        metadata=row['metadata']
                    )
                    for row in message_rows
                ]
                
                return ConversationContext(
                    session_id=session_id,
                    user_id=conv_row['user_id'],
                    messages=messages,
                    metadata=conv_row['metadata'],
                    created_at=conv_row['created_at'],
                    updated_at=conv_row['updated_at'],
                    project_context=proj_row['project_data'] if proj_row else None
                )
                
        except Exception as e:
            logger.error(f"Database retrieval error: {str(e)}")
            return None
    
    async def _save_to_database(self, context: ConversationContext):
        """Save context to PostgreSQL"""
        try:
            async with self.pg_pool.acquire() as conn:
                async with conn.transaction():
                    # Upsert conversation
                    await conn.execute("""
                        INSERT INTO conversations (session_id, user_id, metadata, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (session_id) 
                        DO UPDATE SET 
                            metadata = $3,
                            updated_at = $5
                    """, 
                        uuid4.UUID(context.session_id),
                        context.user_id,
                        json.dumps(context.metadata),
                        context.created_at,
                        context.updated_at
                    )
                    
                    # Get existing message IDs
                    existing_ids = await conn.fetch("""
                        SELECT id FROM messages WHERE session_id = $1
                    """, uuid4.UUID(context.session_id))
                    existing_id_set = {str(row['id']) for row in existing_ids}
                    
                    # Insert new messages
                    for message in context.messages:
                        if message.id not in existing_id_set:
                            await conn.execute("""
                                INSERT INTO messages (id, session_id, role, content, metadata, timestamp)
                                VALUES ($1, $2, $3, $4, $5, $6)
                            """,
                                uuid4.UUID(message.id),
                                uuid4.UUID(context.session_id),
                                message.role,
                                message.content,
                                json.dumps(message.metadata),
                                message.timestamp
                            )
                    
                    # Update project context if exists
                    if context.project_context:
                        await conn.execute("""
                            INSERT INTO project_contexts (session_id, project_data, updated_at)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (session_id)
                            DO UPDATE SET
                                project_data = $2,
                                updated_at = $3
                        """,
                            uuid4.UUID(context.session_id),
                            json.dumps(context.project_context),
                            datetime.utcnow()
                        )
                        
        except Exception as e:
            logger.error(f"Database save error: {str(e)}")
    
    async def cleanup_old_sessions(self, days: int = 30):
        """Clean up old sessions"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        async with self.pg_pool.acquire() as conn:
            deleted = await conn.execute("""
                DELETE FROM conversations
                WHERE updated_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up {deleted} old sessions")
    
    def is_healthy(self) -> bool:
        """Check if context manager is healthy"""
        return bool(self.redis_client and self.pg_pool)
    
    async def close(self):
        """Close database connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.pg_pool:
            await self.pg_pool.close()


