# MCP AI Collab - Comprehensive Troubleshooting Guide

## Table of Contents
- [Installation Issues](#installation-issues)
- [API Key Problems](#api-key-problems)
- [Connection Errors](#connection-errors)
- [Context/Memory Issues](#contextmemory-issues)
- [Performance Problems](#performance-problems)
- [Database Issues (Full Version)](#database-issues-full-version)
- [Common Error Messages](#common-error-messages)
- [Debug Mode](#debug-mode)

## Installation Issues

### ❌ Error: "Permission denied" when running setup script

**Symptom:**
```bash
$ ./one_click_setup.sh
bash: ./one_click_setup.sh: Permission denied
```

**Solution:**
```bash
# Make the script executable
chmod +x one_click_setup.sh
chmod +x install_*.sh

# Then run again
./one_click_setup.sh
```

### ❌ Error: "Python 3.8+ is required"

**Symptom:**
```
Python 3.8+ is required but Python 3.7.x was found
```

**Solution:**
```bash
# macOS
brew install python@3.11
brew link python@3.11

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-pip

# Verify
python3 --version
```

### ❌ Error: "claude: command not found"

**Symptom:**
```bash
$ claude mcp add
bash: claude: command not found
```

**Solution:**
1. Ensure Claude Code is installed
2. Add Claude to PATH:
```bash
# Find claude location
find ~ -name "claude" -type f 2>/dev/null

# Add to PATH (example for macOS)
echo 'export PATH="/Applications/Claude.app/Contents/MacOS:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## API Key Problems

### ❌ Error: "API key not found for gemini"

**Symptom:**
```
Error: gemini not configured. Set GEMINI_API_KEY
```

**Solution:**
1. Check if API key is set:
```bash
cat ~/.mcp-ai-collab/.env | grep GEMINI_API_KEY
```

2. If missing or incorrect:
```bash
# Edit the .env file
nano ~/.mcp-ai-collab/.env

# Add your key
GEMINI_API_KEY=your-actual-api-key-here

# Save and exit (Ctrl+X, Y, Enter)
```

3. Restart Claude Code completely

### ❌ Error: "Invalid API key"

**Symptom:**
```
Error calling gemini: 400 API key not valid
```

**Solution:**
1. Verify API key is correct:
   - Go to [Google AI Studio](https://aistudio.google.com/apikey)
   - Generate a new key if needed
   - Copy the entire key (no spaces)

2. Common mistakes to avoid:
   - Don't include quotes around the key
   - Don't add spaces before/after the = sign
   - Ensure no trailing newlines

Correct format:
```bash
GEMINI_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz
```

### ❌ Error: "Rate limit exceeded"

**Symptom:**
```
Error calling openai: Rate limit exceeded
```

**Solution:**
1. Check your API usage on provider dashboard
2. Upgrade to a paid tier if needed
3. Implement rate limiting in your requests
4. Use different AI for non-critical tasks

## Connection Errors

### ❌ Error: "Server not responding"

**Symptom:**
Claude Code shows "mcp-ai-collab: disconnected"

**Solution:**
1. Check if server is registered:
```bash
claude mcp list --scope user
```

2. Re-register if missing:
```bash
claude mcp remove mcp-ai-collab --scope user
claude mcp add mcp-ai-collab "$HOME/.mcp-ai-collab/run.sh" --scope user
```

3. Check server logs:
```bash
# Find Claude Code logs
~/Library/Logs/Claude/
# or
~/.config/Claude/logs/
```

### ❌ Error: "Connection refused"

**Symptom:**
```
Error: connect ECONNREFUSED 127.0.0.1:6379
```

**Solution (Full version with Redis):
```bash
# Check if Redis is running
redis-cli ping

# If not, start Redis
# Docker
docker-compose up -d redis

# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

## Context/Memory Issues

### ❌ Problem: AI doesn't remember previous conversations

**Diagnosis Steps:**
1. Check current project hash:
```bash
pwd | md5sum
# or on macOS
pwd | md5
```

2. Verify context directory exists:
```bash
ls -la ~/.mcp-ai-collab/contexts/
```

3. Check if context file exists:
```bash
ls -la ~/.mcp-ai-collab/contexts/*/gemini_context.json
```

**Solutions:**
- Ensure you're in the same project directory
- Check file permissions:
```bash
chmod -R 755 ~/.mcp-ai-collab/
```
- Clear corrupted context:
```bash
rm -rf ~/.mcp-ai-collab/contexts/[project-hash]/
```

### ❌ Problem: Context gets mixed between projects

**Symptom:**
AI references conversations from different projects

**Solution:**
1. Clear all contexts:
```bash
rm -rf ~/.mcp-ai-collab/contexts/*
```

2. Verify project isolation:
```bash
# In project A
pwd && pwd | md5sum

# In project B
pwd && pwd | md5sum

# Hashes should be different
```

## Performance Problems

### ❌ Problem: Slow response times

**Diagnosis:**
```bash
# Check system resources
top
# or
htop

# Check Python process
ps aux | grep mcp_server
```

**Solutions:**

1. **Clean Version**: 
   - Reduce context size (auto-prunes to 20 messages)
   - Clear old contexts:
   ```bash
   find ~/.mcp-ai-collab/contexts -mtime +30 -delete
   ```

2. **Full Version**:
   - Check Redis performance:
   ```bash
   redis-cli --latency
   ```
   - Optimize PostgreSQL:
   ```sql
   VACUUM ANALYZE ai_messages;
   ```

### ❌ Problem: High memory usage

**Solution:**
1. Restart the server (automatic via Claude Code)
2. Use Clean version instead of Full version
3. Limit context retention

## Database Issues (Full Version)

### ❌ Error: "PostgreSQL connection failed"

**Symptom:**
```
Error: connection to server at "localhost" (::1), port 5432 failed
```

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres
# or
pg_isready

# Start PostgreSQL
docker-compose up -d postgres
# or
brew services start postgresql
```

### ❌ Error: "Database does not exist"

**Solution:**
```bash
# Create database
docker exec -it postgres psql -U postgres -c "CREATE DATABASE mcp_dev;"

# Or manually
psql -U postgres
CREATE DATABASE mcp_dev;
CREATE USER mcp_user WITH PASSWORD 'mcp_password';
GRANT ALL PRIVILEGES ON DATABASE mcp_dev TO mcp_user;
```

### ❌ Problem: Redis cache not working

**Diagnosis:**
```bash
# Test Redis connection
redis-cli
> PING
PONG
> INFO server
```

**Solution:**
```bash
# Clear Redis cache
redis-cli FLUSHDB

# Check Redis config
redis-cli CONFIG GET maxmemory
```

## Common Error Messages

### MCP Protocol Errors

| Error Code | Meaning | Solution |
|------------|---------|----------|
| -32700 | Parse error | Check JSON formatting in requests |
| -32601 | Method not found | Update to latest version |
| -32602 | Invalid params | Check tool parameter names |
| -32603 | Internal error | Check server logs |

### API-Specific Errors

| Error | Meaning | Solution |
|-------|---------|----------|
| 400 | Bad request | Check API key and parameters |
| 401 | Unauthorized | Verify API key is valid |
| 429 | Rate limited | Wait or upgrade plan |
| 500 | Server error | Try again later |

## Debug Mode

### Enable Detailed Logging

1. Set environment variable:
```bash
export MCP_DEBUG=true
export LOG_LEVEL=DEBUG
```

2. Run server manually for debugging:
```bash
cd ~/.mcp-ai-collab
python3 server.py
```

3. Watch logs in real-time:
```bash
tail -f ~/Library/Logs/Claude/*.log
```

### Test Server Directly

Create a test script:
```python
# test_server.py
import subprocess
import json

# Test initialize
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {}
}

proc = subprocess.Popen(
    ['python3', 'server.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

response = proc.communicate(json.dumps(request) + '\n')[0]
print(response)
```

### Check Server Health

```bash
# Full version with database
curl -X POST http://localhost:8000/health

# Check all components
echo "Redis:" && redis-cli ping
echo "PostgreSQL:" && pg_isready
echo "Server:" && ps aux | grep mcp_server
```

## Getting Help

If none of these solutions work:

1. **Collect Debug Information:**
```bash
# System info
uname -a
python3 --version
claude --version

# Error logs
tail -n 100 ~/Library/Logs/Claude/*.log > debug.log

# Configuration
cat ~/.mcp-ai-collab/.env | grep -v API_KEY > config.log
```

2. **Open an Issue:**
- Go to [GitHub Issues](https://github.com/RaiAnsar/claude_code-coding-mcp/issues)
- Include debug information
- Describe steps to reproduce
- **Never include API keys!**

3. **Community Support:**
- Check [Discussions](https://github.com/RaiAnsar/claude_code-coding-mcp/discussions)
- Search existing issues
- Ask in Claude Code community

## Prevention Tips

1. **Regular Maintenance:**
```bash
# Weekly cleanup
find ~/.mcp-ai-collab/contexts -mtime +30 -delete

# Monthly update
cd claude_code-coding-mcp
git pull
./one_click_setup.sh  # Choose update option
```

2. **Backup Contexts:**
```bash
# Backup important contexts
tar -czf mcp-contexts-backup.tar.gz ~/.mcp-ai-collab/contexts/

# Restore if needed
tar -xzf mcp-contexts-backup.tar.gz -C ~/
```

3. **Monitor Usage:**
- Check API usage regularly
- Set up billing alerts
- Rotate API keys periodically