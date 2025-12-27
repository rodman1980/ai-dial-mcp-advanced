from typing import Any

from mcp_server.tools.users.base import BaseUserServiceTool

# ============================================================================
# Search Users Tool: MCP tool for flexible user search with optional filters
# ============================================================================
# Implements the "search_users" MCP tool, allowing clients to query users
# by any combination of name, surname, email, or gender filters.
# All filters are optional; empty filters return all users.
# ============================================================================


class SearchUsersTool(BaseUserServiceTool):
    """
    MCP tool for searching users with optional filters.
    
    Provides flexible search capability across multiple user attributes.
    All filter parameters are optional—callers can search by any combination
    or provide no filters to retrieve all users.
    
    **Schema:** Accepts object with optional properties:
    - name: string (user's first name)
    - surname: string (user's last name)
    - email: string (user's email address)
    - gender: string (user's gender)
    
    **No required fields** allows empty search queries (returns all users).
    """

    @property
    def name(self) -> str:
        """Tool identifier used by MCP clients to invoke this tool."""
        return "search_users"

    @property
    def description(self) -> str:
        """Human-readable description for tool discovery and AI model routing."""
        return "Search for users by name, surname, email, or gender"

    @property
    def input_schema(self) -> dict[str, Any]:
        """
        Define expected input parameters as JSON Schema.
        
        Describes four optional string properties for flexible filtering:
        - name: Search by first name (case-sensitive per service behavior)
        - surname: Search by last name (case-sensitive per service behavior)
        - email: Search by email address (exact match or partial, per service)
        - gender: Search by gender field value (case-sensitive per service)
        
        Returns:
            dict: JSON Schema with type=object, four optional properties.
                  No required fields allows empty searches.
        
        Remarks:
            All properties are strings; no required array means all are optional.
            This design allows AI models to build queries incrementally:
            - Search by name only: {"name": "John"}
            - Multi-field search: {"name": "John", "email": "@example.com"}
            - All users: {} (empty object, no filters applied)
            
            The UserClient.search_users() method handles sparse params gracefully
            (only includes non-None values in REST query string).
        """
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "User's first name"
                },
                "surname": {
                    "type": "string",
                    "description": "User's last name"
                },
                "email": {
                    "type": "string",
                    "description": "User's email address"
                },
                "gender": {
                    "type": "string",
                    "description": "User's gender"
                }
            }
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        """
        Execute the tool: search for users with provided filters.
        
        **Flow:**
        1. Accept arguments dict with optional filter keys (name, surname, email, gender)
        2. Delegate to UserClient.search_users(**arguments) for REST call
        3. UserClient filters out None values and builds sparse query params
        4. Return formatted list of matching users as markdown blocks
        
        Args:
            arguments: Dict with keys matching input_schema properties.
                      Keys may be missing (treated as None/no filter).
                      Example: {"name": "John"} or {"email": "@example.com"}
        
        Returns:
            str: Formatted user list (one markdown code block per user).
                 Also prints result count to stdout via UserClient.
        
        Remarks:
            The **arguments unpacking passes all optional filters to UserClient.
            This allows UserClient to decide which params to include in the
            REST request (skipping empty/None values for clean query strings).
            
            Design note: No validation here; schema validation happens before
            execute() is called by MCPServer. This keeps the method simple.
            
            Example result:
            ```
              id: 123
              name: John
              email: john@example.com
            ```
            ```
              id: 456
              name: Jane
              email: jane@example.com
            ```
        """
        # Delegate to UserClient with all filter parameters
        # UserClient.search_users(**kwargs) handles sparse params gracefully
        return await self._user_client.search_users(**arguments)