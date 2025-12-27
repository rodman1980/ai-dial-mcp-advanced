# ============================================================================
# User Service Tool Base Class
# ============================================================================
# Provides a specialized abstract base for all user management tools.
# Extends BaseTool with UserClient injection for consistent user service access.
# ============================================================================

from abc import ABC

from mcp_server.tools.base import BaseTool
from mcp_server.tools.users.user_client import UserClient


class BaseUserServiceTool(BaseTool, ABC):
    """
    Abstract base class for user service MCP tools.
    
    This class extends BaseTool and provides dependency injection of UserClient,
    ensuring all user-specific tools (create_user, search_users, etc.) have
    consistent access to the user service API through _user_client.
    
    **Responsibility:**
    - Initialize concrete user tools with a configured UserClient instance
    - Enforce that all user tools inherit both BaseTool contract and UserClient access
    
    **Design Pattern:**
    - Template Method: Derived classes implement abstract properties/methods from BaseTool
    - Dependency Injection: UserClient injected via constructor parameter
    
    **Usage:**
    Concrete tools like CreateUserTool inherit from this class:
    
        class CreateUserTool(BaseUserServiceTool):
            @property
            def name(self) -> str:
                return "add_user"
            
            async def execute(self, arguments: dict) -> str:
                user = UserCreate.model_validate(arguments)
                return await self._user_client.add_user(user)
    """

    def __init__(self, user_client: UserClient):
        """
        Initialize the user service tool with a UserClient instance.
        
        Args:
            user_client: Configured UserClient for making requests to the user service API.
                        This is injected by the tool registry and provides methods like
                        add_user(), search_users(), get_user_by_id(), etc.
        
        Side Effect:
            Calls parent BaseTool.__init__() to complete abstract base initialization.
        """
        super().__init__()
        self._user_client = user_client
