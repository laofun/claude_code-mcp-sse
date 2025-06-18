#!/usr/bin/env bash
set -e  # Exit immediately if a command exits with a non-zero status

# Pull the latest commit
echo "Pulling the latest commit..."
git pull



# Build Docker 
echo "Building and starting Docker containers..."
docker compose up --build -d --force-recreate mcp-sse-server

docker compose logs -f --tail=200 mcp-sse-server 

