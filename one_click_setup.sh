#!/bin/bash

# One-Click Setup Script for Enhanced MCP Server
# This script automates the entire setup process

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ASCII Art Banner
echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║     Enhanced MCP Server - AI Context Bridge Setup             ║
║        Give ALL AIs Memory in Claude Code!                    ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to display menu
display_menu() {
    echo -e "${BLUE}Please select installation type:${NC}"
    echo ""
    echo "1) Quick Install (Simple version - no databases)"
    echo "2) Full Install (With Redis + PostgreSQL)"
    echo "3) Docker Install (Everything in containers)"
    echo "4) Development Install (For contributors)"
    echo "5) Update Existing Installation"
    echo "6) Uninstall"
    echo ""
    read -p "Enter your choice (1-6): " choice
}

# Function to check dependencies
check_dependencies() {
    local missing_deps=()
    
    echo -e "${BLUE}Checking dependencies...${NC}"
    
    if ! command_exists python3; then
        missing_deps+=("python3")
    fi
    
    if ! command_exists pip3; then
        missing_deps+=("pip3")
    fi
    
    if ! command_exists claude; then
        missing_deps+=("claude")
    fi
    
    if [ "$1" == "docker" ] && ! command_exists docker; then
        missing_deps+=("docker")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo -e "${RED}Missing dependencies: ${missing_deps[*]}${NC}"
        echo ""
        echo "Please install the missing dependencies:"
        echo ""
        
        if [[ " ${missing_deps[@]} " =~ " python3 " ]] || [[ " ${missing_deps[@]} " =~ " pip3 " ]]; then
            echo "Python 3.8+: https://www.python.org/downloads/"
        fi
        
        if [[ " ${missing_deps[@]} " =~ " claude " ]]; then
            echo "Claude Code CLI: https://docs.anthropic.com/claude-code"
        fi
        
        if [[ " ${missing_deps[@]} " =~ " docker " ]]; then
            echo "Docker: https://docs.docker.com/get-docker/"
        fi
        
        exit 1
    fi
    
    echo -e "${GREEN}✓ All dependencies found${NC}"
}

# Function to setup API keys
setup_api_keys() {
    local env_file="$1"
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    API Key Configuration                       ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}Would you like to configure API keys now? (y/n)${NC}"
    read -p "> " configure_keys
    
    if [[ "$configure_keys" =~ ^[Yy]$ ]]; then
        echo ""
        echo "Leave blank to skip any API key you don't have yet."
        echo ""
        
        # Gemini
        echo -e "${BLUE}Gemini API Key (from https://aistudio.google.com/apikey):${NC}"
        read -p "> " gemini_key
        if [ ! -z "$gemini_key" ]; then
            sed -i.bak "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$gemini_key/" "$env_file"
        fi
        
        # Grok
        echo -e "${BLUE}Grok API Key (from https://console.x.ai/):${NC}"
        read -p "> " grok_key
        if [ ! -z "$grok_key" ]; then
            sed -i.bak "s/GROK_API_KEY=.*/GROK_API_KEY=$grok_key/" "$env_file"
        fi
        
        # OpenAI
        echo -e "${BLUE}OpenAI API Key (from https://platform.openai.com/api-keys):${NC}"
        read -p "> " openai_key
        if [ ! -z "$openai_key" ]; then
            sed -i.bak "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" "$env_file"
        fi
        
        # DeepSeek
        echo -e "${BLUE}DeepSeek API Key (from https://platform.deepseek.com/):${NC}"
        read -p "> " deepseek_key
        if [ ! -z "$deepseek_key" ]; then
            sed -i.bak "s/DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=$deepseek_key/" "$env_file"
        fi
        
        # Clean up backup files
        rm -f "$env_file.bak"
        
        echo ""
        echo -e "${GREEN}✓ API keys configured${NC}"
    else
        echo ""
        echo -e "${YELLOW}You can configure API keys later by editing:${NC}"
        echo -e "${YELLOW}$env_file${NC}"
    fi
}

# Quick Install Function
quick_install() {
    echo -e "${BLUE}Starting Quick Install...${NC}"
    check_dependencies
    
    # Run the simple installation script
    ./install_mcp_ai_collab.sh
    
    # Setup API keys
    INSTALL_DIR="$HOME/.mcp-ai-collab"
    if [ -f "$INSTALL_DIR/.env" ]; then
        setup_api_keys "$INSTALL_DIR/.env"
    fi
}

# Full Install Function
full_install() {
    echo -e "${BLUE}Starting Full Install...${NC}"
    check_dependencies
    
    # Check if Docker is available for databases
    if command_exists docker; then
        echo -e "${GREEN}✓ Docker found - will use containerized databases${NC}"
        
        # Start databases
        echo -e "${BLUE}Starting PostgreSQL and Redis...${NC}"
        docker-compose up -d postgres redis
        
        # Wait for databases
        echo -e "${BLUE}Waiting for databases to be ready...${NC}"
        sleep 10
    else
        echo -e "${YELLOW}⚠️  Docker not found. Please install PostgreSQL and Redis manually.${NC}"
        echo ""
        echo "Installation instructions:"
        echo ""
        echo "macOS:"
        echo "  brew install postgresql redis"
        echo "  brew services start postgresql redis"
        echo ""
        echo "Ubuntu/Debian:"
        echo "  sudo apt install postgresql redis-server"
        echo "  sudo systemctl start postgresql redis"
        echo ""
        read -p "Press Enter when databases are ready..."
    fi
    
    # Run the full installation script
    ./install_full.sh
    
    # Setup API keys
    INSTALL_DIR="$HOME/.mcp-ai-collab"
    if [ -f "$INSTALL_DIR/.env" ]; then
        setup_api_keys "$INSTALL_DIR/.env"
    fi
}

# Docker Install Function
docker_install() {
    echo -e "${BLUE}Starting Docker Install...${NC}"
    check_dependencies "docker"
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        cp .env.example .env
    fi
    
    # Setup API keys
    setup_api_keys ".env"
    
    # Build and start all services
    echo -e "${BLUE}Building and starting all services...${NC}"
    docker-compose up -d --build
    
    # Wait for services
    echo -e "${BLUE}Waiting for services to be ready...${NC}"
    sleep 15
    
    # Add to Claude Code
    echo -e "${BLUE}Adding to Claude Code...${NC}"
    claude mcp add mcp-ai-collab "docker exec -i mcp-server python /app/src/mcp_server_full.py --stdio" --scope user
    
    echo ""
    echo -e "${GREEN}✅ Docker installation complete!${NC}"
    echo ""
    echo "Services running:"
    echo "- PostgreSQL: localhost:5432"
    echo "- Redis: localhost:6379"
    echo "- MCP Server: localhost:8000"
    echo "- WebSocket Server: localhost:3000"
}

# Development Install Function
dev_install() {
    echo -e "${BLUE}Starting Development Install...${NC}"
    check_dependencies
    
    # Install Python dependencies
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    pip3 install -r requirements.txt
    pip3 install -r requirements-dev.txt 2>/dev/null || true
    
    # Install Node dependencies
    if [ -f "package.json" ]; then
        echo -e "${BLUE}Installing Node dependencies...${NC}"
        npm install
    fi
    
    # Setup pre-commit hooks
    if command_exists pre-commit; then
        echo -e "${BLUE}Setting up pre-commit hooks...${NC}"
        pre-commit install
    fi
    
    # Create .env file
    if [ ! -f ".env" ]; then
        cp .env.example .env
    fi
    
    # Setup API keys
    setup_api_keys ".env"
    
    # Create development directories
    mkdir -p logs data cache sessions
    
    echo ""
    echo -e "${GREEN}✅ Development environment ready!${NC}"
    echo ""
    echo "To run the server locally:"
    echo "  python src/main.py --stdio"
    echo ""
    echo "To run tests:"
    echo "  pytest"
}

# Update Installation Function
update_install() {
    echo -e "${BLUE}Updating existing installation...${NC}"
    
    # Detect installation type
    INSTALL_DIR="$HOME/.mcp-ai-collab"
    
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${GREEN}✓ Found installation at $INSTALL_DIR${NC}"
        
        # Backup current installation
        echo -e "${BLUE}Backing up current installation...${NC}"
        cp -r "$INSTALL_DIR" "$INSTALL_DIR.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Update files
        echo -e "${BLUE}Updating server files...${NC}"
        
        # Determine which server file to copy
        if [ -f "$INSTALL_DIR/server.py" ]; then
            # Check if it's the full or clean version
            if grep -q "redis" "$INSTALL_DIR/server.py"; then
                cp src/mcp_server_full.py "$INSTALL_DIR/server.py"
                echo -e "${GREEN}✓ Updated full version${NC}"
            else
                cp src/mcp_server_clean.py "$INSTALL_DIR/server.py"
                echo -e "${GREEN}✓ Updated clean version${NC}"
            fi
        fi
        
        # Update dependencies
        echo -e "${BLUE}Updating dependencies...${NC}"
        pip3 install --upgrade google-generativeai openai
        
        if grep -q "redis" "$INSTALL_DIR/server.py"; then
            pip3 install --upgrade redis asyncpg
        fi
        
        echo ""
        echo -e "${GREEN}✅ Update complete!${NC}"
        echo -e "${YELLOW}Restart Claude Code to use the updated server.${NC}"
    else
        echo -e "${RED}❌ No existing installation found at $INSTALL_DIR${NC}"
        echo -e "${YELLOW}Please run a fresh installation instead.${NC}"
    fi
}

# Uninstall Function
uninstall() {
    echo -e "${RED}Uninstalling Enhanced MCP Server...${NC}"
    echo ""
    echo -e "${YELLOW}This will remove:${NC}"
    echo "- MCP server from Claude Code"
    echo "- Installation directory at ~/.mcp-ai-collab"
    echo "- Docker containers (if using Docker install)"
    echo ""
    read -p "Are you sure? (y/N): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        # Remove from Claude Code
        echo -e "${BLUE}Removing from Claude Code...${NC}"
        claude mcp remove mcp-ai-collab --scope user 2>/dev/null || true
        
        # Remove installation directory
        INSTALL_DIR="$HOME/.mcp-ai-collab"
        if [ -d "$INSTALL_DIR" ]; then
            echo -e "${BLUE}Removing installation directory...${NC}"
            rm -rf "$INSTALL_DIR"
        fi
        
        # Stop Docker containers
        if command_exists docker && [ -f "docker-compose.yml" ]; then
            echo -e "${BLUE}Stopping Docker containers...${NC}"
            docker-compose down 2>/dev/null || true
        fi
        
        echo ""
        echo -e "${GREEN}✅ Uninstall complete!${NC}"
    else
        echo -e "${YELLOW}Uninstall cancelled.${NC}"
    fi
}

# Main execution
main() {
    # Get script directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    cd "$SCRIPT_DIR"
    
    # Display menu and get choice
    display_menu
    
    # Execute based on choice
    case $choice in
        1)
            quick_install
            ;;
        2)
            full_install
            ;;
        3)
            docker_install
            ;;
        4)
            dev_install
            ;;
        5)
            update_install
            ;;
        6)
            uninstall
            ;;
        *)
            echo -e "${RED}Invalid choice. Please run the script again.${NC}"
            exit 1
            ;;
    esac
    
    # Final instructions
    if [ "$choice" != "6" ]; then
        echo ""
        echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
        echo -e "${BLUE}                    Setup Complete!                             ${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
        echo ""
        echo -e "${GREEN}Next steps:${NC}"
        echo "1. Restart Claude Code"
        echo "2. Use /mcp to verify 'mcp-ai-collab' is listed"
        echo "3. Try asking Claude to use the AI tools!"
        echo ""
        echo -e "${YELLOW}Example commands:${NC}"
        echo '  "Claude, ask Gemini to help analyze this code"'
        echo '  "Have Grok review the architecture"'
        echo '  "Ask all AIs what they think about this approach"'
        echo ""
        echo -e "${GREEN}Enjoy your context-aware AI team! 🚀${NC}"
    fi
}

# Run main function
main