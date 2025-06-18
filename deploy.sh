#!/bin/bash

# MCP AI Collab - Deployment Script
# This script pulls the latest code and deploys using Docker

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check required commands
print_status "Checking required commands..."

if ! command_exists git; then
    print_error "Git is not installed. Please install Git first."
    exit 1
fi

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "All required commands are available"

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found!"
    if [ -f ".env.example" ]; then
        print_status "Copying .env.example to .env..."
        cp .env.example .env
        print_warning "Please edit .env file with your actual API keys and configuration before continuing."
        read -p "Press Enter after editing .env file, or Ctrl+C to cancel..."
    else
        print_error ".env.example file not found. Cannot create .env file."
        exit 1
    fi
fi

# Pull latest code
print_status "Pulling latest code from repository..."
git stash push -m "Auto-stash before deploy $(date)"
git pull origin main
if [ $? -ne 0 ]; then
    print_error "Failed to pull latest code"
    exit 1
fi
print_success "Code updated successfully"

# Stop existing containers
print_status "Stopping existing containers..."
docker-compose down
print_success "Containers stopped"

# Remove old images (optional - uncomment if you want to force rebuild)
# print_status "Removing old images..."
# docker-compose down --rmi all
# docker system prune -f

# Build and start containers
print_status "Building and starting containers..."
docker-compose up --build -d

if [ $? -ne 0 ]; then
    print_error "Failed to start containers"
    exit 1
fi

# Wait for services to be healthy
print_status "Waiting for services to be healthy..."
sleep 10

# Check service health
print_status "Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U mcp_user >/dev/null 2>&1; then
    print_success "PostgreSQL is healthy"
else
    print_warning "PostgreSQL health check failed"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    print_success "Redis is healthy"
else
    print_warning "Redis health check failed"
fi

# Check MCP Server
if curl -f http://localhost:${MCP_PORT:-8000}/health >/dev/null 2>&1; then
    print_success "MCP Server is healthy"
else
    print_warning "MCP Server health check failed - it may still be starting up"
fi

# Check WebSocket Server
if curl -f http://localhost:${WEBSOCKET_PORT:-3000}/health >/dev/null 2>&1; then
    print_success "WebSocket Server is healthy"
else
    print_warning "WebSocket Server health check failed - it may still be starting up"
fi

# Display running containers
print_status "Running containers:"
docker-compose ps

# Display logs
print_status "Recent logs (last 20 lines):"
docker-compose logs --tail=20

print_success "Deployment completed!"
print_status "Services are available at:"
echo "  - MCP Server: http://localhost:${MCP_PORT:-8000}"
echo "  - WebSocket Server: http://localhost:${WEBSOCKET_PORT:-3000}"
echo ""
print_status "To view logs: docker-compose logs -f"
print_status "To stop services: docker-compose down"
print_status "To restart services: docker-compose restart"