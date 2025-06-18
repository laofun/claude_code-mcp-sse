# Version Comparison Guide

## Overview

MCP AI Collab offers three versions to match different needs. This guide helps you choose the right one.

## Quick Decision Matrix

| Your Situation | Recommended Version |
|----------------|-------------------|
| Individual developer, want to start quickly | **Clean** |
| Team/production environment | **Full** |
| Learning MCP protocol | **Standalone** |
| Need high performance | **Full** |
| Limited system resources | **Clean** |
| Want minimal dependencies | **Standalone** |

## Detailed Comparison

### Clean Version (`mcp_server_clean.py`)

**What it is:** The recommended starting point for most users.

**Features:**
- ✅ File-based storage (JSON)
- ✅ No external dependencies
- ✅ 1-minute setup
- ✅ Works immediately
- ✅ Project-based isolation
- ✅ Supports all three AIs

**Storage:** `~/.mcp-ai-collab/contexts/[project-id]/[ai-name].json`

**Best for:**
- Individual developers
- Quick prototyping
- Small to medium projects
- Getting started quickly

**Limitations:**
- Single-user only
- No concurrent access handling
- Limited to ~1000 messages per AI efficiently

### Full Version (`mcp_server_full.py`)

**What it is:** Production-ready version with enterprise features.

**Features:**
- ✅ Redis for fast caching
- ✅ PostgreSQL for unlimited storage
- ✅ Concurrent access support
- ✅ Database transactions
- ✅ Performance monitoring
- ✅ Scalable architecture

**Storage:** 
- Redis: Last 10 messages per session (1-hour cache)
- PostgreSQL: Complete conversation history

**Best for:**
- Teams and organizations
- Production deployments
- High-traffic usage
- Long-term context storage
- Performance-critical applications

**Requirements:**
- Docker or manual Redis/PostgreSQL setup
- ~200MB RAM for databases
- ~100MB disk space

### Standalone Version (`mcp_standalone.py`)

**What it is:** Minimal implementation for learning and development.

**Features:**
- ✅ Single file implementation
- ✅ Minimal dependencies
- ✅ Easy to understand
- ✅ Good for customization
- ✅ Educational purposes

**Best for:**
- Learning MCP protocol
- Building custom solutions
- Debugging and testing
- Minimal installations

## Performance Comparison

| Metric | Clean | Full | Standalone |
|--------|-------|------|-------------|
| Startup time | <1s | 2-3s | <1s |
| Response time | 10-50ms | 5-20ms | 10-50ms |
| Max conversations | ~100 | Unlimited | ~100 |
| Concurrent users | 1 | Many | 1 |
| Memory usage | 50MB | 200MB | 30MB |

## Migration Paths

### Clean → Full

1. Export contexts: `python3 export_contexts.py`
2. Install Full version
3. Import contexts: `python3 import_contexts.py`

### Full → Clean

1. Use built-in export tool
2. Install Clean version
3. Copy JSON files to new location

## Frequently Asked Questions

**Q: Can I switch versions later?**  
A: Yes! We provide migration tools.

**Q: Which is most reliable?**  
A: All versions are reliable. Full version has redundancy.

**Q: Do all versions support the same features?**  
A: Yes, core features are identical. Full adds performance and scalability.

**Q: Which version do you use?**  
A: We use Full for development, Clean for quick tests.

## Recommendation Flow

```
Start here → Do you need team collaboration?
                 ├─ Yes → Full Version
                 └─ No → Are you learning MCP?
                          ├─ Yes → Standalone Version
                          └─ No → Clean Version (Recommended)
```