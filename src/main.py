#!/usr/bin/env python3
"""
Enhanced MCP Server for Claude Code
Main entry point for the FastAPI application
"""

import os
import sys
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our modules
from core.context_manager import ContextManager
from core.mcp_protocol import MCPProtocolHandler
from core.session_manager import SessionManager
from core.ai_router import AIContextRouter
from services.debug_service import DebugService
from services.analysis_service import AnalysisService
from utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)


class MCPRequest(BaseModel):
    """MCP Protocol Request Model"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: Optional[int] = None


class MCPResponse(BaseModel):
    """MCP Protocol Response Model"""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle"""
    # Startup
    logger.info("Starting Enhanced MCP Server...")
    
    # Initialize services
    app.state.context_manager = ContextManager()
    app.state.session_manager = SessionManager()
    app.state.debug_service = DebugService()
    app.state.analysis_service = AnalysisService()
    app.state.mcp_handler = MCPProtocolHandler()
    app.state.ai_router = AIContextRouter()
    
    # Initialize connections
    await app.state.context_manager.initialize()
    await app.state.session_manager.initialize()
    await app.state.ai_router.initialize()
    await app.state.debug_service.initialize()
    await app.state.analysis_service.initialize()
    
    logger.info("MCP Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP Server...")
    await app.state.context_manager.close()
    await app.state.session_manager.close()
    logger.info("MCP Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Claude Code Enhanced MCP Server",
    description="Advanced MCP server with persistent context and development tools",
    version="0.1.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Claude Code Enhanced MCP Server",
        "version": "0.1.0",
        "status": "running",
        "features": {
            "context_persistence": True,
            "debugging": os.getenv("ENABLE_DEBUGGING", "true") == "true",
            "code_analysis": os.getenv("ENABLE_CODE_ANALYSIS", "true") == "true",
            "performance_profiling": os.getenv("ENABLE_PERFORMANCE_PROFILING", "true") == "true",
            "test_generation": os.getenv("ENABLE_TEST_GENERATION", "true") == "true"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "context_manager": app.state.context_manager.is_healthy(),
            "session_manager": app.state.session_manager.is_healthy(),
            "debug_service": app.state.debug_service.is_healthy(),
            "analysis_service": app.state.analysis_service.is_healthy()
        }
    }


@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    """Handle MCP protocol requests"""
    try:
        # Process the request through MCP handler
        result = await app.state.mcp_handler.handle_request(
            method=request.method,
            params=request.params,
            request_id=request.id,
            context_manager=app.state.context_manager,
            session_manager=app.state.session_manager,
            debug_service=app.state.debug_service,
            analysis_service=app.state.analysis_service
        )
        
        return MCPResponse(
            jsonrpc="2.0",
            result=result,
            id=request.id
        )
    except Exception as e:
        logger.error(f"MCP request error: {str(e)}")
        return MCPResponse(
            jsonrpc="2.0",
            error={
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            },
            id=request.id
        )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time features"""
    await websocket.accept()
    
    # Register the websocket connection
    await app.state.session_manager.register_websocket(session_id, websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Handle the message
            response = await app.state.mcp_handler.handle_websocket_message(
                session_id=session_id,
                message=data,
                context_manager=app.state.context_manager,
                debug_service=app.state.debug_service
            )
            
            # Send response
            await websocket.send_json(response)
            
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}")
    finally:
        # Unregister the websocket
        await app.state.session_manager.unregister_websocket(session_id)


@app.post("/context/{session_id}")
async def get_context(session_id: str):
    """Get context for a session"""
    context = await app.state.context_manager.get_context(session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    return context


@app.post("/debug/start")
async def start_debug_session(session_id: str, file_path: str):
    """Start a debugging session"""
    debug_session = await app.state.debug_service.start_session(
        session_id=session_id,
        file_path=file_path
    )
    return {"debug_session_id": debug_session.id, "status": "started"}


@app.post("/analyze")
async def analyze_code(code: str, language: str = "python"):
    """Analyze code for issues and suggestions"""
    results = await app.state.analysis_service.analyze(
        code=code,
        language=language
    )
    return results


# Standard MCP protocol handling for stdio
async def handle_stdio():
    """Handle MCP protocol over stdio"""
    logger.info("Starting stdio MCP handler...")
    
    while True:
        try:
            # Read from stdin
            line = sys.stdin.readline()
            if not line:
                break
                
            # Parse JSON-RPC request
            try:
                request_data = json.loads(line.strip())
                request = MCPRequest(**request_data)
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error",
                        "data": str(e)
                    },
                    "id": None
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
                continue
            
            # Handle the request
            result = await app.state.mcp_handler.handle_request(
                method=request.method,
                params=request.params,
                request_id=request.id,
                context_manager=app.state.context_manager,
                session_manager=app.state.session_manager,
                debug_service=app.state.debug_service,
                analysis_service=app.state.analysis_service
            )
            
            # Send response
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request.id
            }
            print(json.dumps(response))
            sys.stdout.flush()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Stdio handler error: {str(e)}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                },
                "id": None
            }
            print(json.dumps(error_response))
            sys.stdout.flush()


def main():
    """Main entry point"""
    # Check if running in stdio mode
    if "--stdio" in sys.argv:
        # Run in stdio mode for MCP protocol
        asyncio.run(handle_stdio())
    else:
        # Run as HTTP server
        uvicorn.run(
            "main:app",
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_PORT", 8000)),
            reload=os.getenv("PYTHON_ENV", "development") == "development",
            log_level=os.getenv("LOG_LEVEL", "info").lower()
        )


if __name__ == "__main__":
    main()