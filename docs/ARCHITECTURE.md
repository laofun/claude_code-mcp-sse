# Architecture Overview

## System Architecture

MCP AI Collab acts as a context-aware proxy between Claude Code and AI services, adding persistent memory to stateless AI APIs.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Claude Code   │────▶│ MCP AI Collab    │────▶│   AI Services   │
│                 │◀────│    Server        │◀────│ (Gemini, Grok,  │
│                 │     │                  │     │  ChatGPT)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │ Context Storage  │
                        │ (Redis/PostgreSQL│
                        │  or JSON files)  │
                        └──────────────────┘
```

## Core Components

### 1. MCP Protocol Handler

Implements the Model Context Protocol specification:

```python
# Handles standard MCP methods
- initialize()      # Establish connection
- tools/list()      # List available tools
- tools/call()      # Execute tool functions
```

### 2. Context Manager

Manages conversation persistence:

```python
# Key responsibilities
- Load context for AI + project combination
- Save new messages to storage
- Handle context overflow (rotation)
- Clear contexts on demand
```

### 3. AI Router

Routes requests to appropriate AI services:

```python
# Supported AIs
- Gemini (Google AI)
- Grok (X.AI)
- ChatGPT (OpenAI)
```

### 4. Storage Backends

#### JSON Storage (Clean/Standalone)
```
~/.mcp-ai-collab/contexts/
├── project-hash-1/
│   ├── gemini_context.json
│   ├── grok_context.json
│   └── openai_context.json
└── project-hash-2/
    └── ...
```

#### Redis + PostgreSQL (Full)
```sql
-- PostgreSQL Schema
CREATE TABLE ai_sessions (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(32),
    ai_name VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE ai_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES ai_sessions(id),
    role VARCHAR(20),
    content TEXT,
    timestamp TIMESTAMP
);
```

## Data Flow

### 1. Request Flow

```
Claude Code → MCP Request → Context Injection → AI API → Response
```

1. Claude sends MCP tool call (e.g., `ask_gemini`)
2. Server loads context for current project + AI
3. Context injected into AI request
4. AI processes with full conversation history
5. Response saved to context
6. Response returned to Claude

### 2. Context Management

```python
# Project identification
project_id = hash(current_working_directory)

# Context key
context_key = f"{project_id}:{ai_name}"

# Storage pattern
{
    "messages": [
        {"role": "user", "content": "...", "timestamp": "..."},
        {"role": "assistant", "content": "...", "timestamp": "..."}
    ]
}
```

## Security Architecture

### API Key Protection

```
┌─────────────────┐
│   .env file     │ ← Local only, gitignored
│ (your machine)  │
└────────┬────────┘
         │
    ┌────▼────┐
    │ Server  │ ← Never logs keys
    │ Process │
    └────┬────┘
         │
    ┌────▼────────┐
    │ HTTPS Only  │
    │   to APIs   │
    └─────────────┘
```

### Security Measures

1. **Environment Variables**: Keys loaded from `.env`
2. **No Logging**: Keys never appear in logs
3. **No Transmission**: Keys only sent to official APIs
4. **Open Source**: Full code transparency

## Performance Optimizations

### Clean Version
- In-memory cache for active session
- Lazy loading of contexts
- JSON streaming for large files

### Full Version
- Redis caching (last 10 messages)
- PostgreSQL indexing on session_id
- Connection pooling
- Async I/O throughout

## Scalability Considerations

### Horizontal Scaling (Full Version)

```
Load Balancer
     │
┌────┴────┬──────────┬──────────┐
│ Server  │ Server   │ Server   │
│ Node 1  │ Node 2   │ Node 3   │
└────┬────┴────┬─────┴────┬─────┘
     │         │          │
     └─────────┼──────────┘
               │
        Shared Redis/PostgreSQL
```

### Limits

| Component | Clean | Full |
|-----------|-------|------|
| Messages per AI | ~1000 | Unlimited |
| Concurrent requests | 1 | 100+ |
| Projects | Unlimited | Unlimited |
| Message size | 1MB | 10MB |

## Extension Points

### Adding New AIs

```python
# 1. Add to credentials
ANTHROPIC_API_KEY=...

# 2. Initialize client
if CREDENTIALS.get("anthropic"):
    AI_CLIENTS["anthropic"] = AnthropicClient(...)

# 3. Handle in router
if ai_name == "anthropic":
    response = call_anthropic(prompt, context)
```

### Custom Storage Backends

Implement the `StorageBackend` interface:

```python
class StorageBackend:
    async def get_context(project_id: str, ai_name: str) -> List[Dict]
    async def save_context(project_id: str, ai_name: str, messages: List[Dict])
    async def clear_context(project_id: str, ai_name: str)
```

## Monitoring & Debugging

### Debug Mode

```bash
# Enable debug logs
export LOG_LEVEL=debug

# View MCP communication
claude mcp logs mcp-ai-collab
```

### Health Checks

```bash
# Check system status
Use db_status

# Returns:
# ✓ Redis: Connected
# ✓ PostgreSQL: Connected
# Sessions: 5
# Messages: 127
```