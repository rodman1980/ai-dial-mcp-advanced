---
title: Setup Guide
description: Complete installation and configuration guide for development environment
version: 1.0.0
last_updated: 2025-12-30
related: [architecture.md, testing.md]
tags: [setup, installation, configuration, environment]
---

# Setup Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [IDE Setup](#ide-setup)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows (WSL2 recommended)
- **Python**: 3.11 or higher ([download](https://www.python.org/downloads/))
- **Docker**: Docker Desktop or Docker Engine ([download](https://www.docker.com/products/docker-desktop))
- **Git**: Version control ([download](https://git-scm.com/downloads))
- **Network**: EPAM VPN connection (for DIAL API access)

### Verify Installations

```bash
# Python version check
python --version  # Should show 3.11.x or higher

# Docker check
docker --version
docker ps  # Should connect without errors

# Git check
git --version
```

### DIAL API Access

1. **Connect to VPN**: Ensure EPAM VPN is active
2. **Request API Key**: Visit [DIAL API Portal](https://support.epam.com/ess?id=sc_cat_item&table=sc_cat_item&sys_id=910603f1c3789e907509583bb001310c)
3. **Save Key**: Store in password manager (needed for agent configuration)

**Note**: External users without EPAM access cannot test AI agent features but can still develop/test MCP server independently.

## Installation

### 1. Clone Repository

```bash
cd ~/Documents/git  # Or your preferred workspace
git clone <repository-url> ai-dial-mcp-advanced
cd ai-dial-mcp-advanced
```

### 2. Create Virtual Environment

**macOS/Linux:**
```bash
python -m venv dial_mcp_advanced
source dial_mcp_advanced/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv dial_mcp_advanced
.\dial_mcp_advanced\Scripts\Activate.ps1
```

**Verification:**
```bash
which python  # Should show path inside virtual environment
# Output: /path/to/ai-dial-mcp-advanced/dial_mcp_advanced/bin/python
```

### 3. Install Dependencies

```bash
pip install --upgrade pip  # Ensure latest pip
pip install -r requirements.txt
```

**Expected Output:**
```
Successfully installed:
  fastmcp-2.10.1
  requests-2.28.0
  aiohttp-3.13.2
  fastapi-0.116.0
  openai-1.93.3
  ...
```

**Verify Installation:**
```bash
pip list | grep -E "fastmcp|fastapi|openai"
```

## Configuration

### 1. Environment Variables

Create `.env` file in project root:

```bash
# .env
DIAL_API_KEY=your_dial_api_key_here
USERS_MANAGEMENT_SERVICE_URL=http://localhost:8041
```

**Load Environment:**
```bash
# Option 1: Export manually
export DIAL_API_KEY='your_key'

# Option 2: Use python-dotenv (already in requirements)
# Loaded automatically by agent/app.py if .env exists
```

**Security Warning**: Never commit `.env` to Git. Verify `.gitignore` includes:
```gitignore
.env
*.env.local
```

### 2. Docker Configuration

**Start User Service:**
```bash
docker-compose up -d
```

**Verify Running:**
```bash
docker ps
# Should show: khshanovskyi/mockuserservice on port 8041
```

**Test Health Endpoint:**
```bash
curl http://localhost:8041/health
# Expected: {"status": "healthy"}
```

**View Logs:**
```bash
docker-compose logs -f userservice
```

**Stop Service:**
```bash
docker-compose down
```

### 3. Port Allocation

| Service | Port | Configurable? | Notes |
|---------|------|---------------|-------|
| User Service | 8041 | Yes (docker-compose.yml) | Mock REST API |
| MCP Server | 8006 | Yes (mcp_server/server.py) | Default Uvicorn port |
| DIAL API | 443 | No | External Azure OpenAI |

**Change MCP Server Port:**

Edit [mcp_server/server.py](../mcp_server/server.py):
```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)  # Changed from 8006
```

**Change User Service Port:**

Edit [docker-compose.yml](../docker-compose.yml):
```yaml
services:
  userservice:
    ports:
      - "8042:8000"  # Changed from 8041:8000
```

Update environment variable accordingly:
```bash
export USERS_MANAGEMENT_SERVICE_URL=http://localhost:8042
```

## Running the Project

### Full Stack Startup

**Terminal 1 - User Service:**
```bash
docker-compose up
# Runs in foreground; Ctrl+C to stop
# Use -d flag for background: docker-compose up -d
```

**Terminal 2 - MCP Server:**
```bash
source dial_mcp_advanced/bin/activate  # Activate venv
python mcp_server/server.py
```

**Expected Output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8006 (Press CTRL+C to quit)
```

**Terminal 3 - AI Agent:**
```bash
source dial_mcp_advanced/bin/activate
export DIAL_API_KEY='your_key'
python agent/app.py
```

**Expected Output:**
```
Connected to MCP server: {'name': 'custom-ums-mcp-server', 'version': '1.0.0'}

You: 
```

### Test Query

```text
Check if Arkadiy Dobkin present as a user, if not then search info about him in the web and add him
```

**Expected Behavior:**
1. Agent calls `search_users` tool (local MCP server)
2. If not found, calls web search (TODO: remote MCP server)
3. Agent calls `add_user` tool with extracted information
4. Returns confirmation message

### Shutdown Sequence

1. **Agent**: Ctrl+C in Terminal 3
2. **MCP Server**: Ctrl+C in Terminal 2
3. **User Service**: `docker-compose down` or Ctrl+C in Terminal 1

## IDE Setup

### Visual Studio Code

#### Recommended Extensions

Install via VS Code Extensions panel (Cmd/Ctrl+Shift+X):

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.debugpy",
    "ms-azuretools.vscode-docker",
    "humao.rest-client",
    "bierner.markdown-mermaid"
  ]
}
```

#### Python Interpreter

1. Open Command Palette (Cmd/Ctrl+Shift+P)
2. Type "Python: Select Interpreter"
3. Choose: `./dial_mcp_advanced/bin/python`

**Verify in Status Bar**: Should show `Python 3.11.x ('dial_mcp_advanced')`

#### Launch Configuration

Create [.vscode/launch.json](../.vscode/launch.json):

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "MCP Server",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/mcp_server/server.py",
      "console": "integratedTerminal",
      "justMyCode": true,
      "env": {
        "USERS_MANAGEMENT_SERVICE_URL": "http://localhost:8041"
      }
    },
    {
      "name": "AI Agent",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/agent/app.py",
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "DIAL_API_KEY": "${input:dialApiKey}"
      }
    }
  ],
  "inputs": [
    {
      "id": "dialApiKey",
      "type": "promptString",
      "description": "Enter DIAL API Key",
      "password": true
    }
  ]
}
```

**Usage**: Press F5 → Select configuration → Enter API key when prompted

#### Tasks Configuration

Create [.vscode/tasks.json](../.vscode/tasks.json):

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start User Service",
      "type": "shell",
      "command": "docker-compose up",
      "isBackground": true,
      "problemMatcher": []
    },
    {
      "label": "Stop User Service",
      "type": "shell",
      "command": "docker-compose down"
    }
  ]
}
```

**Usage**: Terminal → Run Task → Select task

### PyCharm

#### Project Interpreter

1. File → Settings → Project: ai-dial-mcp-advanced → Python Interpreter
2. Add Interpreter → Existing Environment
3. Select: `/path/to/ai-dial-mcp-advanced/dial_mcp_advanced/bin/python`

#### Run Configurations

**MCP Server:**
- Script path: `mcp_server/server.py`
- Environment variables: `USERS_MANAGEMENT_SERVICE_URL=http://localhost:8041`

**AI Agent:**
- Script path: `agent/app.py`
- Environment variables: `DIAL_API_KEY=your_key`

## Troubleshooting

### Common Issues

#### 1. Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'fastmcp'
```

**Solution:**
```bash
# Ensure virtual environment is activated
source dial_mcp_advanced/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip show fastmcp
```

#### 2. Docker Connection Refused

**Symptom:**
```
requests.exceptions.ConnectionError: ('Connection aborted.', ConnectionRefusedError(61, 'Connection refused'))
```

**Solution:**
```bash
# Check Docker is running
docker ps

# Restart user service
docker-compose down
docker-compose up -d

# Verify port binding
lsof -i :8041  # macOS/Linux
netstat -an | grep 8041  # Windows
```

#### 3. MCP Server Port In Use

**Symptom:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Find process using port 8006
lsof -ti:8006  # Returns PID

# Kill process
kill -9 <PID>

# Or use different port (edit server.py)
```

#### 4. DIAL API 401 Unauthorized

**Symptom:**
```
openai.AuthenticationError: 401 Unauthorized
```

**Solution:**
- Verify VPN connection active
- Check API key correctness (no extra spaces/quotes)
- Confirm key not expired (request new one)
- Test with curl:
  ```bash
  curl -H "Authorization: Bearer $DIAL_API_KEY" \
       https://ai-proxy.lab.epam.com/health
  ```

#### 5. Session Not Ready (400)

**Symptom:**
```
{"error": "Session not ready. Send notifications/initialized first"}
```

**Solution:**
- Ensure `notifications/initialized` called after `initialize`
- Verify session ID passed in `Mcp-Session-Id` header
- See [Testing Guide](./testing.md) for correct request sequence

#### 6. Python Version Mismatch

**Symptom:**
```
SyntaxError: invalid syntax (type hints)
```

**Solution:**
```bash
# Check Python version
python --version

# If < 3.11, install newer version:
# macOS: brew install python@3.11
# Ubuntu: sudo apt install python3.11
# Windows: Download from python.org

# Recreate virtual environment
rm -rf dial_mcp_advanced
python3.11 -m venv dial_mcp_advanced
source dial_mcp_advanced/bin/activate
pip install -r requirements.txt
```

### Logging and Debugging

#### Enable Debug Logging

**MCP Server** ([server.py](../mcp_server/server.py)):
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**MCPClient** ([mcp_client.py](../agent/clients/mcp_client.py)):
```python
# Add print statements in _send_request()
print(f"Request: {request_data}")
print(f"Response: {response_data}")
```

#### Postman Debugging

1. Import [mcp.postman_collection.json](../mcp.postman_collection.json)
2. Enable "Show headers" in response view
3. Check "Mcp-Session-Id" header presence
4. View SSE stream in "Raw" tab

#### Docker Logs

```bash
# Real-time logs
docker-compose logs -f userservice

# Last 100 lines
docker-compose logs --tail=100 userservice

# Filter errors
docker-compose logs userservice | grep ERROR
```

### Cleanup and Reset

**Full Reset:**
```bash
# Stop all services
docker-compose down

# Remove virtual environment
rm -rf dial_mcp_advanced

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reinstall from scratch
python -m venv dial_mcp_advanced
source dial_mcp_advanced/bin/activate
pip install -r requirements.txt
docker-compose up -d
```

**Reset User Data:**
```bash
# User service stores data in ./data volume
docker-compose down
rm -rf ./data
docker-compose up -d  # Regenerates 1000 users
```

### Getting Help

- **GitHub Issues**: Check project issues for known bugs
- **MCP Specification**: [Official Docs](https://modelcontextprotocol.io/)
- **EPAM Support**: Internal Slack channels or forums
- **Logs**: Include full error messages and stack traces when reporting issues

---

**Next Steps**: 
1. Verify installation: Run `python mcp_server/server.py` and test with Postman
2. Complete TODO tasks: Implement remaining MCP server methods
3. Test AI agent: Run agent with sample queries

See [Testing Guide](./testing.md) for comprehensive validation procedures.
