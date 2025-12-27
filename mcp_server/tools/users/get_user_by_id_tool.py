from typing import Any

from mcp_server.tools.users.base import BaseUserServiceTool

# ============================================================================
# Get User By ID Tool: MCP tool for retrieving a single user by their ID
# ============================================================================
# Implements the "get_user_by_id" MCP tool, allowing clients to fetch
# complete user information when the user's ID is known.
# Requires the user ID as a mandatory parameter.
# ============================================================================


class GetUserByIdTool(BaseUserServiceTool):
    """
    MCP tool for retrieving a specific user by their unique identifier.
    
    Direct lookup tool for when the user ID is already known.
    Useful for AI agents that need to fetch full user details before
    performing operations (e.g., verify user exists before update/delete).
    
    **Schema:** Requires exactly one parameter:
    - id: number (user's unique identifier)
    
    **Error Handling:** Returns error if user not found (404 from service).
    """

    @property
    def name(self) -> str:
        """Tool identifier used by MCP clients to invoke this tool."""
        return "get_user_by_id"

    @property
    def description(self) -> str:
        """Human-readable description for tool discovery and AI model routing."""
        return "Get user information by ID"

    @property
    def input_schema(self) -> dict[str, Any]:
        """
        Define expected input parameters as JSON Schema.
        
        Specifies a single required numeric parameter (id) for direct user lookup.
        JSON Schema definition ensures:
        - Client validates user ID is numeric before calling execute()
        - AI models understand this tool requires exactly one parameter
        - Schema is exposed in tools/list response for discovery
        
        Returns:
            dict: JSON Schema requiring "id" as a number.
                  No other parameters accepted (strict single-lookup pattern).
        
        Remarks:
            The "required" array enforces that callers must provide an ID;
            empty or missing ID will be rejected by MCPServer before execute().
            
            Type is "number" (not "string") to match user service's ID type,
            even though arguments pass through JSON (which supports numbers).
            The execute() method safely converts to int for UserClient.
        """
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "number",
                    "description": "The ID of the user to retrieve"
                }
            },
            "required": ["id"]
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        """
        Execute the tool: retrieve user by ID from the service.
        
        **Flow:**
        1. Extract user ID from arguments dict (guaranteed to exist by schema)
        2. Coerce to int (JSON numbers deserialize as float; user service expects int)
        3. Call UserClient.get_user(user_id) which:
           - Makes HTTP GET to user service /user/{id} endpoint
           - Returns formatted user information as string on success
           - Raises exception (caught by MCPServer) if user not found (404)
        
        Args:
            arguments: Dict with single key "id" (numeric value).
                      Guaranteed to be present by input_schema validation.
        
        Returns:
            str: Formatted user information (backtick-wrapped markdown block
                 with fields: id, name, surname, email, gender, etc.).
        
        Raises:
            Exception: Raised by UserClient if HTTP request fails (e.g., 404 not found,
                      500 server error, network timeout). MCPServer catches and
                      wraps in ToolCallResult with isError=True.
        
        Remarks:
            Type conversion: arguments["id"] from JSON is float, but user service
            expects int. int() conversion is safe (truncates decimal part if any).
            
            Design note: No defensive checks (e.g., id > 0) because schema validation
            and type coercion happen before execute(). We trust the contract.
            
            Example result on success:
            ```
              id: 123
              name: John
              surname: Doe
              email: john.doe@example.com
              gender: M
            ```
        """
        # Extract and coerce ID to int (JSON numbers deserialize as float)
        user_id = int(arguments["id"])
        
        # Delegate to UserClient for REST call and response formatting
        return await self._user_client.get_user(user_id)