---
title: Glossary
description: Definitions of technical terms, acronyms, and domain-specific vocabulary
version: 1.0.0
last_updated: 2025-12-30
related: [architecture.md, api.md]
tags: [glossary, definitions, terminology]
---

# Glossary

## Table of Contents

- [MCP Protocol Terms](#mcp-protocol-terms)
- [JSON-RPC Terms](#json-rpc-terms)
- [HTTP/Networking Terms](#httpnetworking-terms)
- [AI/LLM Terms](#aillm-terms)
- [Python/Programming Terms](#pythonprogramming-terms)
- [Project-Specific Terms](#project-specific-terms)

## MCP Protocol Terms

### MCP (Model Context Protocol)
Communication protocol for AI agents to discover and execute tools on remote servers. Enables LLMs to interact with external services in a standardized way.

**Specification**: [modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/basic)

---

### Session
Stateful connection between MCP client and server identified by UUID. Tracks initialization state and operation readiness.

**Lifecycle**: `initialize` → `notifications/initialized` → operational

**Storage**: In-memory dictionary mapping session ID to `MCPSession` object

---

### Tool
Discrete operation exposed by MCP server (e.g., `add_user`, `search_users`). Defined by name, description, and JSON Schema for arguments.

**Example**: `get_user_by_id` tool retrieves user from database given numeric ID.

---

### Tool Discovery
Process where client requests available tools from server via `tools/list` method. Returns JSON Schema definitions for each tool.

---

### Tool Execution
Invocation of specific tool via `tools/call` method with arguments validated against tool's input schema.

**Response**: `ToolCallResult` with `content` array and optional `isError` flag.

---

### Capabilities
Features supported by client or server announced during initialization handshake. Example: `{"tools": {}}` indicates tool support.

---

### Content Item
Structured response object wrapping tool results. Format: `{"type": "text", "text": "..."}`.

**Future Extensions**: Could support `type: "image"`, `type: "file"`, etc.

---

### Protocol Version
MCP specification version (e.g., `"2024-11-05"`). Used for compatibility negotiation during initialization.

**Current**: Project uses `2024-11-05` version.

---

## JSON-RPC Terms

### JSON-RPC (Remote Procedure Call)
Stateless RPC protocol encoded in JSON. Defines request/response structure for invoking remote methods.

**Version**: Project uses JSON-RPC 2.0 specification.

**Structure**:
- Request: `{"jsonrpc": "2.0", "id": 1, "method": "...", "params": {...}}`
- Response: `{"jsonrpc": "2.0", "id": 1, "result": {...}}` or `{"error": {...}}`

---

### Method
Remote procedure name in JSON-RPC request (e.g., `initialize`, `tools/list`, `tools/call`).

---

### Params
Optional parameters dictionary in JSON-RPC request. Content varies by method.

**Example**: For `tools/call`, params include `{"name": "...", "arguments": {...}}`.

---

### Request ID
Unique identifier for correlating JSON-RPC request with its response. Can be string, number, or null.

**Notifications**: Omit `id` field to indicate fire-and-forget (no response expected).

---

### Error Object
JSON-RPC error structure: `{"code": -32600, "message": "...", "data": {...}}`.

**Standard Codes**:
- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

---

### Notification
JSON-RPC request without `id` field. Server does not send response (fire-and-forget pattern).

**Example**: `notifications/initialized` has no response body, returns HTTP 202.

---

## HTTP/Networking Terms

### SSE (Server-Sent Events)
HTTP streaming protocol for server-to-client push. Uses `text/event-stream` content type.

**Format**:
```
data: {...}\n\n
data: [DONE]\n\n
```

**Use Case**: MCP server streams JSON-RPC responses as SSE for client parsing.

---

### Accept Header
HTTP request header specifying acceptable response MIME types.

**MCP Requirement**: Must include both `application/json` and `text/event-stream`.

---

### Content-Type Header
HTTP header indicating body format. MCP uses:
- Request: `application/json`
- Response: `text/event-stream` (SSE streaming)

---

### Mcp-Session-Id Header
Custom HTTP header carrying session UUID after initialization.

**Flow**: Server sets in `initialize` response → Client includes in all subsequent requests.

---

### Endpoint
HTTP URL path handling requests. MCP uses single endpoint: `/mcp`.

**Pattern**: Method routing via JSON-RPC `method` field, not URL paths.

---

### HTTP Status Codes (Project-Specific)

| Code | Usage |
|------|-------|
| 200 | Successful SSE stream |
| 202 | Notification accepted |
| 400 | Session error (missing ID, not ready) |
| 406 | Invalid Accept header |
| 500 | Unhandled server exception |

---

## AI/LLM Terms

### DIAL (Distributed AI Laboratory)
EPAM's internal Azure OpenAI proxy service. Provides standardized API for multiple LLM models.

**Endpoint**: `https://ai-proxy.lab.epam.com`

**Access**: Requires VPN connection and API key.

---

### LLM (Large Language Model)
AI model trained on text data for generation/understanding tasks. Examples: GPT-4, Claude.

**Project Use**: AI agent streams LLM responses to generate tool calls.

---

### Tool Call
LLM's structured request to execute external tool. Format varies by provider (OpenAI uses JSON objects).

**OpenAI Structure**:
```json
{
  "id": "call_abc123",
  "function": {"name": "search_users", "arguments": "{\"name\": \"John\"}"},
  "type": "function"
}
```

---

### Function Calling
LLM capability to generate structured tool invocations based on available tool schemas.

**Mechanism**: Model trained to emit JSON objects matching function signatures.

---

### Message History
Conversation context maintained by AI agent. Includes system, user, assistant, and tool messages.

**Format**: List of `Message` objects with `role` and `content` fields.

---

### Streaming Response
LLM output generated token-by-token. Enables real-time display before full response completes.

**Implementation**: `AsyncAzureOpenAI.chat.completions.create(stream=True)`

---

### Prompt Engineering
Crafting system messages and instructions to guide LLM behavior.

**Example**: "You are a helpful assistant that can search and manage users."

---

## Python/Programming Terms

### Async/Await
Python concurrency pattern for non-blocking I/O operations.

**Example**: `async def execute()` + `await user_client.get_user(id)`

**Benefit**: Multiple requests can overlap without blocking event loop.

---

### Pydantic
Python library for data validation using type annotations. Auto-generates JSON schemas.

**Project Use**: `UserCreate`, `UserUpdate`, `MCPRequest`, `MCPResponse` models.

---

### Type Hints
Python annotations specifying expected types (e.g., `def foo(x: int) -> str`).

**Project Use**: All functions/methods include type hints for IDE support and validation.

---

### Abstract Base Class (ABC)
Python pattern for defining interface contracts. Subclasses must implement abstract methods.

**Example**: `BaseTool` with abstract `name`, `description`, `input_schema`, `execute()`.

---

### Dependency Injection
Design pattern where objects receive dependencies as constructor parameters, not create them internally.

**Example**: `BaseUserServiceTool(user_client: UserClient)` receives client instance.

---

### Context Manager
Python pattern using `with` statement for resource management (enter/exit lifecycle).

**Example**: `async with streamablehttp_client(url) as (read, write, _):`

---

### FastAPI
Python web framework for building APIs with automatic OpenAPI documentation and Pydantic integration.

**Project Use**: MCP server HTTP endpoint (`@app.post("/mcp")`).

---

### Uvicorn
ASGI server running FastAPI applications. Handles HTTP connections and async request handling.

**Start Command**: `uvicorn mcp_server.server:app --port 8006`

---

## Project-Specific Terms

### UMS (User Management Service)
Mock REST API providing user CRUD operations. Runs in Docker container on port 8041.

**Image**: `khshanovskyi/mockuserservice:latest`

**Data**: Generates 1000 random users on startup.

---

### DialClient
AI orchestration component streaming LLM responses and routing tool calls to MCP clients.

**Location**: [agent/clients/dial_client.py](../agent/clients/dial_client.py)

---

### MCPClient
Framework-based MCP client using `fastmcp` library for protocol abstraction.

**Location**: [agent/clients/mcp_client.py](../agent/clients/mcp_client.py)

---

### CustomMCPClient
Educational pure Python MCP client with explicit HTTP/SSE handling.

**Purpose**: Demonstrate protocol internals without framework abstractions.

**Location**: [agent/clients/custom_mcp_client.py](../agent/clients/custom_mcp_client.py)

---

### UserClient
REST API wrapper for User Management Service. Converts HTTP responses to formatted strings.

**Methods**: `get_user()`, `search_users()`, `add_user()`, `update_user()`, `delete_user()`

**Location**: [mcp_server/tools/users/user_client.py](../mcp_server/tools/users/user_client.py)

---

### Tool Registry
Dictionary mapping tool names to `BaseTool` instances. Populated during `MCPServer.__init__()`.

**Structure**: `{"get_user_by_id": GetUserByIdTool(...), ...}`

---

### Agent Loop
Recursive pattern where AI agent:
1. Streams LLM response
2. Detects tool calls
3. Executes tools via MCP
4. Feeds results back to LLM
5. Repeats until completion

**Termination**: No more tool calls in LLM response.

---

### Virtual Environment (venv)
Isolated Python environment with separate package installations. Prevents dependency conflicts.

**Project Path**: `dial_mcp_advanced/`

**Activation**: `source dial_mcp_advanced/bin/activate`

---

### TODO Marker
Code comment indicating incomplete implementation requiring attention.

**Pattern**: `# TODO: Implement <description>`

**Project Use**: Guides learning tasks (see [Roadmap](./roadmap.md)).

---

### Markdown Formatting (Tool Results)
Convention where tools return results wrapped in triple backticks for LLM readability.

**Example**:
```
```
  id: 123
  name: John Doe
  email: john@example.com
```
```

---

### Session Ready Flag
Boolean attribute (`MCPSession.ready_for_operation`) indicating whether client sent `notifications/initialized`.

**Enforcement**: Tools blocked until flag is `True`.

---

### Protocol Negotiation
Handshake process during `initialize` where client/server agree on protocol version.

**Current**: Simple validation (client version must match `"2024-11-05"`).

---

## Acronyms

| Acronym | Full Term | Context |
|---------|-----------|---------|
| **MCP** | Model Context Protocol | AI tool protocol |
| **RPC** | Remote Procedure Call | Method invocation pattern |
| **SSE** | Server-Sent Events | HTTP streaming |
| **LLM** | Large Language Model | AI text generation |
| **CRUD** | Create, Read, Update, Delete | Database operations |
| **REST** | Representational State Transfer | API architecture |
| **JSON** | JavaScript Object Notation | Data format |
| **UUID** | Universally Unique Identifier | Session ID format |
| **HTTP** | Hypertext Transfer Protocol | Web communication |
| **API** | Application Programming Interface | External service contract |
| **ASGI** | Asynchronous Server Gateway Interface | Python async web standard |
| **ABC** | Abstract Base Class | Python interface pattern |
| **IDE** | Integrated Development Environment | Code editor (VS Code, PyCharm) |
| **VPN** | Virtual Private Network | Secure remote connection |

---

## Abbreviations

- **args**: Arguments
- **params**: Parameters
- **req**: Request
- **res/resp**: Response
- **init**: Initialize/Initialization
- **exec**: Execute/Execution
- **impl**: Implementation
- **spec**: Specification
- **env**: Environment
- **venv**: Virtual Environment
- **cfg/config**: Configuration
- **mgmt**: Management

---

**Cross-References**:
- For protocol details, see [Architecture](./architecture.md)
- For API specifications, see [API Reference](./api.md)
- For setup terminology, see [Setup Guide](./setup.md)
