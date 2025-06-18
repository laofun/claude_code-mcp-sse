#!/bin/bash

# MCP AI Collab - Full Installation with Redis/PostgreSQL

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Installing MCP AI Collab Server (Full Version)${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Installation directory
INSTALL_DIR="$HOME/.mcp-ai-collab"

# Backup existing installation if it exists
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Backing up existing installation...${NC}"
    mv "$INSTALL_DIR" "$INSTALL_DIR.backup.$(date +%s)"
fi

# Create directory
echo -e "${BLUE}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Copy server file
echo -e "${BLUE}Copying server...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cp "$SCRIPT_DIR/src/mcp_server_full.py" "$INSTALL_DIR/server.py"
chmod +x "$INSTALL_DIR/server.py"

# Create .env file from example if it doesn't exist
echo -e "${BLUE}Setting up environment...${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    # Copy .env.example from script directory
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env"
        echo -e "${YELLOW}⚠️  IMPORTANT: Edit $INSTALL_DIR/.env and add your API keys!${NC}"
        echo -e "${YELLOW}   Get your API keys from:${NC}"
        echo -e "${YELLOW}   - Gemini: https://aistudio.google.com/apikey${NC}"
        echo -e "${YELLOW}   - Grok: https://console.x.ai/${NC}"
        echo -e "${YELLOW}   - OpenAI: https://platform.openai.com/api-keys${NC}"
    else
        # Create a minimal .env file if .env.example doesn't exist
        cat > "$INSTALL_DIR/.env" << EOF
# Database Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=mcp_password
POSTGRES_DB=mcp_dev

# API Keys - ADD YOUR KEYS HERE
GEMINI_API_KEY=your-gemini-api-key-here
GROK_API_KEY=your-grok-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
EOF
        echo -e "${RED}❌ WARNING: No API keys configured!${NC}"
        echo -e "${YELLOW}   Edit $INSTALL_DIR/.env and add your API keys before using the server.${NC}"
    fi
else
    echo -e "${GREEN}✓ Using existing .env file${NC}"
fi

# Create run script
echo -e "${BLUE}Creating run script...${NC}"
cat > "$INSTALL_DIR/run.sh" << 'EOF'
#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

# Run the server
exec python3 "$DIR/server.py"
EOF

chmod +x "$INSTALL_DIR/run.sh"

# Install Python dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip3 install --quiet google-generativeai openai redis asyncpg

# Check if databases are running
echo -e "${BLUE}Checking databases...${NC}"

# Check Redis
if docker ps | grep -q "redis.*6379"; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${YELLOW}⚠ Redis not found. Starting it...${NC}"
    cd "$SCRIPT_DIR"
    docker-compose up -d redis
fi

# Check PostgreSQL
if docker ps | grep -q "postgres.*5432"; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL not found. Starting it...${NC}"
    cd "$SCRIPT_DIR"
    docker-compose up -d postgres
fi

# Wait for databases
echo -e "${BLUE}Waiting for databases to be ready...${NC}"
sleep 5

# Remove old MCP server if exists
echo -e "${BLUE}Removing old MCP server...${NC}"
claude mcp remove mcp-ai-collab --scope user 2>/dev/null || true

# Add to Claude Code
echo -e "${BLUE}Adding to Claude Code...${NC}"
claude mcp add mcp-ai-collab "$INSTALL_DIR/run.sh" --scope user

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo -e "${GREEN}Full version with Redis + PostgreSQL is ready!${NC}"
echo ""
echo "Features:"
echo "- Redis for fast context caching"
echo "- PostgreSQL for persistent storage"
echo "- Automatic session management"
echo "- Database-backed conversation history"
echo ""
echo "Test commands:"
echo "1. Use db_status to check database connections"
echo "2. Use ask_gemini to ask a question"
echo "3. Use show_context to see stored history"
echo ""
echo "Restart Claude Code to use the new server!"