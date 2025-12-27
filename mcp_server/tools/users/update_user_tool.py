from typing import Any

from mcp_server.models.user_info import UserUpdate
from mcp_server.tools.users.base import BaseUserServiceTool

# ============================================================================
# Update User Tool: MCP tool for partial user information updates
# ============================================================================
# Implements the "update_user" MCP tool, allowing clients to update
# an existing user's information via partial updates (UserUpdate schema).
# ============================================================================


class UpdateUserTool(BaseUserServiceTool):
    """
    MCP tool for updating existing users.
    
    Allows callers to update user information by ID using partial updates.
    The UserUpdate schema (Pydantic) defines which fields can be updated
    (most fields optional for flexibility).
    
    **Schema:** Accepts object with:
    - id: number (required, user's database ID)
    - new_info: UserUpdate object (required, with optional fields)
    """

    @property
    def name(self) -> str:
        """Tool identifier used by MCP clients to invoke this tool."""
        return "update_user"

    @property
    def description(self) -> str:
        """Human-readable description for tool discovery and AI model routing."""
        return "Update an existing user's information"

    @property
    def input_schema(self) -> dict[str, Any]:
        """
        Define expected input parameters as JSON Schema.
        
        Combines two required fields:
        - id: numeric user identifier
        - new_info: UserUpdate Pydantic schema (auto-generated from model)
        
        Returns:
            dict: JSON Schema with type=object, two properties, both required
        
        Remarks:
            UserUpdate.model_json_schema() generates schema with optional fields,
            allowing callers to update only the fields they need (partial updates).
            Example: {"id": 123, "new_info": {"name": "Jane", "email": null}}
        """
        schema = UserUpdate.model_json_schema()
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "number",
                    "description": "The ID of the user to update"
                },
                "new_info": schema
            },
            "required": ["id", "new_info"]
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        """
        Execute the tool: update user's information.
        
        **Flow:**
        1. Extract and convert user ID to int (from JSON number)
        2. Validate new_info dict against UserUpdate schema (Pydantic)
        3. Call UserClient.update_user() with validated model
        4. Return formatted success message from service
        
        Args:
            arguments: Dict with keys "id" (number) and "new_info" (dict).
                      Extracted by MCPServer from JSON-RPC params.arguments.
        
        Returns:
            str: Formatted success message (e.g., "User successfully updated: {...}")
        
        Raises:
            ValueError: If arguments["id"] is not a valid number
            ValidationError: If arguments["new_info"] fails UserUpdate schema validation
            Exception: From UserClient.update_user() if HTTP request fails
        
        Remarks:
            Pydantic validation (model_validate) ensures schema compliance before
            sending to UserClient, preventing invalid data from reaching the service.
            Type conversion int(arguments["id"]) necessary because JSON numbers
            arrive as floats in some JSON implementations.
        """
        # Extract and convert user ID from JSON (number arrives as float)
        user_id = int(arguments["id"])
        
        # Validate new_info against UserUpdate schema; raises ValidationError if invalid
        new_info = UserUpdate.model_validate(arguments["new_info"])
        
        # Delegate to UserClient (async HTTP call to microservice)
        return await self._user_client.update_user(user_id, new_info)

