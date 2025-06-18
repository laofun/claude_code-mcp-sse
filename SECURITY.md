# Security & Privacy Policy

## 🔒 Your API Keys Are 100% Safe

**We understand your concern about API key security. Here's exactly how we protect them:**

## How Your Keys Are Protected

### 1. Local Storage Only
```bash
# Your keys are stored in .env file on YOUR machine
~/.mcp-ai-collab/.env

# They are ONLY used for official API calls:
- https://generativelanguage.googleapis.com (Gemini)
- https://api.x.ai (Grok)  
- https://api.openai.com (ChatGPT)
```

### 2. Complete Transparency
- **100% Open Source** - Every line of code is visible
- **No Hidden Code** - No compiled binaries or obfuscated scripts
- **Verify Yourself** - Search our entire codebase:

```bash
# Check if we send keys anywhere suspicious
grep -r "http" src/ | grep -v "googleapis\|openai\|x.ai"
# Result: Nothing found - we only call official APIs
```

### 3. What We DON'T Do
- ❌ **No Analytics** - We don't track usage
- ❌ **No Telemetry** - No phoning home
- ❌ **No Backend** - We have no servers to steal keys
- ❌ **No Validation** - We don't "check" your keys
- ❌ **No Logging** - Keys never appear in logs

## Verify Our Security Claims

### 1. Audit the Code
```bash
# Search for any external URLs
find . -name "*.py" -exec grep -l "requests\|http\|post\|get" {} \;

# Check each file - you'll see only official API endpoints
```

### 2. Monitor Network Traffic
```bash
# Run this while using the server
netstat -an | grep ESTABLISHED

# You'll only see connections to:
# - googleapis.com:443 (Gemini)
# - api.x.ai:443 (Grok)
# - api.openai.com:443 (ChatGPT)
```

### 3. Check Process Behavior
```bash
# See what files the process accesses
lsof -p $(pgrep -f mcp_server)

# Results show only:
# - Your .env file (read once at startup)
# - Local context storage
# - Standard Python libraries
```

## Security Architecture

```
Your Computer
│
├── .env file (your API keys)
│   ├── Only readable by you (chmod 600)
│   ├── Never transmitted anywhere
│   └── Loaded once at startup
│
├── MCP AI Collab Server
│   ├── Reads .env file
│   ├── Stores contexts locally
│   └── Makes HTTPS calls to official APIs only
│
└── Network Connections (HTTPS only)
    ├── → googleapis.com (Google's servers)
    ├── → api.x.ai (X.AI's servers)
    └── → api.openai.com (OpenAI's servers)
```

## Best Practices for Maximum Security

### 1. Protect Your .env File
```bash
# Set restrictive permissions
chmod 600 ~/.mcp-ai-collab/.env

# Verify permissions
ls -la ~/.mcp-ai-collab/.env
# Should show: -rw------- (only you can read/write)
```

### 2. Use API Key Restrictions
- **Gemini**: Set per-project quotas in Google AI Studio
- **OpenAI**: Set monthly spend limits
- **Grok**: Monitor usage in X.AI console

### 3. Regular Security Checks
```bash
# Check for unauthorized access
last | grep -v "your-username"

# Review API usage on provider dashboards
# Set up alerts for unusual activity
```

## Common Security Questions

**Q: Can you see my API keys?**  
A: No. We have no servers, no analytics, no way to see anything on your machine.

**Q: What if someone hacks your GitHub?**  
A: They can't get your keys - they're only on your machine, not in our code.

**Q: Do you store my conversations?**  
A: Only locally on your machine in `~/.mcp-ai-collab/contexts/`

**Q: Can I verify the binaries?**  
A: There are no binaries! It's pure Python - you can read every line.

**Q: What about dependencies?**  
A: We only use well-known libraries (openai, google-generativeai) from PyPI.

## Reporting Security Issues

Found a security concern? Please report it:

**Email**: raiworks.ai@gmail.com  
**Subject**: [SECURITY] MCP AI Collab

Include:
- Description of the issue
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We'll respond within 48 hours and credit you in the fix.

## Security Audit Checklist

- [x] **No Hardcoded Secrets** - Verified ✓
- [x] **Environment Variables Only** - Verified ✓
- [x] **No External Services** - Verified ✓
- [x] **No Analytics/Telemetry** - Verified ✓
- [x] **Secure File Permissions** - Documented ✓
- [x] **HTTPS Only** - All API calls use TLS ✓
- [x] **Open Source** - Full transparency ✓

## Third-Party Security Audits

We welcome security audits! If you're a security researcher:

1. Clone the repository
2. Audit the code
3. Run in an isolated environment
4. Report findings via email

## Legal

This software is provided "as is" under the MIT License. We've taken every precaution to ensure security, but you're responsible for protecting your own API keys and data.