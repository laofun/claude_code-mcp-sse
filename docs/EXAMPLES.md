# MCP AI Collab - Real-World Examples

## 🎯 Example Conversations

### Example 1: Debugging with Memory

```
Session 1 - Finding the Bug
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "I'm getting a TypeError: 
     Cannot read property 'id' of undefined in my React 
     component when I click the delete button"

Gemini: This TypeError typically occurs when you're trying to 
        access a property on an undefined object. In your delete 
        handler, check if:
        1. The item exists before accessing item.id
        2. The event handler is properly bound
        3. The item prop is being passed correctly
        
        Can you share your delete handler code?

You: Use ask_gemini with prompt "Here's my delete handler:
     const handleDelete = (item) => {
       dispatch(deleteItem(item.id));
     }"

Gemini: I see the issue. The delete handler looks correct, but 
        the error suggests 'item' is undefined when the function 
        is called. This usually happens when:
        
        1. The onClick is written as: onClick={handleDelete(item)}
           Instead of: onClick={() => handleDelete(item)}
        
        2. Or the item is undefined in the map function
        
        Check how you're calling handleDelete in your JSX.

Session 2 - Following Up (Next Day)
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "What was that React TypeError 
     we debugged yesterday?"

Gemini: Yesterday we debugged a "TypeError: Cannot read property 
        'id' of undefined" in your React delete button handler. 
        
        We found the issue was likely in how you were calling 
        the handler - using onClick={handleDelete(item)} instead 
        of onClick={() => handleDelete(item)}.
        
        Did that fix resolve your issue?
```

### Example 2: Code Review with Multiple AIs

```
Getting Different Perspectives
─────────────────────────────────────────────────────
You: Use ask_gemini to review this authentication middleware:
     
     const authMiddleware = (req, res, next) => {
       const token = req.headers.authorization;
       if (!token) return res.status(401).send('No token');
       
       const decoded = jwt.decode(token);
       req.user = decoded;
       next();
     }

Gemini: Security issues found:
        1. Using jwt.decode() instead of jwt.verify() - no signature validation!
        2. No try-catch for malformed tokens
        3. Not checking token expiration
        4. Should use Bearer token format
        5. No rate limiting

You: Use ask_grok with prompt "Gemini found security issues in my 
     auth middleware including no jwt.verify(). What else should I fix?"

Grok: Good catch by Gemini! Beyond those issues, also consider:
      1. Token refresh mechanism
      2. Blacklist for revoked tokens  
      3. Different token types (access vs refresh)
      4. CORS configuration
      5. Secure cookie storage option
      6. Audit logging for auth events

You: Use ask_openai with prompt "Based on Gemini and Grok's feedback,
     write a secure auth middleware"

ChatGPT: Here's a secure implementation incorporating all feedback:

         ```javascript
         const authMiddleware = async (req, res, next) => {
           try {
             const authHeader = req.headers.authorization;
             if (!authHeader?.startsWith('Bearer ')) {
               return res.status(401).json({ error: 'Invalid token format' });
             }
             
             const token = authHeader.substring(7);
             const decoded = jwt.verify(token, process.env.JWT_SECRET);
             
             // Check if token is blacklisted
             if (await isTokenBlacklisted(token)) {
               return res.status(401).json({ error: 'Token revoked' });
             }
             
             req.user = decoded;
             req.token = token;
             
             // Audit log
             logger.info(`Auth success for user ${decoded.userId}`);
             
             next();
           } catch (error) {
             logger.error(`Auth failed: ${error.message}`);
             
             if (error.name === 'TokenExpiredError') {
               return res.status(401).json({ error: 'Token expired' });
             }
             
             return res.status(403).json({ error: 'Invalid token' });
           }
         };
         ```
```

### Example 3: Learning Journey with Persistent Context

```
Day 1 - Learning Concept
─────────────────────────────────────────────────────
You: Use ask_gemini to explain Python decorators with examples

Gemini: Python decorators are a way to modify or enhance functions 
        without changing their code. Think of them as "wrappers":
        
        Basic example:
        ```python
        def timer_decorator(func):
            def wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                end = time.time()
                print(f"{func.__name__} took {end-start} seconds")
                return result
            return wrapper
        
        @timer_decorator
        def slow_function():
            time.sleep(1)
            return "Done"
        ```

Day 3 - Building on Knowledge
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "Can you show me a more advanced 
     decorator example? Maybe combining with what you showed before?"

Gemini: Building on the timer decorator I showed you earlier, here's 
        an advanced example combining multiple concepts:
        
        ```python
        def retry_with_timer(max_attempts=3, delay=1):
            def decorator(func):
                @timer_decorator  # Using our previous decorator!
                def wrapper(*args, **kwargs):
                    for attempt in range(max_attempts):
                        try:
                            return func(*args, **kwargs)
                        except Exception as e:
                            if attempt == max_attempts - 1:
                                raise
                            print(f"Attempt {attempt + 1} failed: {e}")
                            time.sleep(delay)
                return wrapper
            return decorator
        
        @retry_with_timer(max_attempts=3, delay=2)
        def flaky_api_call():
            # Simulated API call that might fail
            if random.random() < 0.7:
                raise ConnectionError("API timeout")
            return "Success"
        ```
        
        This combines our timer with retry logic and parameters!

Week Later - Applying Knowledge
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "I'm trying to create a decorator 
     for caching. Remember those decorator examples you showed me?"

Gemini: Yes! Building on the decorator patterns we've explored, 
        here's a caching decorator using the same principles:
        
        ```python
        def cache_decorator(ttl_seconds=60):
            def decorator(func):
                cache = {}
                cache_time = {}
                
                def wrapper(*args, **kwargs):
                    # Create cache key from arguments
                    key = str(args) + str(kwargs)
                    
                    # Check if cached and not expired
                    if key in cache:
                        if time.time() - cache_time[key] < ttl_seconds:
                            print(f"Cache hit for {func.__name__}")
                            return cache[key]
                    
                    # Call function and cache result
                    result = func(*args, **kwargs)
                    cache[key] = result
                    cache_time[key] = time.time()
                    
                    return result
                return wrapper
            return decorator
        ```
        
        This follows the same pattern as our timer and retry decorators!
```

### Example 4: Project Architecture Discussion

```
Initial Design Discussion
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "I'm building a real-time chat app 
     with React and Node.js. What architecture would you recommend?"

Gemini: For a real-time chat app, I recommend:

        Frontend (React):
        - React with Context API for state
        - Socket.io-client for real-time
        - React Router for navigation
        - Tailwind for styling
        
        Backend (Node.js):
        - Express.js server
        - Socket.io for WebSocket
        - MongoDB for messages
        - Redis for session/presence
        - JWT for authentication
        
        Key considerations:
        - Message delivery guarantees
        - Offline message queue
        - Typing indicators
        - Read receipts

A Week Later - Specific Implementation
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "Last week you suggested Redis 
     for presence in my chat app. How should I implement user 
     presence tracking?"

Gemini: Right, for the chat app architecture we discussed, here's 
        how to implement presence tracking with Redis:
        
        ```javascript
        // User comes online
        async function setUserOnline(userId, socketId) {
          const key = `presence:${userId}`;
          const data = {
            status: 'online',
            socketId,
            lastSeen: Date.now()
          };
          
          // Set with expiration (auto-offline after 5 min)
          await redis.setex(key, 300, JSON.stringify(data));
          
          // Add to online users set
          await redis.sadd('users:online', userId);
          
          // Publish status change
          await redis.publish('presence:updates', JSON.stringify({
            userId,
            status: 'online'
          }));
        }
        
        // Get online users
        async function getOnlineUsers() {
          const userIds = await redis.smembers('users:online');
          // Get detailed info for each user
          const users = await Promise.all(
            userIds.map(id => redis.get(`presence:${id}`))
          );
          return users.filter(Boolean).map(JSON.parse);
        }
        ```
        
        This builds on our previous architecture discussion!
```

### Example 5: Progressive Feature Development

```
Phase 1 - Initial Implementation
─────────────────────────────────────────────────────
You: Use ask_gemini to help implement a rate limiter for my API

Gemini: Here's a simple but effective rate limiter using Redis:

        ```javascript
        const rateLimiter = (maxRequests = 100, windowMs = 60000) => {
          return async (req, res, next) => {
            const key = `rate:${req.ip}`;
            const current = await redis.incr(key);
            
            if (current === 1) {
              await redis.expire(key, windowMs / 1000);
            }
            
            if (current > maxRequests) {
              return res.status(429).json({
                error: 'Too many requests'
              });
            }
            
            res.setHeader('X-RateLimit-Limit', maxRequests);
            res.setHeader('X-RateLimit-Remaining', maxRequests - current);
            
            next();
          };
        };
        ```

Phase 2 - Enhancement Request
─────────────────────────────────────────────────────
You: Use ask_gemini with prompt "Can we enhance the rate limiter 
     you helped me with to support different limits per endpoint?"

Gemini: Absolutely! Building on our previous rate limiter, here's 
        an enhanced version supporting per-endpoint limits:
        
        ```javascript
        const rateLimiter = (options = {}) => {
          const defaults = {
            windowMs: 60000,
            maxRequests: 100,
            keyGenerator: (req) => `rate:${req.ip}`,
            skip: (req) => false
          };
          
          const config = { ...defaults, ...options };
          
          return async (req, res, next) => {
            if (config.skip(req)) {
              return next();
            }
            
            const key = config.keyGenerator(req);
            const current = await redis.incr(key);
            
            if (current === 1) {
              await redis.expire(key, config.windowMs / 1000);
            }
            
            if (current > config.maxRequests) {
              return res.status(429).json({
                error: 'Too many requests',
                retryAfter: config.windowMs / 1000
              });
            }
            
            res.setHeader('X-RateLimit-Limit', config.maxRequests);
            res.setHeader('X-RateLimit-Remaining', 
                         config.maxRequests - current);
            
            next();
          };
        };
        
        // Usage with different limits:
        app.get('/api/search', rateLimiter({ maxRequests: 10 }), searchHandler);
        app.get('/api/data', rateLimiter({ maxRequests: 1000 }), dataHandler);
        app.post('/api/auth/login', rateLimiter({ 
          maxRequests: 5,
          keyGenerator: (req) => `rate:login:${req.ip}`
        }), loginHandler);
        ```
        
        This extends our original implementation with flexibility!
```

## 💡 Best Practices from Examples

### 1. Reference Previous Discussions
- "Based on what you suggested..."
- "Following up on our conversation about..."
- "Can you expand on the X example you gave?"

### 2. Build Knowledge Progressively
- Start with basic concepts
- Ask for enhancements later
- Reference previous implementations

### 3. Cross-Reference Between AIs
- "Gemini suggested X, what do you think?"
- "Grok mentioned Y, can you elaborate?"
- "Based on feedback from all AIs..."

### 4. Use Context for Debugging
- Share error messages in first conversation
- Reference the error in follow-ups
- Track what solutions you've tried

### 5. Maintain Project Context
- Mention your tech stack early
- Reference architectural decisions
- Build features incrementally

## 🎨 Creative Uses

### Code Golf Assistant
```
You: Use ask_gemini to help me golf this Python code:
     def fibonacci(n):
         if n <= 1:
             return n
         return fibonacci(n-1) + fibonacci(n-2)

Gemini: Here's a progressively golfed version:
        
        # Lambda version (43 chars)
        f=lambda n:n if n<2 else f(n-1)+f(n-2)
        
        # Using a list (35 chars)
        f=lambda n:[0,1,f(n-1)+f(n-2)][min(n,2)]

Next session:
You: Use ask_gemini with prompt "Can we golf that fibonacci 
     function further? You got it to 35 chars last time"

Gemini: Ah yes! We were at 35 chars. Here's an even shorter approach
        using Python 3.8+ walrus operator... [continues]
```

### Learning Path Tracker
```
You: Use ask_openai with prompt "I want to learn React. 
     Starting as a beginner. Track my progress."

ChatGPT: Welcome to your React journey! Let's start with:
         Week 1: JSX and Components
         - What is JSX
         - Function components
         - Props basics
         [creates learning plan]

[Two weeks later]
You: Use ask_openai with prompt "What React topics have I 
     covered and what's next?"

ChatGPT: Based on our conversations, you've covered:
         ✓ JSX and Components (Week 1)
         ✓ Props and State (Week 2)
         
         Next up: useEffect and API calls...
```

## 🚀 Advanced Patterns

### Pattern 1: AI Pair Programming
```
You: Use ask_gemini as my pair programmer for implementing 
     binary search

[Work through implementation together across multiple messages]

You: Use ask_gemini to review our complete binary search 
     implementation
```

### Pattern 2: Architecture Evolution
```
Day 1: "Design a simple blog API"
Week 2: "Add authentication to our blog API"  
Month 2: "Scale our blog API for 1M users"

Each conversation builds on previous decisions!
```

### Pattern 3: Debugging Detective
```
"Error X appeared"
"Tried solution Y, now getting error Z"
"That worked! Document the complete fix"

The AI maintains the full debugging context!
```

## 📈 Results You Can Expect

With persistent memory, your AI assistants become:
- **More Helpful**: They remember your project details
- **More Efficient**: No need to re-explain context
- **More Accurate**: They track what's been tried
- **More Personal**: They learn your style and preferences

Start using MCP AI Collab today and experience the difference!