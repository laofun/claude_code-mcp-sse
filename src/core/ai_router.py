"""
Multi-AI Context Router
Routes requests to appropriate AI services while maintaining their individual contexts
"""

import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger(__name__)


class AIConfig:
    """Configuration for an AI service"""
    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.headers = self._build_headers()
    
    def _build_headers(self) -> Dict[str, str]:
        """Build headers based on AI type"""
        if self.name == "gemini":
            return {
                "Content-Type": "application/json"
            }
        elif self.name in ["openai", "deepseek"]:
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        elif self.name == "grok":
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        return {}


class AIContextRouter:
    """
    Routes requests to different AI services while maintaining context
    Each AI gets its own context per project
    """
    
    def __init__(self):
        self.ai_configs: Dict[str, AIConfig] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # AI-specific endpoints
        self.endpoints = {
            "gemini": {
                "chat": "/v1beta/models/{model}:generateContent?key={api_key}",
                "stream": "/v1beta/models/{model}:streamGenerateContent?key={api_key}"
            },
            "openai": {
                "chat": "/v1/chat/completions",
                "models": "/v1/models"
            },
            "grok": {
                "chat": "/v1/chat/completions",
                "models": "/v1/models"
            },
            "deepseek": {
                "chat": "/chat/completions",
                "models": "/models"
            }
        }
    
    async def initialize(self):
        """Initialize HTTP session and load AI configurations"""
        self.session = aiohttp.ClientSession()
        await self._load_ai_configs()
        logger.info("AI Context Router initialized")
    
    async def _load_ai_configs(self):
        """Load AI configurations from environment or config file"""
        import os
        
        # Load from environment variables
        configs = {
            "gemini": {
                "base_url": "https://generativelanguage.googleapis.com",
                "api_key": os.getenv("GEMINI_API_KEY", ""),
                "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            },
            "openai": {
                "base_url": "https://api.openai.com",
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": os.getenv("OPENAI_MODEL", "gpt-4o")
            },
            "grok": {
                "base_url": "https://api.x.ai",
                "api_key": os.getenv("GROK_API_KEY", ""),
                "model": os.getenv("GROK_MODEL", "grok-3")
            },
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            }
        }
        
        # Create AIConfig objects for configured AIs
        for ai_name, config in configs.items():
            if config["api_key"]:
                self.ai_configs[ai_name] = AIConfig(
                    name=ai_name,
                    base_url=config["base_url"],
                    api_key=config["api_key"],
                    model=config["model"]
                )
                logger.info(f"Configured AI: {ai_name} with model {config['model']}")
    
    async def route_request(
        self,
        ai_name: str,
        method: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route request to appropriate AI service
        Handles context injection and response formatting
        """
        if ai_name not in self.ai_configs:
            return {
                "error": f"AI '{ai_name}' not configured",
                "available_ais": list(self.ai_configs.keys())
            }
        
        ai_config = self.ai_configs[ai_name]
        
        try:
            # Determine the operation type
            if "ask" in method or "chat" in method:
                return await self._handle_chat_request(ai_config, params, context)
            elif "code_review" in method:
                return await self._handle_code_review(ai_config, params, context)
            elif "debug" in method:
                return await self._handle_debug_request(ai_config, params, context)
            elif "brainstorm" in method:
                return await self._handle_brainstorm(ai_config, params, context)
            elif "analyze" in method:
                return await self._handle_analysis(ai_config, params, context)
            else:
                return await self._handle_generic_request(ai_config, method, params, context)
                
        except Exception as e:
            logger.error(f"Error routing to {ai_name}: {str(e)}")
            return {
                "error": f"Failed to call {ai_name}: {str(e)}",
                "ai": ai_name,
                "method": method
            }
    
    async def _handle_chat_request(
        self,
        ai_config: AIConfig,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle chat/ask requests for an AI"""
        # Extract prompt
        prompt = params.get("prompt", params.get("message", ""))
        
        # Build request based on AI type
        if ai_config.name == "gemini":
            request_data = self._build_gemini_request(prompt, context)
            url = ai_config.base_url + self.endpoints["gemini"]["chat"].format(
                model=ai_config.model,
                api_key=ai_config.api_key
            )
        else:
            # OpenAI-compatible format (OpenAI, Grok, DeepSeek)
            request_data = self._build_openai_request(prompt, context, ai_config.model)
            url = ai_config.base_url + self.endpoints[ai_config.name]["chat"]
        
        # Make the request
        response = await self._make_request(ai_config, url, request_data)
        
        # Extract and format response
        return self._format_response(ai_config.name, response, "chat")
    
    async def _handle_code_review(
        self,
        ai_config: AIConfig,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle code review requests"""
        code = params.get("code", "")
        focus = params.get("focus", "general")
        
        prompt = f"""Please review the following code with a focus on {focus}:

```
{code}
```

Provide specific suggestions for improvement."""
        
        # Add context about previous reviews if available
        if context and "previous_reviews" in context:
            prompt = f"Previous review context:\n{context['previous_reviews']}\n\n{prompt}"
        
        params["prompt"] = prompt
        return await self._handle_chat_request(ai_config, params, context)
    
    async def _handle_debug_request(
        self,
        ai_config: AIConfig,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle debugging requests"""
        error = params.get("error", "")
        code = params.get("code", "")
        
        prompt = f"""Help debug this issue:

Error: {error}

Related code:
```
{code}
```

Provide step-by-step debugging suggestions."""
        
        # Add debugging context if available
        if context and "debug_session" in context:
            prompt = f"Current debugging session: {context['debug_session']}\n\n{prompt}"
        
        params["prompt"] = prompt
        return await self._handle_chat_request(ai_config, params, context)
    
    async def _handle_brainstorm(
        self,
        ai_config: AIConfig,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle brainstorming requests"""
        topic = params.get("topic", params.get("challenge", ""))
        constraints = params.get("constraints", "")
        
        prompt = f"Brainstorm creative solutions for: {topic}"
        if constraints:
            prompt += f"\n\nConstraints: {constraints}"
        
        params["prompt"] = prompt
        return await self._handle_chat_request(ai_config, params, context)
    
    async def _handle_analysis(
        self,
        ai_config: AIConfig,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle code analysis requests"""
        code = params.get("code", "")
        analysis_type = params.get("type", "general")
        
        prompt = f"Analyze the following code for {analysis_type}:\n\n```\n{code}\n```"
        
        params["prompt"] = prompt
        return await self._handle_chat_request(ai_config, params, context)
    
    async def _handle_generic_request(
        self,
        ai_config: AIConfig,
        method: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle generic requests"""
        # Pass through to chat handler
        return await self._handle_chat_request(ai_config, params, context)
    
    def _build_gemini_request(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build request for Gemini API"""
        contents = []
        
        # Add context as previous messages if available
        if context and "_context_metadata" in context:
            # Context has already been injected by MCP handler
            contents.append({
                "parts": [{"text": prompt}]
            })
        else:
            contents.append({
                "parts": [{"text": prompt}]
            })
        
        return {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }
    
    def _build_openai_request(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]],
        model: str
    ) -> Dict[str, Any]:
        """Build request for OpenAI-compatible APIs"""
        messages = []
        
        # Check if context messages were already injected
        if context and "messages" in context:
            messages = context["messages"]
        else:
            messages = [
                {"role": "user", "content": prompt}
            ]
        
        return {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }
    
    async def _make_request(
        self,
        ai_config: AIConfig,
        url: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make HTTP request to AI service"""
        async with self.session.post(
            url,
            headers=ai_config.headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            response_data = await response.json()
            
            if response.status != 200:
                logger.error(f"AI request failed: {response.status} - {response_data}")
                raise Exception(f"AI request failed: {response_data}")
            
            return response_data
    
    def _format_response(
        self,
        ai_name: str,
        response: Dict[str, Any],
        response_type: str
    ) -> Dict[str, Any]:
        """Format AI response to consistent structure"""
        formatted = {
            "ai": ai_name,
            "type": response_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Extract content based on AI type
        if ai_name == "gemini":
            if "candidates" in response and response["candidates"]:
                content = response["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    formatted["content"] = parts[0].get("text", "")
        else:
            # OpenAI format
            if "choices" in response and response["choices"]:
                message = response["choices"][0].get("message", {})
                formatted["content"] = message.get("content", "")
        
        # Add usage statistics if available
        if "usage" in response:
            formatted["usage"] = response["usage"]
        
        return formatted
    
    async def get_available_ais(self) -> List[Dict[str, str]]:
        """Get list of available AIs with their configurations"""
        return [
            {
                "name": ai_name,
                "model": config.model,
                "configured": True
            }
            for ai_name, config in self.ai_configs.items()
        ]
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()