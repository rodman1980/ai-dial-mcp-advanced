"""
MCP Client wrapper using fastmcp library for streamlined server communication.

This module provides a high-level abstraction over the MCP (Model Context Protocol)
client implementation. It handles HTTP streaming, session lifecycle, and JSON-RPC
message formatting transparently, allowing agents to discover and invoke tools
on remote MCP servers with minimal boilerplate.

Key responsibilities:
- Establish persistent HTTP/SSE connection to MCP server
- Manage JSON-RPC 2.0 session state and initialization handshake
- Transform tool discovery responses into OpenAI-compatible format
- Execute tool calls with error handling and result extraction
"""

from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent


class MCPClient:
    """
    Framework-based MCP client leveraging fastmcp's built-in transport layer.
    
    This client wraps the fastmcp library's ClientSession to provide a simplified
    async interface for agent integration. It automatically handles:
    - HTTP/SSE streaming setup via streamablehttp_client
    - JSON-RPC request/response serialization
    - Session initialization and capability negotiation
    
    **Lifecycle:**
    1. create() factory - instantiates and connects in one call
    2. connect() - opens HTTP streams and initializes MCP session
    3. get_tools() / call_tool() - operations on connected session
    
    **Session State:**
    - _streams_context: Manages HTTP connection lifecycle (enter/exit)
    - _session_context: Manages MCP ClientSession lifecycle
    - session: Active ClientSession after initialization (or None if not connected)
    """

    def __init__(self, mcp_server_url: str) -> None:
        """
        Initialize MCPClient with server URL (does not connect yet).
        
        Args:
            mcp_server_url: Full URL to MCP server endpoint (e.g., http://localhost:8006/mcp)
        """
        self.server_url = mcp_server_url
        self.session: Optional[ClientSession] = None
        self._streams_context = None  # Context manager for HTTP stream lifecycle
        self._session_context = None  # Context manager for ClientSession lifecycle

    @classmethod
    async def create(cls, mcp_server_url: str) -> 'MCPClient':
        """
        Async factory method: instantiate and connect to MCP server in one call.
        
        This pattern avoids separate __init__/connect steps for cleaner async initialization.
        The server initialization handshake (capabilities negotiation) completes before
        returning, so the returned client is ready for tool operations immediately.
        
        Args:
            mcp_server_url: Full URL to MCP server endpoint
            
        Returns:
            MCPClient: Connected instance with active session and initialized state
            
        Raises:
            RuntimeError: If connection or initialization fails (propagated from connect())
        """
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def connect(self):
        """
        Establish HTTP/SSE connection to MCP server and initialize session.
        
        **Flow:**
        1. Create HTTP stream context (streamablehttp_client handles SSE setup)
        2. Extract bidirectional read/write streams from context
        3. Wrap streams in ClientSession for JSON-RPC message handling
        4. Call initialize() for server capability negotiation
        5. Print server info for debugging/verification
        
        **Side Effects:**
        - Sets self._streams_context: Manages HTTP connection lifecycle
        - Sets self._session_context: Manages MCP ClientSession lifecycle
        - Sets self.session: Ready for tool operations (get_tools, call_tool)
        - Prints server info to stdout (useful for debugging)
        
        **Error Handling:**
        - Network errors or malformed responses will raise exceptions that propagate
        - Caller should wrap in try/except or use create() factory for error handling
        
        **Precondition:**
        - self.server_url must be a valid HTTP URL pointing to MCP server /mcp endpoint
        """
        # Initialize HTTP stream handling for SSE protocol
        self._streams_context = streamablehttp_client(self.server_url)
        read_stream, write_stream, _ = await self._streams_context.__aenter__()

        # Wrap streams in ClientSession for JSON-RPC 2.0 message protocol
        self._session_context = ClientSession(read_stream, write_stream)
        self.session: ClientSession = await self._session_context.__aenter__()

        # Perform MCP initialization handshake to negotiate capabilities
        init_result = await self.session.initialize()
        print(init_result.model_dump_json(indent=2))

    async def get_tools(self) -> list[dict[str, Any]]:
        """
        Retrieve available tools from the MCP server and transform to OpenAI format.
        
        **Flow:**
        1. Validate that session is initialized (connection required)
        2. Call session.list_tools() to fetch tool definitions from server
        3. Transform each tool to OpenAI-compatible function schema:
           - Wrap tool definition in "function" key
           - Map MCP inputSchema directly to OpenAI "parameters" field
           - Set type to "function" for OpenAI compatibility
        
        **Returns:**
        List of tools in OpenAI function format:
        {
            "type": "function",
            "function": {
                "name": tool name,
                "description": tool description,
                "parameters": JSON Schema of input arguments
            }
        }
        
        **Precondition:**
        - self.session must be initialized (call connect() first)
        
        **Error Handling:**
        - Raises RuntimeError if session not initialized
        - Network errors from session.list_tools() will propagate
        """
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        # Fetch tool definitions from MCP server via JSON-RPC
        tools = await self.session.list_tools()
        
        # Transform to OpenAI-compatible function schema for agent use
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool in tools.tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server and return its result.
        
        **Flow:**
        1. Validate that session is initialized
        2. Invoke tool via session.call_tool() with JSON-RPC request
        3. Handle response and extract content:
           - If TextContent: extract and return the text string
           - Otherwise: return raw content object (fallback for other types)
        4. Log results for debugging
        
        **Args:**
        - tool_name: Unique tool identifier (must exist on MCP server)
        - tool_args: Dictionary of arguments matching tool's inputSchema
        
        **Returns:**
        - str: Tool execution result as text (most common case)
        - Any: Raw content object if result is not TextContent (edge case)
        
        **Precondition:**
        - self.session must be initialized (call connect() first)
        - tool_name must be a valid tool returned by get_tools()
        - tool_args must conform to the tool's input schema
        
        **Side Effects:**
        - Prints debug info: tool invocation details and results
        
        **Error Handling:**
        - Raises RuntimeError if session not initialized
        - Tool execution errors are handled server-side (returned in content with isError flag)
        - Network/timeout errors propagate from session.call_tool()
        """
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        print(f"    Calling `{tool_name}` with {tool_args}")

        # Invoke tool via JSON-RPC and retrieve response
        tool_result: CallToolResult = await self.session.call_tool(tool_name, tool_args)
        content = tool_result.content

        print(f"    ⚙️: {content}\n")

        # Extract text from TextContent wrapper, otherwise return raw content
        if isinstance(content, TextContent):
            return content.text

        return content

