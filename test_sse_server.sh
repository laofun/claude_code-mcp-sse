#!/bin/bash

# Test script for MCP SSE Server
# This script tests all SSE server endpoints

set -e

PORT=${SSE_PORT:-8001}
BASE_URL="http://localhost:$PORT"

echo "🧪 Testing MCP SSE Server on $BASE_URL"
echo ""

# Test 1: Basic server info
echo "📋 Test 1: Server Info"
echo "curl $BASE_URL/"
response=$(curl -s "$BASE_URL/" || echo "FAILED")
if [[ $response == *"MCP SSE Server"* ]]; then
    echo "✅ Server info endpoint working"
    echo "Response: $response"
else
    echo "❌ Server info endpoint failed"
    echo "Response: $response"
    exit 1
fi
echo ""

# Test 2: Health check
echo "🏥 Test 2: Health Check"
echo "curl $BASE_URL/health"
health_response=$(curl -s "$BASE_URL/health" || echo "FAILED")
if [[ $health_response == *"healthy"* ]]; then
    echo "✅ Health check endpoint working"
    echo "Response: $health_response"
else
    echo "❌ Health check endpoint failed"
    echo "Response: $health_response"
fi
echo ""

# Test 3: SSE Connection (quick test)
echo "🔄 Test 3: SSE Stream (5 second test)"
echo "curl -N -H 'Accept: text/event-stream' $BASE_URL/sse"
echo "Testing for 5 seconds..."

timeout 5s curl -N -H "Accept: text/event-stream" "$BASE_URL/sse" 2>/dev/null | head -10 > /tmp/sse_test.log || true

if [ -s /tmp/sse_test.log ]; then
    echo "✅ SSE endpoint working"
    echo "Sample events received:"
    cat /tmp/sse_test.log | head -5
    rm -f /tmp/sse_test.log
else
    echo "❌ SSE endpoint failed"
fi
echo ""

# Test 4: Context endpoint
echo "📚 Test 4: Context Storage"
echo "curl $BASE_URL/contexts"
contexts_response=$(curl -s "$BASE_URL/contexts" || echo "FAILED")
if [[ $contexts_response == *"contexts"* ]]; then
    echo "✅ Context endpoint working"
    echo "Response: $contexts_response"
else
    echo "❌ Context endpoint failed"
    echo "Response: $contexts_response"
fi
echo ""

# Test 5: MCP Protocol endpoints
echo "🔌 Test 5: MCP Protocol Support"
echo "Testing MCP initialize endpoint..."
mcp_init_data='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'
mcp_response=$(curl -s -X POST -H "Content-Type: application/json" -d "$mcp_init_data" "$BASE_URL/mcp/initialize" || echo "FAILED")
if [[ $mcp_response == *"protocolVersion"* ]]; then
    echo "✅ MCP initialize endpoint working"
    echo "Response: $mcp_response"
else
    echo "❌ MCP initialize endpoint failed"
    echo "Response: $mcp_response"
fi
echo ""

echo "🎉 SSE Server test completed!"
echo ""
echo "📖 Usage Examples:"
echo "  Start server:     ./start_sse_server.sh"
echo "  Server info:      curl $BASE_URL/"
echo "  Health check:     curl $BASE_URL/health"
echo "  SSE stream:       curl -N -H 'Accept: text/event-stream' $BASE_URL/sse"
echo "  Browse contexts:  curl $BASE_URL/contexts"