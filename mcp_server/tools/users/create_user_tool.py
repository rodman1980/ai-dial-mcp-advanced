# ==============================================================================
# MCP Tool: Create User
# ==============================================================================
# Implements the "add_user" MCP tool for creating new users in the user service.
# Validates input against the UserCreate schema and delegates to the UserClient.
# ==============================================================================

from typing import Any

from mcp_server.models.user_info import UserCreate
from mcp_server.tools.users.base import BaseUserServiceTool


class CreateUserTool(BaseUserServiceTool):
    """
    MCP tool for creating a new user in the user service.
    
    Inherits session and user service client management from BaseUserServiceTool.
    Provides schema-based validation through Pydantic's UserCreate model.
    
    **Lifecycle:**
    1. MCP server calls to_mcp_tool() to expose this tool to clients
    2. Client calls execute() with validated user creation parameters
    3. execute() validates args against input_schema and delegates to UserClient
    4. Returns formatted result string wrapped in MCP ContentItem structure
    """

    @property
    def name(self) -> str:
        """
        Returns the tool identifier for MCP discovery and invocation.
        
        The "add_user" name is what clients use when calling tools/call requests.
        
        Returns:
            str: The MCP tool name ("add_user")
        """
        return "add_user"

    @property
    def description(self) -> str:
        """
        Provides human-readable description of the tool's purpose.
        
        Used by MCP clients and AI models to understand when to use this tool.
        
        Returns:
            str: Tool description for discovery documentation
        """
        return "Create a new user with the provided information"

    @property
    def input_schema(self) -> dict[str, Any]:
        """
        Generates JSON Schema for user creation parameters.
        
        Uses Pydantic's model_json_schema() to auto-generate schema from UserCreate
        fields (name, email, age, etc.). This schema is returned in tools/list response
        so clients and AI models know which fields are required and their types.
        
        Returns:
            dict[str, Any]: JSON Schema describing required/optional user fields
        """
        return UserCreate.model_json_schema()

    async def execute(self, arguments: dict[str, Any]) -> str:
        """
        Execute user creation with validated input.
        
        **Flow:**
        1. Validates arguments against UserCreate schema (raises ValidationError if invalid)
        2. Converts dict args to UserCreate Pydantic model instance
        3. Delegates creation to UserClient.add_user() (handles REST call to external service)
        4. Returns formatted string result
        
        **Error Handling:**
        - Pydantic ValidationError raised if arguments don't match input_schema
        - UserClient exceptions propagate (network errors, service errors, duplicate emails)
        - MCP server catches exceptions and wraps in isError: true response
        
        Args:
            arguments: Dictionary of user creation parameters validated against input_schema.
                      Expected keys: name, email, age (from UserCreate model).
        
        Returns:
            str: Formatted user creation result (e.g., "User 'John Doe' created with ID: 123")
        
        Raises:
            pydantic.ValidationError: If arguments don't match UserCreate schema
            Exception: Any error from UserClient.add_user() (e.g., network, service errors)
        """
        # Validate input dict against UserCreate schema and create model instance
        user = UserCreate.model_validate(arguments)
        
        # Delegate to user service client for REST API call and return formatted result
        return await self._user_client.add_user(user)