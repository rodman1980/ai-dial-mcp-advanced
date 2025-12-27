import json
from typing import Optional
from fastapi import FastAPI, Response, Header
from fastapi.responses import StreamingResponse
import uvicorn

from mcp_server.services.mcp_server import MCPServer
from models.request import MCPRequest
from models.response import MCPResponse, ErrorResponse

# ============================================================================
# MCP Server: HTTP endpoint for Model Context Protocol (MCP) tool operations
# ============================================================================
# Provides single endpoint (/mcp) that handles the complete MCP lifecycle:
# 1. Initialize: create session, return capabilities
# 2. Notify: mark session as ready for operations
# 3. Discover: list available tools
# 4. Execute: call tools and stream results via SSE
#
# Protocol: JSON-RPC 2.0 over HTTP with Server-Sent Events (SSE) streaming
# Session Management: UUID-based sessions with ready_for_operation flag
# ============================================================================

MCP_SESSION_ID_HEADER = "Mcp-Session-Id"

app = FastAPI(title="MCP Tools Server", version="1.0.0")
mcp_server = MCPServer()


def _validate_accept_header(accept_header: Optional[str]) -> bool:
    """
    Validate that client accepts both JSON and SSE response formats.
    
    MCP requires clients to handle both application/json (for errors/simple responses)
    and text/event-stream (for streaming tool results).
    
    Args:
        accept_header: HTTP Accept header value (comma-separated MIME types)
    
    Returns:
        True if both application/json and text/event-stream are accepted, False otherwise
    """
    if not accept_header:
        return False
    
    # Parse comma-separated Accept header, normalize to lowercase for comparison
    accept_types = [t.strip().lower() for t in accept_header.split(",")]
    has_json = any("application/json" in t for t in accept_types)
    has_sse = any("text/event-stream" in t for t in accept_types)
    
    return has_json and has_sse


async def _create_sse_stream(messages: list):
    """
    Convert MCP response messages to Server-Sent Events (SSE) format for streaming.
    
    Format: data: {JSON}\n\n followed by data: [DONE]\n\n terminator.
    This allows HTTP clients to receive JSON-RPC responses as a stream.
    
    Args:
        messages: List of MCPResponse objects to stream
    
    Yields:
        Bytes in SSE format: b"data: {...}\n\n"
    """
    for message in messages:
        # Convert response to JSON with exclude_none=True to skip null fields
        event_data = f"data: {json.dumps(message.dict(exclude_none=True))}\n\n"
        yield event_data.encode('utf-8')
    
    # Signal end of stream; client stops reading after this marker
    yield b"data: [DONE]\n\n"


@app.post("/mcp")
async def handle_mcp_request(
        request: MCPRequest,
        response: Response,
        accept: Optional[str] = Header(None),
        mcp_session_id: Optional[str] = Header(None, alias=MCP_SESSION_ID_HEADER)
):
    """
    Single MCP endpoint handling all JSON-RPC requests with proper session lifecycle.
    
    **Session Lifecycle:**
    1. Initialize: create session, no ID required, returns Mcp-Session-Id header
    2. Notify (notifications/initialized): mark session ready, session ID required
    3. Discover/Execute: tools/list, tools/call only work after session is ready
    
    **Error Responses:**
    - 406: Client doesn't accept both JSON and SSE (missing Accept header types)
    - 400: Missing session ID for non-initialize requests, or session not ready
    - 400 (JSON-RPC): Method not found (-32602), tool not found (-32601), etc.
    
    **Important:** All responses (including errors) are streamed as SSE with [DONE] marker.
    
    Args:
        request: JSON-RPC 2.0 request (method, params, id)
        response: FastAPI response object (used to set session ID header)
        accept: HTTP Accept header (must include application/json and text/event-stream)
        mcp_session_id: Mcp-Session-Id header (from client or previous initialize response)
    
    Returns:
        StreamingResponse with SSE-formatted JSON-RPC response
    """
    
    # === PHASE 1: Validate Accept header ===
    # Client must accept both JSON and SSE; otherwise we can't reliably communicate
    if not _validate_accept_header(accept):
        error_response = MCPResponse(
            id="server-error",
            error=ErrorResponse(code=-32600, message="Client must accept both application/json and text/event-stream")
        )
        return Response(
            status_code=406,
            content=error_response.model_dump_json(),
            media_type="application/json"
        )
    
    # === PHASE 2: Handle initialize (creates session, no ID required) ===
    if request.method == "initialize":
        # initialize is special: it doesn't require a session ID and creates one
        mcp_response, session_id = mcp_server.handle_initialize(request)
        if session_id:
            response.headers[MCP_SESSION_ID_HEADER] = session_id
            mcp_session_id = session_id
    else:
        # === PHASE 3: Non-initialize requests require valid session ===
        
        # Step 1: Validate session ID was provided
        if not mcp_session_id:
            error_response = MCPResponse(
                id="server-error",
                error=ErrorResponse(code=-32600, message="Missing session ID")
            )
            return Response(
                status_code=400,
                content=error_response.model_dump_json(),
                media_type="application/json"
            )
        
        # Step 2: Retrieve session and verify it exists
        session = mcp_server.get_session(mcp_session_id)
        if not session:
            return Response(
                status_code=400,
                content="No valid session ID provided"
            )
        
        # Step 3: Handle notifications/initialized - gates all subsequent tool operations
        # Client MUST send this before calling tools/list or tools/call
        if request.method == "notifications/initialized":
            session.ready_for_operation = True
            return Response(
                status_code=202,  # 202 Accepted for notifications (no body expected)
                headers={MCP_SESSION_ID_HEADER: session.session_id}
            )
        
        # Step 4: Verify session is ready before allowing tool discovery/execution
        # This prevents tools/list or tools/call before notifications/initialized
        if not session.ready_for_operation:
            error_response = MCPResponse(
                id="server-error",
                error=ErrorResponse(code=-32600, message="Session not initialized")
            )
            return Response(
                status_code=400,
                content=error_response.model_dump_json(),
                media_type="application/json"
            )
        
        # Step 5: Route to appropriate handler based on method
        if request.method == "tools/list":
            # Synchronous: return all available tools and their schemas
            mcp_response = mcp_server.handle_tools_list(request)
        elif request.method == "tools/call":
            # Asynchronous: execute tool and wrap result, handle any exceptions
            mcp_response = await mcp_server.handle_tools_call(request)
        else:
            # Unknown method not in our handlers
            mcp_response = MCPResponse(
                id=request.id,
                error=ErrorResponse(code=-32602, message=f"Method '{request.method}' not found")
            )
    
    # === PHASE 4: Stream response as SSE ===
    # All responses (success, error, notifications) are streamed with [DONE] terminator
    return StreamingResponse(
        content=_create_sse_stream([mcp_response]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",  # Prevent caching of streaming responses
            "Connection": "keep-alive",   # Keep connection open for long operations
            MCP_SESSION_ID_HEADER: mcp_session_id if mcp_session_id else ""
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
        log_level="debug"
    )