# 🚀 MCP AI Collab - Quick Start Guide

## 🎯 5-Minute Setup

### Step 1: Clone & Install

```bash
# Clone the repository
git clone https://github.com/RaiAnsar/claude_code-coding-mcp.git
cd claude_code-coding-mcp

# Run the installer
./one_click_setup.sh
```

### Step 2: Choose Your Setup

```
Please select installation type:

1) Quick Install (Simple version - no databases) ← Start here!
2) Full Install (With Redis + PostgreSQL)
3) Docker Install (Everything in containers)
```

**First time? Choose option 1!**

### Step 3: Add Your API Keys

The installer will ask for your API keys. You need at least one:

```
Gemini API Key (from https://aistudio.google.com/apikey):
> AIzaSyYourActualKeyHere

Grok API Key (from https://console.x.ai/):
> [Press Enter to skip]

OpenAI API Key (from https://platform.openai.com/api-keys):
> [Press Enter to skip]
```

### Step 4: Restart Claude Code

Close and reopen Claude Code completely.

### Step 5: Verify Installation

In Claude Code, type:
```
/mcp
```

You should see `mcp-ai-collab` in the list!

## 🎮 Your First AI Conversation with Memory

### Example 1: Basic Memory Test

```bash
# First message
You: Use ask_gemini with prompt "Hi! My name is Alex and I'm working on a Python web app"
Gemini: Hello Alex! Nice to meet you. I'd be happy to help with your Python web app...

# Later (even after closing Claude Code!)
You: Use ask_gemini with prompt "What's my name and what am I working on?"
Gemini: Your name is Alex, and you're working on a Python web app...
```

### Example 2: Code Review with Context

```bash
# Initial review
You: Use ask_gemini to review this authentication code:
```python
def login(username, password):
    user = db.get_user(username)
    if user and user.password == password:
        return create_token(user)
```

Gemini: I see several security issues:
1. Passwords appear to be stored in plain text
2. No rate limiting for login attempts
3. No password complexity validation...

# Follow-up question
You: Use ask_gemini with prompt "What was the first security issue you mentioned?"
Gemini: The first security issue I mentioned was that passwords appear to be stored in plain text instead of being hashed...
```

### Example 3: Multi-AI Collaboration

```bash
# Get different perspectives
You: Use ask_gemini for security review of this API endpoint
You: Use ask_grok for performance optimization suggestions  
You: Use ask_openai for best practices and code style

# Later, check what each AI said
You: Use show_context with ai "gemini"
You: Use show_context with ai "grok"
You: Use show_context with ai "openai"
```

## 📚 Common Use Cases

### 1. Debugging Assistant

```bash
# First encounter with bug
You: Use ask_gemini with prompt "I'm getting 'KeyError: user_id' in my Flask app"
Gemini: This error typically occurs when... Let me help you debug...

# After trying some fixes
You: Use ask_gemini with prompt "The KeyError is gone but now I'm getting a 401"
Gemini: Based on our previous debugging of the KeyError, the 401 might be related...
```

### 2. Learning Assistant

```bash
# Learning session
You: Use ask_gemini to explain Python decorators with examples
Gemini: [Detailed explanation with examples]

# Next day
You: Use ask_gemini with prompt "Can you show me that decorator example you gave yesterday?"
Gemini: Yesterday I showed you this decorator example...
```

### 3. Project Documentation Helper

```bash
# Document as you code
You: Use ask_openai with prompt "I just added user authentication using JWT"
ChatGPT: Noted! You've implemented JWT authentication...

# Later when writing docs
You: Use ask_openai to summarize all the features I've mentioned adding
ChatGPT: Based on our conversations, you've added: 1) JWT authentication...
```

## 🛠️ Essential Commands

### Basic AI Interaction

```bash
# Ask any AI with memory
Use ask_gemini with prompt "your question here"
Use ask_grok with prompt "your question here"
Use ask_openai with prompt "your question here"

# With custom temperature (0=focused, 1=creative)
Use ask_gemini with prompt "write a poem" and temperature 0.9
```

### Context Management

```bash
# View conversation history
Use show_context with ai "gemini"

# Clear history for fresh start
Use clear_context with ai "gemini"     # Clear one AI
Use clear_context with ai "all"        # Clear all AIs

# Check system status (Full version only)
Use db_status
```

## 💡 Pro Tips

### 1. Project-Specific Memory

Each project directory has its own AI memory:

```bash
~/project-a/
  └─ Gemini remembers: "Working on e-commerce site"

~/project-b/
  └─ Gemini remembers: "Building mobile app API"
```

### 2. Effective Prompting

```bash
# ❌ Vague
Use ask_gemini with prompt "fix this"

# ✅ Specific with context
Use ask_gemini with prompt "fix the SQL injection vulnerability we discussed in the login function"
```

### 3. Collaborative Debugging

```bash
# Start with one AI
Use ask_gemini to help debug this WebSocket connection issue

# If stuck, get second opinion
Use ask_grok with prompt "Gemini and I tried X and Y for WebSocket issue, any other ideas?"
```

### 4. Building on Previous Conversations

```bash
# Reference previous discussions
"Based on our earlier conversation about..."
"Following up on your suggestion to..."
"As you mentioned before..."
```

## 🔧 Switching Between Versions

### Upgrade to Full Version

If you need Redis/PostgreSQL features:

```bash
./one_click_setup.sh
# Choose option 2 (Full Install)
```

### Downgrade to Simple Version

If you want to go back to file-based:

```bash
./one_click_setup.sh
# Choose option 1 (Quick Install)
```

Your conversation history is preserved when switching!

## 🆘 Quick Troubleshooting

### "API key not found"
```bash
# Edit your .env file
nano ~/.mcp-ai-collab/.env
# Add: GEMINI_API_KEY=your-key-here
# Restart Claude Code
```

### "Server not connected"
```bash
# Re-run installation
./install_mcp_ai_collab.sh
# Restart Claude Code
```

### AI doesn't remember anything
```bash
# Check you're in the same project directory
pwd
# Clear corrupted context
Use clear_context with ai "all"
```

## 📺 Visual Examples

### What Success Looks Like

```
Claude Code:
┌────────────────────────────────────────┐
│ You: Use ask_gemini with prompt        │
│      "What's the bug we found?"        │
│                                        │
│ Gemini: Earlier we identified a race   │
│ condition in the user registration     │
│ endpoint when...                       │
│                                        │
│ You: Use ask_gemini to show the fix   │
│                                        │
│ Gemini: For the race condition, I     │
│ suggested using database constraints   │
│ and this transaction pattern...        │
└────────────────────────────────────────┘
```

### Command Patterns

```bash
# Pattern 1: Simple question
Use ask_[ai] with prompt "[question]"

# Pattern 2: With temperature
Use ask_[ai] with prompt "[question]" and temperature [0-1]

# Pattern 3: Context management
Use show_context with ai "[ai_name]"
Use clear_context with ai "[ai_name|all]"
```

## 🎉 Next Steps

1. **Try Different AIs**: Each has unique strengths
   - Gemini: Great for coding and technical explanations
   - Grok: Excellent for creative solutions and humor
   - ChatGPT: Best for general tasks and documentation

2. **Explore Advanced Features**:
   - Check out the [Full Version](ARCHITECTURE.md) for database features
   - Read [Troubleshooting Guide](TROUBLESHOOTING.md) for more tips
   - See [Security Guide](../SECURITY.md) for best practices

3. **Join the Community**:
   - Share your use cases
   - Request features
   - Report issues

Happy coding with your new AI team! 🚀