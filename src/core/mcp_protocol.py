"""
MCP Protocol Handler with Context Injection
Intercepts MCP requests to other AIs and injects their project-specific context
"""

import json
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger(__name__)


class MCPProtocolHandler:
    """
    Handles MCP protocol requests and responses
    Key features:
    - Detects which AI is being called
    - Injects relevant context for that AI
    - Handles /clear command synchronization
    - Maintains conversation continuity
    """
    
    def __init__(self):
        # Patterns to detect AI calls
        self.ai_patterns = {
            "gemini": [
                r"mcp__gemini.*__(.+)",
                r"ask_gemini",
                r"gemini_(.+)"
            ],
            "grok": [
                r"mcp__.*grok.*__(.+)",
                r"ask_grok", 
                r"grok_(.+)"
            ],
            "openai": [
                r"mcp__.*openai.*__(.+)",
                r"ask_openai",
                r"ask_chatgpt",
                r"openai_(.+)"
            ],
            "deepseek": [
                r"mcp__.*deepseek.*__(.+)",
                r"ask_deepseek",
                r"deepseek_(.+)"
            ]
        }
        
        # Tools that should have context injected
        self.context_aware_tools = [
            "ask", "code_review", "debug", "analyze", "brainstorm",
            "think_deep", "architecture", "test", "refactor"
        ]
        
        # Commands that trigger actions
        self.command_patterns = {
            "clear": r"^/clear\s*(.*)$",
            "context": r"^/context\s*(.*)$",
            "history": r"^/history\s*(.*)$"
        }
    
    def detect_ai_from_method(self, method: str) -> Optional[str]:
        """Detect which AI is being called from the method name"""
        for ai_name, patterns in self.ai_patterns.items():
            for pattern in patterns:
                if re.search(pattern, method, re.IGNORECASE):
                    return ai_name
        return None
    
    def should_inject_context(self, method: str) -> bool:
        """Determine if this method should have context injected"""
        method_lower = method.lower()
        return any(tool in method_lower for tool in self.context_aware_tools)
    
    def detect_command(self, content: str) -> Optional[Tuple[str, str]]:
        """Detect if content contains a command like /clear"""
        for cmd_name, pattern in self.command_patterns.items():
            match = re.match(pattern, content.strip(), re.IGNORECASE)
            if match:
                return (cmd_name, match.group(1) if match.groups() else "")
        return None
    
    async def handle_request(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: Optional[int],
        context_manager,
        session_manager,
        debug_service,
        analysis_service
    ) -> Any:
        """
        Handle incoming MCP request
        Injects context when calling other AIs
        """
        try:
            # Get current project path (from params or environment)
            project_path = params.get("project_path") or os.getcwd()
            
            # Handle special methods
            if method == "initialize":
                return await self._handle_initialize(params)
            
            elif method == "tools/list":
                return await self._handle_tools_list()
            
            elif method == "notifications/list":
                return await self._handle_notifications_list()
            
            # Check for commands in the content
            if "prompt" in params or "content" in params:
                content = params.get("prompt") or params.get("content", "")
                command = self.detect_command(content)
                
                if command:
                    cmd_name, cmd_args = command
                    if cmd_name == "clear":
                        # Handle /clear command
                        return await self._handle_clear_command(
                            cmd_args, project_path, session_manager, context_manager
                        )
            
            # Detect which AI is being called
            ai_name = self.detect_ai_from_method(method)
            
            if ai_name and self.should_inject_context(method):
                # Get or create session for this AI and project
                session = await session_manager.get_or_create_session(
                    ai_name, project_path
                )
                
                if session:
                    # Get context for this AI
                    context = await context_manager.get_context(session.session_id)
                    
                    if context and context.messages:
                        # Inject context into the request
                        params = await self._inject_context(
                            params, context, ai_name, method
                        )
                        
                        logger.info(f"Injected context for {ai_name}: {len(context.messages)} messages")
            
            # Handle the actual tool call
            if method.startswith("tools/call"):
                tool_name = params.get("name", "")
                tool_params = params.get("arguments", {})
                
                # Route to appropriate service
                if "debug" in tool_name:
                    result = await debug_service.handle_tool_call(tool_name, tool_params)
                elif "analyze" in tool_name or "review" in tool_name:
                    result = await analysis_service.handle_tool_call(tool_name, tool_params)
                else:
                    # Default handling - pass through to the actual AI
                    result = await self._call_external_ai(ai_name, method, params)
                
                # Store the response in context
                if ai_name and session:
                    await self._store_ai_response(
                        context_manager, session.session_id, ai_name, params, result
                    )
                
                return result
            
            # Default response for unhandled methods
            return {"status": "ok"}
            
        except Exception as e:
            logger.error(f"MCP request error: {str(e)}")
            raise
    
    async def _inject_context(
        self,
        params: Dict[str, Any],
        context,
        ai_name: str,
        method: str
    ) -> Dict[str, Any]:
        """
        Inject relevant context into the AI request
        Makes the AI aware of previous conversations
        """
        # Build context summary
        context_summary = self._build_context_summary(context, ai_name)
        
        # Inject based on parameter type
        if "prompt" in params:
            # Prepend context to the prompt
            original_prompt = params["prompt"]
            params["prompt"] = f"{context_summary}\n\nCurrent request: {original_prompt}"
            
        elif "messages" in params:
            # For chat-style APIs, prepend context messages
            context_messages = self._convert_to_chat_messages(context, ai_name)
            params["messages"] = context_messages + params.get("messages", [])
            
        elif "content" in params:
            # For content-based requests
            original_content = params["content"]
            params["content"] = f"{context_summary}\n\n{original_content}"
        
        # Add metadata about the session
        params["_context_metadata"] = {
            "ai_name": ai_name,
            "session_id": context.session_id,
            "message_count": len(context.messages),
            "project_context": context.project_context
        }
        
        return params
    
    def _build_context_summary(self, context, ai_name: str) -> str:
        """Build a concise summary of previous context"""
        if not context.messages:
            return ""
        
        summary_parts = [
            f"[Previous context for {ai_name.upper()}]",
            f"You have been working on this project before. Here's what you should remember:"
        ]
        
        # Add project context if available
        if context.project_context:
            summary_parts.append(f"\nProject: {context.project_context.get('name', 'Unknown')}")
            summary_parts.append(f"Path: {context.project_context.get('path', 'Unknown')}")
            
            if "current_files" in context.project_context:
                summary_parts.append(f"Files you've worked with: {', '.join(context.project_context['current_files'][:5])}")
        
        # Add recent conversation summary
        recent_messages = context.messages[-10:]  # Last 10 messages
        if recent_messages:
            summary_parts.append("\nRecent conversation:")
            for msg in recent_messages:
                role = "You" if msg.role == "assistant" else "User"
                # Truncate long messages
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                summary_parts.append(f"{role}: {content}")
        
        # Add any active debugging or analysis state
        if context.metadata.get("active_debug_session"):
            summary_parts.append(f"\nActive debugging session: {context.metadata['active_debug_session']}")
        
        summary_parts.append("\n[End of previous context]")
        
        return "\n".join(summary_parts)
    
    def _convert_to_chat_messages(self, context, ai_name: str) -> List[Dict[str, str]]:
        """Convert context to chat message format"""
        messages = []
        
        # Add system message with context
        system_msg = {
            "role": "system",
            "content": f"You are {ai_name.upper()} assisting with a software project. "
                      f"You have previous context from earlier conversations that you should consider."
        }
        
        if context.project_context:
            system_msg["content"] += f"\n\nProject: {context.project_context.get('name', 'Unknown')}"
            system_msg["content"] += f"\nPath: {context.project_context.get('path', 'Unknown')}"
        
        messages.append(system_msg)
        
        # Add recent conversation messages
        for msg in context.messages[-20:]:  # Last 20 messages
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return messages
    
    async def _store_ai_response(
        self,
        context_manager,
        session_id: str,
        ai_name: str,
        request: Dict[str, Any],
        response: Any
    ):
        """Store AI request and response in context"""
        # Extract the actual prompt/content
        user_content = request.get("prompt") or request.get("content", "")
        
        # Remove our injected context to get original request
        if "[Previous context for" in user_content:
            parts = user_content.split("[End of previous context]")
            if len(parts) > 1:
                user_content = parts[1].strip()
                if user_content.startswith("Current request:"):
                    user_content = user_content[len("Current request:"):].strip()
        
        # Store user message
        await context_manager.add_message(
            session_id=session_id,
            role="user",
            content=user_content,
            metadata={
                "ai_name": ai_name,
                "method": request.get("_method", "unknown"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Store AI response
        response_content = self._extract_response_content(response)
        if response_content:
            await context_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=response_content,
                metadata={
                    "ai_name": ai_name,
                    "response_type": type(response).__name__,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    def _extract_response_content(self, response: Any) -> str:
        """Extract text content from various response formats"""
        if isinstance(response, str):
            return response
        elif isinstance(response, dict):
            # Try common response fields
            for field in ["content", "text", "message", "result", "output"]:
                if field in response:
                    return str(response[field])
            # Fallback to JSON representation
            return json.dumps(response, indent=2)
        else:
            return str(response)
    
    async def _handle_clear_command(
        self,
        args: str,
        project_path: str,
        session_manager,
        context_manager
    ):
        """
        Handle /clear command
        Can clear specific AI or all AIs
        """
        args = args.strip().lower()
        
        if args in ["all", ""]:
            # Clear all AI contexts for this project
            await session_manager.clear_all_ai_contexts(project_path)
            message = "Cleared context for all AIs in this project"
        else:
            # Clear specific AI
            ai_name = None
            for ai in ["gemini", "grok", "openai", "deepseek"]:
                if ai in args:
                    ai_name = ai
                    break
            
            if ai_name:
                await session_manager.clear_ai_context(ai_name, project_path)
                message = f"Cleared context for {ai_name.upper()}"
            else:
                message = f"Unknown AI: {args}. Use /clear all or /clear [gemini|grok|openai|deepseek]"
        
        # Broadcast clear event
        await session_manager.broadcast_clear_event(project_path, "user_command")
        
        return {"status": "ok", "message": message}
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        return {
            "protocolVersion": "1.0",
            "serverName": "enhanced-mcp-context-server",
            "serverVersion": "0.1.0",
            "capabilities": {
                "tools": True,
                "notifications": True,
                "context": True,
                "debugging": True
            }
        }
    
    async def _handle_tools_list(self) -> Dict[str, Any]:
        """Return list of available tools"""
        tools = [
            {
                "name": "clear_context",
                "description": "Clear AI context for current project",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ai_name": {
                            "type": "string",
                            "description": "AI to clear (gemini/grok/openai/deepseek/all)"
                        }
                    }
                }
            },
            {
                "name": "show_context",
                "description": "Show current context for an AI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ai_name": {
                            "type": "string",
                            "description": "AI to show context for"
                        }
                    }
                }
            },
            {
                "name": "project_info",
                "description": "Get project information and AI session stats",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        return {"tools": tools}
    
    async def _handle_notifications_list(self) -> Dict[str, Any]:
        """Return list of supported notifications"""
        return {
            "notifications": [
                {
                    "method": "context/cleared",
                    "description": "Notifies when context is cleared"
                },
                {
                    "method": "session/created",
                    "description": "Notifies when new AI session is created"
                }
            ]
        }
    
    async def _call_external_ai(
        self,
        ai_name: str,
        method: str,
        params: Dict[str, Any]
    ) -> Any:
        """
        Placeholder for calling actual AI services
        In production, this would route to the appropriate AI MCP server
        """
        # For now, return a mock response
        return {
            "response": f"Response from {ai_name} for method {method}",
            "status": "ok",
            "ai": ai_name,
            "context_aware": True
        }
    
    async def handle_websocket_message(
        self,
        session_id: str,
        message: Dict[str, Any],
        context_manager,
        debug_service
    ) -> Dict[str, Any]:
        """Handle WebSocket messages for real-time features"""
        msg_type = message.get("type")
        
        if msg_type == "debug_update":
            # Handle debug updates
            return await debug_service.handle_websocket_update(session_id, message)
        
        elif msg_type == "context_query":
            # Query context
            context = await context_manager.get_context(session_id)
            return {
                "type": "context_response",
                "context": context.dict() if context else None
            }
        
        else:
            return {
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            }


import os  # Add this import at the top