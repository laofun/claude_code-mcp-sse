"""
Simple File-based Context Manager
Stores context in JSON files without any external dependencies
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import fcntl
import tempfile
import shutil


class SimpleContextManager:
    """
    Manages AI context using local JSON files
    Storage structure: ~/.enhanced-mcp/contexts/{project_id}/{ai_name}.json
    """
    
    def __init__(self):
        # Use home directory for storage
        self.storage_root = os.path.expanduser("~/.enhanced-mcp/contexts")
        self.max_messages = 100  # Keep last 100 messages per AI
        self.lock_timeout = 5  # seconds
    
    async def ensure_storage_dir(self):
        """Ensure storage directory exists"""
        Path(self.storage_root).mkdir(parents=True, exist_ok=True)
    
    def _get_context_path(self, project_id: str, ai_name: str) -> str:
        """Get path to context file"""
        # Sanitize project_id and ai_name to be filesystem-safe
        safe_project_id = "".join(c for c in project_id if c.isalnum() or c in "._-")
        safe_ai_name = "".join(c for c in ai_name if c.isalnum() or c in "._-")
        
        project_dir = os.path.join(self.storage_root, safe_project_id)
        os.makedirs(project_dir, exist_ok=True)
        
        return os.path.join(project_dir, f"{safe_ai_name}.json")
    
    async def get_context(self, project_id: str, ai_name: str) -> Optional[Dict[str, Any]]:
        """Get context for an AI in a project"""
        context_path = self._get_context_path(project_id, ai_name)
        
        if not os.path.exists(context_path):
            return None
        
        try:
            # Read with file locking
            with open(context_path, 'r') as f:
                # Try to acquire lock (non-blocking)
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    content = f.read()
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    
                    if content:
                        return json.loads(content)
                except (IOError, OSError):
                    # If can't get lock, try reading anyway (might get partial data)
                    content = f.read()
                    if content:
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            return None
                
        except Exception as e:
            # Log error but don't crash
            print(f"Error reading context: {e}", file=os.sys.stderr)
            return None
        
        return None
    
    async def save_context(self, project_id: str, ai_name: str, context: Dict[str, Any]):
        """Save context for an AI in a project"""
        context_path = self._get_context_path(project_id, ai_name)
        
        # Ensure messages list exists
        if "messages" not in context:
            context["messages"] = []
        
        # Trim to max messages
        if len(context["messages"]) > self.max_messages:
            context["messages"] = context["messages"][-self.max_messages:]
        
        # Update metadata
        context["updated_at"] = datetime.utcnow().isoformat()
        if "created_at" not in context:
            context["created_at"] = context["updated_at"]
        
        try:
            # Write to temporary file first (atomic write)
            temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(context_path))
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    # Try to acquire exclusive lock
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        json.dump(context, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (IOError, OSError):
                        # If can't get lock, write anyway
                        json.dump(context, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                
                # Atomic rename
                shutil.move(temp_path, context_path)
                
            except Exception:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
                
        except Exception as e:
            print(f"Error saving context: {e}", file=os.sys.stderr)
            # Try direct write as fallback
            try:
                with open(context_path, 'w') as f:
                    json.dump(context, f, indent=2)
            except:
                pass
    
    async def add_message(self, project_id: str, ai_name: str, role: str, content: str):
        """Add a message to the context"""
        # Get existing context or create new
        context = await self.get_context(project_id, ai_name)
        if not context:
            context = {
                "project_id": project_id,
                "ai_name": ai_name,
                "messages": [],
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Add message
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        context["messages"].append(message)
        
        # Save context
        await self.save_context(project_id, ai_name, context)
    
    async def clear_context(self, project_id: str, ai_name: str):
        """Clear context for an AI in a project"""
        context_path = self._get_context_path(project_id, ai_name)
        
        try:
            if os.path.exists(context_path):
                os.unlink(context_path)
        except Exception as e:
            print(f"Error clearing context: {e}", file=os.sys.stderr)
    
    async def clear_project(self, project_id: str):
        """Clear all contexts for a project"""
        safe_project_id = "".join(c for c in project_id if c.isalnum() or c in "._-")
        project_dir = os.path.join(self.storage_root, safe_project_id)
        
        try:
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
        except Exception as e:
            print(f"Error clearing project: {e}", file=os.sys.stderr)
    
    async def list_projects(self) -> List[str]:
        """List all projects with contexts"""
        try:
            if not os.path.exists(self.storage_root):
                return []
            
            return [d for d in os.listdir(self.storage_root) 
                    if os.path.isdir(os.path.join(self.storage_root, d))]
        except Exception:
            return []
    
    async def list_ais_in_project(self, project_id: str) -> List[str]:
        """List all AIs with context in a project"""
        safe_project_id = "".join(c for c in project_id if c.isalnum() or c in "._-")
        project_dir = os.path.join(self.storage_root, safe_project_id)
        
        try:
            if not os.path.exists(project_dir):
                return []
            
            ai_names = []
            for filename in os.listdir(project_dir):
                if filename.endswith('.json'):
                    ai_names.append(filename[:-5])  # Remove .json extension
            
            return ai_names
        except Exception:
            return []