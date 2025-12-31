---
title: ADR-001 - Dual Client Implementation Strategy
description: Rationale for maintaining both framework-based and pure Python MCP clients
version: 1.0.0
last_updated: 2025-12-30
status: Accepted
tags: [adr, architecture, mcp-client, learning]
---

# ADR-001: Dual Client Implementation Strategy

## Status

**Accepted** (2025-12-30)

## Context

The project requires MCP client functionality to connect AI agents to the MCP server. Two approaches exist:

1. **Framework-Based**: Use `fastmcp` library's `ClientSession` and `streamablehttp_client` for protocol abstraction
2. **Pure Python**: Implement HTTP/SSE handling directly with `aiohttp` and manual JSON-RPC envelope construction

### Problem Statement

Should we implement one client approach or both? What are the trade-offs?

### Constraints

- **Learning Project**: Primary goal is education, not production efficiency
- **Protocol Understanding**: Students should understand MCP internals (JSON-RPC, SSE)
- **Time Budget**: Limited to 9-13 hours total implementation time
- **Maintainability**: Code should remain clear and documented

## Decision

**Implement both client approaches with different purposes:**

1. **MCPClient** ([mcp_client.py](../../agent/clients/mcp_client.py))
   - Uses `fastmcp` library for production-ready implementation
   - Minimal boilerplate, focus on business logic
   - **Purpose**: Demonstrate best practices for real-world usage

2. **CustomMCPClient** ([custom_mcp_client.py](../../agent/clients/custom_mcp_client.py))
   - Pure Python with explicit HTTP/SSE handling
   - Manual JSON-RPC construction, SSE parsing
   - **Purpose**: Educational - expose protocol mechanics

Both clients implement the same interface (interchangeable in agent).

## Rationale

### Benefits of Dual Approach

1. **Learning Depth**:
   - Framework client shows "what to do in production"
   - Pure Python client shows "how protocols actually work"
   - Students learn both abstraction and implementation

2. **Protocol Understanding**:
   - Custom client forces understanding of:
     - SSE format (`data: {...}\n\n`, `[DONE]` markers)
     - JSON-RPC 2.0 structure (id correlation, error handling)
     - Session management (header propagation)
   - Cannot "black box" protocol details

3. **Debugging Skills**:
   - Pure Python client aids debugging (step through SSE parsing)
   - Framework client sometimes obscures errors with abstractions
   - Having both helps triangulate issues

4. **Code Comparison**:
   - Side-by-side comparison demonstrates value of frameworks
   - Students see LOC reduction (~50% fewer lines with fastmcp)
   - Appreciate trade-offs (abstraction vs control)

5. **Testing Flexibility**:
   - Can swap clients in agent (one-line change in app.py)
   - Validates that both implementations are protocol-compliant
   - Exposes implementation bugs if behavior differs

### Costs of Dual Approach

1. **Increased Complexity**:
   - Maintains two codebases with similar functionality
   - Risk of divergence if protocol updates
   - ~3-4 hours additional effort for pure Python client

2. **Duplication**:
   - Some logic duplicated (tool discovery, call execution)
   - Testing burden increases (must validate both)

3. **Maintenance**:
   - Two clients to update if MCP spec changes
   - Documentation must cover both approaches

### Why Costs Are Acceptable

- **Learning Project Scope**: One-time implementation, not long-term maintenance
- **Time Investment**: 3-4 hours for CustomMCPClient is valuable learning time
- **Clear Separation**: Files isolated, no shared mutable state
- **Protocol Stability**: MCP spec unlikely to change during course

## Implementation Strategy

### Code Organization

```
agent/clients/
├── mcp_client.py          # Framework-based (production pattern)
├── custom_mcp_client.py   # Pure Python (educational)
└── dial_client.py         # Uses either client (abstraction)
```

### Interface Contract

Both clients must implement:

```python
class MCPClientProtocol:
    @classmethod
    async def create(cls, server_url: str) -> Self:
        """Factory method: instantiate and connect"""
    
    async def connect(self) -> None:
        """Initialize session (internal, called by create)"""
    
    async def get_tools(self) -> list[dict[str, Any]]:
        """Return tools in OpenAI format"""
    
    async def call_tool(self, name: str, args: dict) -> Any:
        """Execute tool and return result"""
```

### Usage Pattern

**Agent Integration** ([app.py](../../agent/app.py)):

```python
# Switch between clients by changing import/class name
from agent.clients.mcp_client import MCPClient
# from agent.clients.custom_mcp_client import CustomMCPClient as MCPClient

# Rest of code unchanged (polymorphic usage)
ums_client = await MCPClient.create("http://localhost:8006/mcp")
tools = await ums_client.get_tools()
```

## Alternatives Considered

### Alternative 1: Framework Only

**Rejected** - Insufficient learning depth. Students wouldn't understand:
- How SSE parsing works
- JSON-RPC envelope structure
- Session lifecycle mechanics

**Result**: Shallow understanding, difficulty debugging protocol issues.

---

### Alternative 2: Pure Python Only

**Rejected** - Doesn't teach production patterns. Students would:
- Reinvent wheels (HTTP client management, streaming)
- Miss framework benefits (error handling, retry logic)
- Write more verbose, less maintainable code

**Result**: Good protocol knowledge, but impractical for real projects.

---

### Alternative 3: Single Client with Layers

Implement one client with two modes:
- `MCPClient(mode="framework")` uses fastmcp
- `MCPClient(mode="custom")` uses aiohttp

**Rejected** - Excessive complexity. Single class would:
- Mix abstractions (framework vs manual)
- Complicate conditionals throughout code
- Obscure differences between approaches

**Result**: Worst of both worlds (complexity without clarity).

## Consequences

### Positive

1. **Comprehensive Learning**: Students understand both framework usage and protocol internals
2. **Flexible Testing**: Can validate implementations against each other
3. **Real-World Preparation**: See production patterns alongside educational examples
4. **Debugging Aid**: Pure Python client helps diagnose protocol issues
5. **Documentation Value**: Side-by-side comparison in docs demonstrates trade-offs

### Negative

1. **Increased Scope**: 3-4 additional hours of implementation time
2. **Maintenance Burden**: Two clients to update if protocol evolves
3. **Potential Confusion**: Students may wonder "which one to use?"
4. **Testing Overhead**: Must validate both clients work identically

### Mitigation Strategies

**For Confusion**:
- Clear documentation stating MCPClient = production, CustomMCPClient = learning
- Inline comments explaining "why this line is needed" in CustomMCPClient
- README section: "When to use which client"

**For Maintenance**:
- Shared protocol constants (MCP_SESSION_ID_HEADER)
- Integration tests that run both clients against same server
- Protocol changes flagged in changelog with client update checklist

**For Testing**:
- Pytest fixtures that parameterize client type
- E2E tests swap clients via environment variable
- Postman collection validates server independently

## Validation

### Success Criteria

- [ ] Both clients successfully initialize session (Mcp-Session-Id header captured)
- [ ] Both clients retrieve identical tool lists from server
- [ ] Both clients execute same tool call with identical results
- [ ] Agent runs without modification when swapping client classes
- [ ] Documentation clearly explains rationale for dual implementation

### Testing Strategy

**Unit Tests** (TODO):
```python
@pytest.mark.parametrize("client_class", [MCPClient, CustomMCPClient])
async def test_tool_discovery(client_class):
    client = await client_class.create("http://localhost:8006/mcp")
    tools = await client.get_tools()
    assert len(tools) == 5
```

**Integration Test** (manual):
1. Run agent with MCPClient → Execute query → Record output
2. Swap to CustomMCPClient in app.py → Execute same query
3. Compare outputs (should be identical)

**Protocol Validation** (Postman):
- Both clients send identical HTTP requests (validated via network capture)
- Both parse SSE responses correctly (curl -N comparison)

## Related Decisions

- See [ADR-002](./ADR-002-session-management-strategy.md) for session lifecycle design
- See [Architecture](../architecture.md#mcp-client-agentclients) for component overview

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic)
- [fastmcp Library Documentation](https://pypi.org/project/fastmcp/)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [Server-Sent Events (SSE) MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

---

**Date**: 2025-12-30  
**Author**: Project Team  
**Reviewers**: N/A (Learning project)  
**Next Review**: After Phase 4 completion
