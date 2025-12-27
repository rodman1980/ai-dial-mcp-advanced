# ============================================================================
# Pure Python MCP Client Implementation
# ============================================================================
# Async MCP (Model Context Protocol) client built with aiohttp, demonstrating
# JSON-RPC 2.0 request/response handling and Server-Sent Events (SSE) parsing.
# This implementation prioritizes educational clarity over framework abstractions.
# ============================================================================

import json
import uuid
from typing import Optional, Any
import aiohttp


MCP_SESSION_ID_HEADER = "Mcp-Session-Id"

class CustomMCPClient:
    """
    Pure Python MCP client using aiohttp for protocol communication.
    
    Implements the MCP session lifecycle:
    1. Initialize: Client sends initialize request → Server responds with session ID
    2. Notify: Client sends notifications/initialized (enables tool operations)
    3. Operate: Client can now call tools/list and tools/call
    
    **Key Flow:**
    - Maintains aiohttp.ClientSession for persistent HTTP connection
    - Tracks Mcp-Session-Id header across requests (critical for session persistence)
    - Handles both SSE and JSON responses based on Content-Type header
    - Extracts and validates JSON-RPC 2.0 responses with error checking
    """

    def __init__(self, mcp_server_url: str) -> None:
        """
        Initialize client state without connecting to server.
        
        Precondition: Must call connect() before calling get_tools() or call_tool()
        
        Args:
            mcp_server_url: Full URL to MCP server endpoint (e.g., http://localhost:8006/mcp)
        """
        self.server_url = mcp_server_url
        self.session_id: Optional[str] = None  # Set by initialize response header
        self.http_session: Optional[aiohttp.ClientSession] = None  # Lazy-initialized in connect()

    @classmethod
    async def create(cls, mcp_server_url: str) -> 'CustomMCPClient':
        """
        Async factory pattern: create and fully initialize client in one call.
        
        This avoids the awkward __init__/await pattern in async code. The returned
        instance is ready for tool operations (session initialized, session ID acquired).
        
        Args:
            mcp_server_url: Full URL to MCP server /mcp endpoint
            
        Returns:
            CustomMCPClient: Connected and initialized, ready for get_tools()/call_tool()
            
        Raises:
            RuntimeError: If connection or MCP initialization fails
        """
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def _send_request(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Send JSON-RPC 2.0 request to MCP server and return parsed response.
        
        **Flow:**
        1. Construct JSON-RPC 2.0 request with unique ID for correlation
        2. Add session ID to headers (if available from prior initialization)
        3. POST request to MCP server endpoint
        4. Capture session ID from response header (if not yet set)
        5. Parse response based on Content-Type (SSE or JSON)
        6. Check for JSON-RPC error field and raise if present
        
        **Precondition:** self.http_session must be initialized (call connect() first)
        
        Args:
            method: JSON-RPC method name (e.g., "tools/list", "tools/call")
            params: Optional method-specific parameters dictionary
            
        Returns:
            dict[str, Any]: Parsed JSON response containing result or error
            
        Raises:
            RuntimeError: If HTTP session not initialized or JSON-RPC error in response
        """
        if self.http_session is None:
            raise RuntimeError("HTTP session not initialized")
        
        # Construct JSON-RPC 2.0 request with unique ID for request/response correlation
        request_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),  # Unique ID for matching async responses
            "method": method
        }
        
        if params:
            request_data["params"] = params
        
        # Headers must accept both JSON and SSE (server may respond with either)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        # Propagate session ID once established (critical for server-side session tracking)
        if self.session_id:
            headers[MCP_SESSION_ID_HEADER] = self.session_id
        
        async with self.http_session.post(
            self.server_url,
            json=request_data,
            headers=headers
        ) as response:
            # Capture session ID from response header if first time (initialization flow)
            if not self.session_id and MCP_SESSION_ID_HEADER in response.headers:
                self.session_id = response.headers[MCP_SESSION_ID_HEADER]
            
            # 202 Accepted indicates notification processed (no response body expected)
            if response.status == 202:
                return {}
            
            # Determine response format based on Content-Type header
            content_type = response.headers.get("content-type", "")
            
            if "text/event-stream" in content_type.lower():
                response_data = await self._parse_sse_response_streaming(response)
            else:
                response_data = await response.json()
            
            # Check for JSON-RPC error field and raise if present (server-side error)
            if "error" in response_data:
                error = response_data["error"]
                raise RuntimeError(f"MCP Error {error['code']}: {error['message']}")
            
            return response_data

    async def _parse_sse_response_streaming(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        """
        Parse Server-Sent Events (SSE) response stream.
        
        SSE format: text/event-stream with lines of form:
            data: {"jsonrpc": "2.0", "id": ..., "result": ...}
            data: [DONE]
        
        **Flow:**
        1. Stream response line-by-line (avoids buffering entire response)
        2. Skip empty lines and comments (lines starting with ':')
        3. Extract JSON from lines starting with 'data: ' prefix
        4. Return first valid JSON (MCP typically sends one data line then [DONE])
        5. Raise if stream ends without finding JSON data
        
        Args:
            response: aiohttp.ClientResponse in streaming mode
            
        Returns:
            dict[str, Any]: Parsed JSON-RPC response object
            
        Raises:
            RuntimeError: If no valid JSON data found before stream end
        """
        async for line in response.content:
            line_str = line.decode('utf-8').strip()
            
            # Skip empty lines and comments (lines starting with ':')
            if not line_str or line_str.startswith(':'):
                continue
            
            # Check for data field and extract JSON payload
            if line_str.startswith('data: '):
                data_part = line_str[6:]  # Remove 'data: ' prefix
                # [DONE] marker signals end of stream; stop on first valid JSON
                if data_part != '[DONE]':
                    return json.loads(data_part)
        
        raise RuntimeError("No valid data found in SSE response")

    async def connect(self) -> None:
        """
        Establish connection to MCP server and complete session initialization.
        
        **MCP Session Lifecycle (CRITICAL):**
        1. initialize: Client→Server, Server responds with Mcp-Session-Id header
        2. notifications/initialized: Client→Server, signals ready for tool operations
        3. Ready: Client can now call tools/list and tools/call
        
        **Flow:**
        1. Create aiohttp.ClientSession with timeouts and connection pooling
        2. Send initialize request to establish session (captures session ID)
        3. Send initialized notification to mark session ready (400 without this!)
        4. Log connection success
        5. Propagate exceptions as RuntimeError for caller handling
        
        **Precondition:** self.server_url must point to valid MCP /mcp endpoint
        
        **Side Effects:**
        - Sets self.http_session for subsequent requests
        - Sets self.session_id from initialize response header
        - Prints connection status to stdout
        
        **Error Handling:** All exceptions wrapped in RuntimeError with context
        
        Raises:
            RuntimeError: If connection, initialization, or notification fails
        """
        try:
            # Configure timeouts: total request 30s, connection established within 10s
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            # Connection pooling: max 100 connections, max 10 per host (for efficiency)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
            self.http_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
            
            # MCP initialize request: declare protocol version and capabilities
            init_params = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},  # Declare support for tools capability
                "clientInfo": {"name": "my-custom-mcp-client", "version": "1.0.0"}
            }
            
            # Initialize: Server responds with Mcp-Session-Id header (captured in _send_request)
            init_result = await self._send_request("initialize", init_params)
            
            # Notify: Signal to server that initialization complete, enables tool operations
            # WITHOUT this notification, subsequent tool/list and tool/call will fail with 400
            await self._send_notification("notifications/initialized")
            
            # Log connection success with server info extracted from initialize response
            print(f"Connected to MCP server: {init_result.get('result', {}).get('serverInfo')}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MCP server: {e}")

    async def _send_notification(self, method: str) -> None:
        """
        Send fire-and-forget notification to MCP server (no response expected).
        
        Notifications per JSON-RPC 2.0 spec omit the 'id' field, signaling to server
        that no response is needed. Used for: notifications/initialized (post-init signal).
        
        Args:
            method: Notification method name (e.g., "notifications/initialized")
            
        **Precondition:** self.http_session must be initialized
        
        Side Effects: Updates self.session_id if present in response header
        """
        if self.http_session is None:
            raise RuntimeError("HTTP session not initialized")
        
        # JSON-RPC notification: intentionally omit 'id' field (signals no response needed)
        request_data = {
            "jsonrpc": "2.0",
            "method": method
            # Note: NO "id" field - this marks it as a notification, not a request
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        # Propagate session ID if already established
        if self.session_id:
            headers[MCP_SESSION_ID_HEADER] = self.session_id
        
        async with self.http_session.post(
            self.server_url,
            json=request_data,
            headers=headers
        ) as response:
            # Capture session ID if server includes it in response (redundant but safe)
            if MCP_SESSION_ID_HEADER in response.headers:
                self.session_id = response.headers[MCP_SESSION_ID_HEADER]
                print(f"Session ID set: {self.session_id}")

    async def get_tools(self) -> list[dict[str, Any]]:
        """
        Retrieve available tools from MCP server in OpenAI-compatible format.
        
        **Flow:**
        1. Validate client is connected (session initialized)
        2. Send tools/list JSON-RPC request to MCP server
        3. Extract tools array from response.result.tools
        4. Transform each tool to OpenAI function schema format (for agent integration)
        
        **Precondition:** connect() must have completed successfully
        
        Returns:
            list[dict[str, Any]]: Tools in OpenAI format with structure:
                {
                    "type": "function",
                    "function": {
                        "name": str,
                        "description": str,
                        "parameters": JSON Schema (inputSchema from MCP)
                    }
                }
        
        Raises:
            RuntimeError: If session not initialized or tools/list fails
        """
        if not self.http_session:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        
        # Request tools/list from MCP server via JSON-RPC
        response = await self._send_request("tools/list")
        # Extract tools array from nested response structure
        tools = response.get("result", {}).get("tools", [])
        
        # Transform MCP tool format to OpenAI-compatible function schema
        # (allows agents to discover and use tools through standard OpenAI API)
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["inputSchema"]  # MCP inputSchema = OpenAI parameters
                }
            }
            for tool in tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """
        Execute a specific tool on the MCP server with given arguments.
        
        **Flow:**
        1. Validate client is connected
        2. Log tool invocation for debugging
        3. Send tools/call JSON-RPC request with tool name and arguments
        4. Extract text result from response.result.content[0].text
        5. Return result string or fallback if missing
        
        **Precondition:** connect() must have completed, tool_name must exist on server
        
        Args:
            tool_name: Unique tool identifier (from get_tools() results)
            tool_args: Dictionary of arguments matching tool's input schema
            
        Returns:
            Any: Tool execution result (typically formatted string from server)
        
        Raises:
            RuntimeError: If session not initialized or tools/call fails
        """
        if self.http_session is None:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        
        # Log tool invocation for debugging/tracing
        print(f"    Calling `{tool_name}` with {tool_args}")
        
        # JSON-RPC tools/call params: name and arguments
        params = {
            "name": tool_name,
            "arguments": tool_args
        }
        
        # Invoke tool and receive response
        response = await self._send_request("tools/call", params)
        
        # Extract text from MCP response structure:
        # response["result"]["content"] is array of ContentItem objects
        # Each ContentItem has {"type": "text", "text": "..."}
        if content := response["result"].get("content", []):
            if item := content[0]:  # Walrus operator: assign and check if truthy
                text_result = item.get("text", "")
                print(f"    ⚙️: {text_result}\n")
                return text_result
        
        # Fallback if response structure unexpected (should not occur in normal flow)
        return "Unexpected error occurred!"