# ============================================================================
# MCP Server Core Service
# ============================================================================
# Implements Model Context Protocol (MCP) server for user management tools.
# Manages protocol lifecycle (initialize → notifications/initialized → tools/list/call),
# session state, and tool discovery/execution. Handles JSON-RPC 2.0 requests and
# returns MCP-compliant responses with proper error handling.
# ============================================================================

import uuid
import asyncio

from mcp_server.models.request import MCPRequest
from mcp_server.models.response import MCPResponse, ErrorResponse
from mcp_server.tools.users.create_user_tool import CreateUserTool
from mcp_server.tools.users.delete_user_tool import DeleteUserTool
from mcp_server.tools.users.get_user_by_id_tool import GetUserByIdTool
from mcp_server.tools.users.search_users_tool import SearchUsersTool
from mcp_server.tools.users.update_user_tool import UpdateUserTool
from mcp_server.tools.users.user_client import UserClient


class MCPSession:
    """
    Represents an MCP client session with state management and lifecycle tracking.
    
    Each client connection receives a unique session after initialization.
    Sessions track operation readiness (set by notifications/initialized) and
    activity timestamps for potential cleanup/timeout logic.
    
    Attributes:
        session_id: Unique session identifier (UUID format)
        ready_for_operation: Flag indicating if client sent notifications/initialized.
                           Only after True can tools/list and tools/call proceed.
        created_at: Event loop timestamp when session was created
        last_activity: Event loop timestamp of last client activity (used for idle tracking)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.ready_for_operation = False  # Set to True only after notifications/initialized
        self.created_at = asyncio.get_event_loop().time()
        self.last_activity = self.created_at


class MCPServer:
    """
    MCP Protocol Server implementation for user management tools.
    
    Lifecycle:
    1. initialize: Client initiates connection → server creates session with ID
    2. notifications/initialized: Client acknowledges readiness → unlocks tool operations
    3. tools/list: Return available tools as JSON Schema
    4. tools/call: Execute requested tool with parameters
    
    Error Handling:
    - Validates session state before tool operations
    - Returns MCP-formatted errors (code, message) for invalid requests
    - Wraps tool exceptions in error responses (isError: true)
    
    Session Management:
    - One session per client connection
    - Sessions tracked by UUID in self.sessions dict
    - Last activity updated on each get_session() call
    """

    def __init__(self):
        # MCP protocol configuration
        self.protocol_version = "2024-11-05"
        self.server_info = {
            "name": "custom-ums-mcp-server",
            "version": "1.0.0"
        }

        # Session management: maps session_id → MCPSession instance
        self.sessions: dict[str, MCPSession] = {}
        
        # Tool registry: maps tool_name → BaseTool instance
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """
        Register all available tools by instantiating tool classes and indexing by name.
        
        All tools share a single UserClient instance for API access.
        Tool registration happens once during server init to avoid repeated instantiation.
        
        Registered tools:
        - get_user_by_id: Fetch user by numeric ID
        - search_users: Query users by name pattern
        - add_user: Create new user (returns assigned ID)
        - update_user: Modify existing user
        - delete_user: Remove user by ID
        
        Side Effect:
            Populates self.tools dict where key=tool.name, value=tool instance
        """
        user_client = UserClient()
        tools = [
            GetUserByIdTool(user_client),
            SearchUsersTool(user_client),
            CreateUserTool(user_client),
            UpdateUserTool(user_client),
            DeleteUserTool(user_client)
        ]
        for tool in tools:
            self.tools[tool.name] = tool

    def _validate_protocol_version(self, client_version: str) -> str:
        """
        Validate client protocol version and negotiate compatible version.
        
        Currently supports only the latest version. In future implementations,
        could downgrade to older versions if client doesn't match.
        
        Args:
            client_version: Protocol version claimed by client (e.g., "2024-11-05")
        
        Returns:
            str: Negotiated protocol version to use for this connection.
                 Either the client version (if supported) or server's default.
        """
        supported_versions = ["2024-11-05"]
        if client_version in supported_versions:
            return client_version
        return self.protocol_version

    def get_session(self, session_id: str) -> MCPSession | None:
        """
        Retrieve an existing session and update its activity timestamp.
        
        Used by HTTP handlers to validate that a session ID from the request header
        is still active on the server. Updates last_activity to track client liveliness.
        
        Args:
            session_id: Session ID from Mcp-Session-Id header
        
        Returns:
            MCPSession if found, None otherwise.
            Side effect: Updates session.last_activity to current event loop time.
        """
        session = self.sessions.get(session_id)
        if session:
            session.last_activity = asyncio.get_event_loop().time()
        return session

    def handle_initialize(self, request: MCPRequest) -> tuple[MCPResponse, str]:
        """
        Handle MCP initialize request and create a new client session.
        
        CRITICAL: This is the first request in the MCP handshake. Creates a unique
        session ID that the client must echo back in subsequent requests via
        Mcp-Session-Id header. Session remains blocked for operations until
        notifications/initialized is received.
        
        Args:
            request: MCPRequest with method="initialize" and params containing:
                   - protocolVersion: Client's claimed protocol version (e.g., "2024-11-05")
                   - capabilities: Client capabilities/features (tools, resources, etc.)
                   - clientInfo: Client name and version
        
        Returns:
            tuple[MCPResponse, str]:
            - MCPResponse: JSON-RPC response with serverInfo and supported capabilities
            - str: New session_id (must be sent in Mcp-Session-Id header by client)
        
        Side Effect:
            Creates new MCPSession instance and stores in self.sessions dict.
        """
        session_id = str(uuid.uuid4()).replace("-", "")
        session = MCPSession(session_id)
        self.sessions[session_id] = session
        
        # Negotiate protocol version (currently no downgrade, just validate)
        protocol_version = request.params.get("protocolVersion") if request.params else self.protocol_version
        
        mcp_response = MCPResponse(
            id=request.id,
            result={
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": self.server_info
            }
        )
        
        return mcp_response, session_id

    def handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """
        Handle tools/list request to discover available tools.
        
        Returns all registered tools in MCP format (name, description, inputSchema).
        Clients call this after notifications/initialized to learn what operations
        the server supports, then use tool names in subsequent tools/call requests.
        
        Args:
            request: MCPRequest with method="tools/list" and no params
        
        Returns:
            MCPResponse with result.tools array containing:
            - name: Tool identifier for tools/call invocation
            - description: Human-readable explanation
            - inputSchema: JSON Schema of required/optional parameters
        """
        tools_list = [tool.to_mcp_tool() for tool in self.tools.values()]
        
        mcp_response = MCPResponse(
            id=request.id,
            result={"tools": tools_list}
        )
        
        return mcp_response

    async def handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """
        Handle tools/call request to execute a specific tool with arguments.
        
        Flow:
        1. Validate request params (name, arguments)
        2. Check tool exists in registry
        3. Execute tool.execute() with arguments (async)
        4. Return result as MCP ToolCallResult structure
        
        Error Handling:
        - Missing params/name → JSON-RPC error (-32602, -32601)
        - Tool not found → JSON-RPC error (-32601)
        - Tool execution exception → Wrapped in isError: true response
        
        Args:
            request: MCPRequest with method="tools/call" and params containing:
                   - name: Tool identifier (string)
                   - arguments: Dict of parameter values for the tool
        
        Returns:
            MCPResponse with result.content array containing text result,
            or error if request/execution fails. If tool raises exception,
            isError flag set to true in response.
        """
        # Validate request has params
        if not request.params:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=-32602, message="Missing parameters")
            )
        
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        # Validate tool name is provided
        if not tool_name:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=-32602, message="Missing required parameter: name")
            )
        
        # Validate tool exists in registry
        if tool_name not in self.tools:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=-32601, message=f"Tool '{tool_name}' not found")
            )
        
        tool = self.tools[tool_name]
        
        try:
            # Execute tool asynchronously (even if tool uses blocking calls internally)
            result_text = await tool.execute(arguments)
            return MCPResponse(
                id=request.id,
                result={"content": [{"type": "text", "text": result_text}]}
            )
        except Exception as tool_error:
            # Wrap tool exceptions in error response to prevent crashes
            return MCPResponse(
                id=request.id,
                result={"content": [{"type": "text", "text": f"Tool execution error: {str(tool_error)}"}], "isError": True}
            )
