# ============================================================================
# MCP Protocol Response Models
# ============================================================================
# Defines Pydantic models for all MCP server response structures.
# These models serialize to JSON-RPC 2.0 compliant responses following the
# MCP specification (https://modelcontextprotocol.io/).
# Responsibilities:
# - Validate response structure and required fields
# - Convert Python objects to JSON-RPC format
# - Provide type safety for response handling in MCPServer
# ============================================================================

from typing import Any, Union, List, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    JSON-RPC error response structure.
    
    Represents an error that occurred during MCP request processing.
    Follows JSON-RPC 2.0 error object specification.
    
    Attributes:
        code: Numeric error code (e.g., -32600 for invalid request)
        message: Human-readable error description
        data: Optional error context/metadata (e.g., validation errors)
    """
    code: int
    message: str
    data: dict[str, Any] | None = None


class ContentItem(BaseModel):
    """
    Single content item in a tool response.
    
    Wraps text results returned by MCP tools. The MCP protocol requires
    tool responses to be wrapped in ContentItem objects (supporting multiple
    content types in future, currently only 'text' is used).
    
    Attributes:
        type: Content type identifier (currently "text" for plain text results)
        text: The actual tool response content (formatted string)
    """
    type: str  # MCP-defined type: "text", "image", etc.
    text: str  # Tool execution result as formatted string


class ToolCallResult(BaseModel):
    """
    MCP-compliant result wrapper for tool execution responses.
    
    Wraps the output of a tool call for transmission back to the MCP client.
    The content list allows for multiple result items (though typically only
    one ContentItem is returned per tool invocation).
    
    Attributes:
        content: List of ContentItem objects returned by the tool.
                 Always contains at least one item on success.
        isError: Optional flag to indicate tool execution failure.
                 If True, content contains error message instead of result.
    """
    content: List[ContentItem]  # Tool result wrapped in ContentItem(s)
    isError: Optional[bool] = None  # Signals tool execution error to client


class MCPResponse(BaseModel):
    """
    JSON-RPC 2.0 response envelope for all MCP server responses.
    
    Wraps all MCP server responses (success or error) in a standardized
    JSON-RPC 2.0 format. Either 'result' OR 'error' is set, but not both.
    
    Attributes:
        jsonrpc: Protocol version string (always "2.0" for JSON-RPC 2.0)
        id: Request identifier echoed back to correlate request/response pairs.
            None for notifications (fire-and-forget requests).
        result: Success case: contains tools/list, tools/call, initialize results.
                Set to None if 'error' is present.
        error: Failure case: contains ErrorResponse with code, message, data.
               Set to None if 'result' is present.
    
    Note:
        extra = "allow" permits additional fields for compatibility with
        extensions and protocol evolution.
    """
    jsonrpc: str = "2.0"  # Always "2.0" per JSON-RPC 2.0 spec
    id: Union[str, int, None] = None  # Request ID for matching responses; None for notifications
    result: Optional[dict[str, Any]] = Field(default=None)  # Success result (mutually exclusive with error)
    error: Optional[ErrorResponse] = Field(default=None)  # Error response (mutually exclusive with result)

    class Config:
        extra = "allow"  # Allow extra fields for protocol evolution compatibility
