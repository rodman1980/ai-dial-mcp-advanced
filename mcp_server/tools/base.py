from abc import ABC, abstractmethod
from typing import Any, Dict

# ============================================================================
# Tool Base Class: Abstract interface for MCP tools
# ============================================================================
# Defines the contract that all MCP tools must follow. Each tool represents
# a single operation (create_user, search_users, etc.) with its own schema.
#
# Design Pattern: Template Method (abstract methods define required properties)
# Responsibility: Enforces consistent tool interface across all implementations
# ============================================================================


class BaseTool(ABC):
    """
    Abstract base class defining the MCP tool interface.
    
    All concrete tools (CreateUserTool, SearchUsersTool, etc.) must inherit
    from this class and implement the required abstract properties/methods.
    This ensures consistent schema definition and execution signatures.
    
    **Contract:**
    - name: Unique tool identifier (lowercase, no spaces)
    - description: Human-readable explanation of what the tool does
    - input_schema: JSON Schema defining expected arguments (for validation)
    - execute(): Async method that performs the actual tool operation
    
    **Lifecycle:**
    1. Tool is registered in MCPServer._register_tools()
    2. to_mcp_tool() is called to generate JSON Schema for discovery
    3. execute() is called by MCPServer.handle_tools_call() during operation
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique tool identifier used by MCP clients to invoke this tool.
        
        Convention: lowercase with underscores (e.g., "add_user", "search_users")
        This name is exposed in tools/list response and used in tools/call requests.
        
        Returns:
            str: Tool name identifier
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of the tool's purpose and behavior.
        
        This description is included in the tools/list response and helps
        AI models understand when and how to use this tool. Should be concise
        but informative (2-3 sentences).
        
        Returns:
            str: Tool description for discovery/documentation
        """
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """
        JSON Schema describing expected tool arguments and their types.
        
        Typically generated from Pydantic models using model_json_schema().
        This schema is used for:
        - Client validation before calling the tool
        - AI model understanding of required parameters
        - OpenAI/Claude parameter generation
        
        Example for a tool accepting user_id:
        {
            "type": "object",
            "properties": {
                "id": {"type": "number", "description": "User ID"}
            },
            "required": ["id"]
        }
        
        Returns:
            Dict[str, Any]: JSON Schema object
        """
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> str:
        """
        Execute the tool operation with provided arguments.
        
        This method performs the actual tool logic: validates input,
        calls external services (UserClient), and returns formatted results.
        
        **Preconditions:**
        - arguments must be validated against input_schema before calling
        - Tool implementation should handle exceptions gracefully
        
        **Error Handling:**
        - Raise Exception with descriptive message on failure
        - MCPServer.handle_tools_call() will catch and wrap in isError: true response
        
        **Output Format:**
        - Must return a string (never dict/list)
        - Result is wrapped in MCP ContentItem(type="text", text=result)
        - Formatting typically uses backticks and structured text for readability
        
        Args:
            arguments: Dictionary of tool arguments as passed by MCP client.
                      These have been extracted from the JSON-RPC params.arguments field.
        
        Returns:
            str: Formatted tool result. Will be wrapped in MCP content format
                and included in the tools/call response result.
        
        Raises:
            Exception: Any exception raised will be caught by MCPServer and
                      included in the response with isError: true flag.
        """
        pass

    def to_mcp_tool(self) -> Dict[str, Any]:
        """
        Convert tool definition to MCP-compliant JSON Schema format.
        
        This method is called by MCPServer.handle_tools_list() to generate
        the response that MCP clients receive when discovering available tools.
        
        The output format allows clients/AI models to understand:
        - Tool name (for invocation)
        - Tool purpose (description)
        - Expected parameters (inputSchema for validation)
        
        Returns:
            Dict[str, Any]: MCP tool definition with keys:
                - "name": Tool identifier
                - "description": Tool purpose
                - "inputSchema": JSON Schema of parameters
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }
