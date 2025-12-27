from typing import Any

from mcp_server.tools.users.base import BaseUserServiceTool

# ============================================================================
# Delete User Tool: MCP tool for removing users by their ID (destructive)
# ============================================================================
# Implements the "delete_users" MCP tool, allowing clients to permanently
# delete user records. This is a destructive operation that cannot be undone.
# Requires the user ID as a mandatory parameter.
# ============================================================================


class DeleteUserTool(BaseUserServiceTool):
    """
    MCP tool for deleting a specific user by their unique identifier.
    
    **WARNING: DESTRUCTIVE OPERATION** – This tool permanently removes a user
    record from the user service. There is no undo; callers should verify the
    target user ID before invoking.
    
    **Schema:** Requires exactly one parameter:
    - id: number (user's unique identifier to delete)
    
    **Side Effects:** Removes user from backend service; cascading effects
    (e.g., deleting associated records) depend on service implementation.
    
    **Error Handling:** Returns error if user not found (404) or if deletion
    fails (permissions, service unavailable, etc.).
    """

    @property
    def name(self) -> str:
        """Tool identifier used by MCP clients to invoke this tool."""
        return "delete_users"

    @property
    def description(self) -> str:
        """Human-readable description for tool discovery and AI model routing."""
        return "Delete a user by ID"

    @property
    def input_schema(self) -> dict[str, Any]:
        """
        Define expected input parameters as JSON Schema.
        
        Specifies a single required numeric parameter (id) for deletion.
        JSON Schema definition ensures:
        - Client validates user ID is numeric before calling execute()
        - AI models understand this is a destructive tool requiring exactly one param
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
            
            This single-parameter design mirrors get_user_by_id for consistency
            and forces callers to be explicit about which user they're deleting
            (prevents accidental multi-user deletes).
        """
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "number",
                    "description": "The ID of the user to delete"
                }
            },
            "required": ["id"]
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        """
        Execute the tool: delete user by ID from the service.
        
        **Flow:**
        1. Extract user ID from arguments dict (guaranteed to exist by schema)
        2. Coerce to int (JSON numbers deserialize as float; user service expects int)
        3. Call UserClient.delete_user(user_id) which:
           - Makes HTTP DELETE to user service /user/{id} endpoint
           - Returns confirmation message as string on success
           - Raises exception (caught by MCPServer) if user not found (404)
             or deletion fails (permission denied, service error, etc.)
        
        Args:
            arguments: Dict with single key "id" (numeric value).
                      Guaranteed to be present by input_schema validation.
        
        Returns:
            str: Confirmation message (typically formatted as markdown block
                 with status or affected user details, per UserClient format).
        
        Raises:
            Exception: Raised by UserClient if HTTP request fails (e.g., 404 not found,
                      403 forbidden, 500 server error, network timeout). MCPServer catches
                      and wraps in ToolCallResult with isError=True.
        
        Remarks:
            Type conversion: arguments["id"] from JSON is float, but user service
            expects int. int() conversion is safe (truncates decimal part if any).
            
            Design note: No defensive checks (e.g., id > 0) because schema validation
            and type coercion happen before execute(). We trust the contract.
            
            Side effects: This method has permanent side effects (deletes data).
            Callers are responsible for ensuring the target user ID is correct
            before invocation. No confirmation mechanism exists at MCP layer.
            
            Example result on success (depends on UserClient implementation):
            ```
              User with id 123 deleted successfully
            ```
            
            Example error:
            ```
              Error: User with id 999 not found (404)
            ```
        """
        # Extract and coerce ID to int (JSON numbers deserialize as float)
        user_id = int(arguments["id"])
        
        # Delegate to UserClient for REST DELETE call and response formatting
        # WARNING: This permanently removes the user record from the service
        return await self._user_client.delete_user(user_id)