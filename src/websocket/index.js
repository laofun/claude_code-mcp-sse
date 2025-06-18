const WebSocket = require('ws');
const Redis = require('ioredis');
const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config();

// Initialize Redis client
const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

// Initialize Express app for health checks
const app = express();
app.use(cors());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Start HTTP server
const PORT = process.env.WEBSOCKET_PORT || 3000;
const server = app.listen(PORT, () => {
  console.log(`WebSocket server listening on port ${PORT}`);
});

// Initialize WebSocket server
const wss = new WebSocket.Server({ server });

// Connected clients map
const clients = new Map();

// Redis pub/sub for multi-instance support
const subscriber = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');
const publisher = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

// Subscribe to Redis channels
subscriber.subscribe('mcp:updates', 'mcp:broadcasts');

subscriber.on('message', (channel, message) => {
  try {
    const data = JSON.parse(message);
    
    // Broadcast to all connected clients
    clients.forEach((client, clientId) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify({
          type: 'update',
          channel,
          data,
          timestamp: new Date().toISOString()
        }));
      }
    });
  } catch (err) {
    console.error('Error handling Redis message:', err);
  }
});

// WebSocket connection handler
wss.on('connection', (ws, req) => {
  const clientId = uuidv4();
  clients.set(clientId, ws);
  
  console.log(`Client connected: ${clientId}`);
  
  // Send welcome message
  ws.send(JSON.stringify({
    type: 'welcome',
    clientId,
    timestamp: new Date().toISOString()
  }));
  
  // Handle incoming messages
  ws.on('message', async (message) => {
    try {
      const data = JSON.parse(message);
      
      switch (data.type) {
        case 'subscribe':
          // Handle subscription to specific AI sessions
          await handleSubscribe(clientId, data.sessions);
          break;
          
        case 'ping':
          // Respond to ping with pong
          ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
          break;
          
        case 'context_update':
          // Publish context update to Redis
          await publisher.publish('mcp:updates', JSON.stringify({
            clientId,
            ...data
          }));
          break;
          
        default:
          console.log(`Unknown message type: ${data.type}`);
      }
    } catch (err) {
      console.error('Error handling WebSocket message:', err);
      ws.send(JSON.stringify({
        type: 'error',
        message: 'Invalid message format',
        timestamp: new Date().toISOString()
      }));
    }
  });
  
  // Handle client disconnect
  ws.on('close', () => {
    clients.delete(clientId);
    console.log(`Client disconnected: ${clientId}`);
  });
  
  // Handle errors
  ws.on('error', (error) => {
    console.error(`WebSocket error for client ${clientId}:`, error);
  });
});

// Handle subscription to AI sessions
async function handleSubscribe(clientId, sessions) {
  if (!Array.isArray(sessions)) return;
  
  // Store subscription info in Redis
  await redis.set(
    `ws:subscriptions:${clientId}`,
    JSON.stringify(sessions),
    'EX',
    3600 // Expire after 1 hour
  );
  
  // Send confirmation
  const client = clients.get(clientId);
  if (client && client.readyState === WebSocket.OPEN) {
    client.send(JSON.stringify({
      type: 'subscribed',
      sessions,
      timestamp: new Date().toISOString()
    }));
  }
}

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, closing connections...');
  
  // Close all WebSocket connections
  clients.forEach((client) => {
    client.close();
  });
  
  // Close Redis connections
  redis.disconnect();
  subscriber.disconnect();
  publisher.disconnect();
  
  // Close HTTP server
  server.close(() => {
    console.log('Server closed');
    process.exit(0);
  });
});

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection at:', promise, 'reason:', reason);
  process.exit(1);
});