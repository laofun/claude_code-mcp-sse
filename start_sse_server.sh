#!/bin/bash

# MCP SSE Server Startup Script
# This script starts the SSE server with proper environment setup

set -e

echo "🚀 Starting MCP SSE Server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install fastapi uvicorn sse-starlette"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found, using .env.example"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "📝 Created .env file from .env.example"
        echo "💡 Please edit .env file to add your API keys"
    fi
fi

# Load environment variables
if [ -f ".env" ]; then
    echo "📄 Loading environment variables from .env"
    set -a
    source .env
    set +a
fi

# Set default values
export PORT=${PORT:-${SSE_PORT:-23000}}
export HOST=${HOST:-0.0.0.0}

echo "📡 Server will start on $HOST:$PORT"

# Check API keys
api_keys_found=0
if [ ! -z "$GEMINI_API_KEY" ] && [ "$GEMINI_API_KEY" != "your-gemini-api-key-here" ]; then
    echo "✅ Gemini API key configured"
    api_keys_found=$((api_keys_found + 1))
fi

if [ ! -z "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "your-openai-api-key-here" ]; then
    echo "✅ OpenAI API key configured"
    api_keys_found=$((api_keys_found + 1))
fi

if [ ! -z "$DEEPSEEK_API_KEY" ] && [ "$DEEPSEEK_API_KEY" != "your-deepseek-api-key-here" ]; then
    echo "✅ DeepSeek API key configured"
    api_keys_found=$((api_keys_found + 1))
fi

if [ ! -z "$GROK_API_KEY" ] && [ "$GROK_API_KEY" != "your-grok-api-key-here" ]; then
    echo "✅ Grok API key configured"
    api_keys_found=$((api_keys_found + 1))
fi

if [ $api_keys_found -eq 0 ]; then
    echo "⚠️  No API keys configured - server will run in mock mode"
    echo "💡 Edit .env file to add real API keys for AI functionality"
else
    echo "🤖 Found $api_keys_found AI service(s) configured"
fi

echo ""
echo "🌐 Starting SSE Server..."
echo "📊 Monitor at: http://localhost:$PORT/"
echo "🔄 SSE Stream: http://localhost:$PORT/sse"
echo "❌ Press Ctrl+C to stop"
echo ""

# Start the server
python src/mcp_sse_server.py