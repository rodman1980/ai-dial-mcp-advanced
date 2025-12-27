# ============================================================================
# MCP Protocol Request Model
# ============================================================================
# Pydantic model for parsing and validating JSON-RPC 2.0 requests sent to
# the MCP server. Enforces structure and types for all incoming requests,
# enabling type-safe request handling in MCPServer.
# ============================================================================

from typing import Any, Union
from pydantic import BaseModel


class MCPRequest(BaseModel):
    """
    JSON-RPC 2.0 request wrapper for MCP protocol communication.
    
    Parses and validates incoming MCP requests (initialize, tools/list, tools/call,
    notifications) into a strongly-typed structure. Pydantic automatically:
    - Validates JSON structure and field types
    - Coerces string IDs to int when possible
    - Provides helpful error messages for malformed requests
    
    Attributes:
        jsonrpc: Protocol version identifier (always "2.0" per JSON-RPC 2.0 spec)
        id: Request identifier for correlating responses to requests. None for
            notifications (fire-and-forget messages with no expected response).
            Supports string, int, or None per JSON-RPC 2.0 spec.
        method: The RPC method name to invoke (e.g., "initialize", "tools/list",
                "tools/call", "notifications/initialized")
        params: Optional dictionary of method-specific parameters. None if the
                method requires no arguments. Maps directly to JSON-RPC params field.
    
    Examples:
        Initialize request:
            MCPRequest(
                jsonrpc="2.0",
                id=1,
                method="initialize",
                params={"protocolVersion": "2024-11-05", ...}
            )
        
        Notification (no response expected):
            MCPRequest(
                jsonrpc="2.0",
                id=None,
                method="notifications/initialized",
                params=None
            )
    """
    jsonrpc: str = "2.0"  # JSON-RPC version (always "2.0")
    id: Union[str, int, None] = None  # Request ID for response correlation; None for notifications
    method: str  # RPC method name to invoke
    params: dict[str, Any] | None = None  # Method parameters (optional)
