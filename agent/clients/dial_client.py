# ============================================================================
# DIAL API Client with MCP Tool Integration
# ============================================================================
# Orchestrates AI model interactions (via Azure OpenAI) with tool execution
# through MCP clients. Implements agentic loop: stream AI response → detect
# tool calls → execute via MCP → feed results back to AI → repeat until done.
#
# **Execution Flow:**
# 1. get_completion() → _stream_response() to generate AI response with tool calls
# 2. Detect tool_calls in AI response (structured as JSON objects)
# 3. _call_tools() executes each tool via appropriate MCP client from mapping
# 4. Tool results added to message history as Role.TOOL messages
# 5. Recursively call get_completion() to continue agent loop (tool results → new AI response)
# 6. Return final AI message when no more tool calls are needed
#
# **Key Responsibility:** Bridge between AI model decision-making and tool execution,
# managing message history and handling streaming + async tool execution.
# ============================================================================

import json
from collections import defaultdict
from typing import Any

from openai import AsyncAzureOpenAI

from agent.clients.custom_mcp_client import CustomMCPClient
from agent.models.message import Message, Role
from agent.clients.mcp_client import MCPClient


class DialClient:
    """
    Orchestrates AI-driven tool calling with MCP server integration.
    
    Manages streaming interactions with Azure OpenAI (DIAL) and routes tool calls
    to registered MCP clients. Implements agent loop with recursive tool execution:
    AI generates response with tool calls → tools execute → results feed back to AI.
    
    **Precondition:**
    - All tools passed to __init__ must have a corresponding entry in tool_name_client_map
    - MCP clients must be already initialized (connected to their servers)
    
    **Side Effects:**
    - Prints streaming tokens to stdout (marked with "🤖: " prefix)
    - Modifies messages list in place (appends AI responses and tool results)
    """

    def __init__(
            self,
            api_key: str,
            endpoint: str,
            tools: list[dict[str, Any]],
            tool_name_client_map: dict[str, MCPClient | CustomMCPClient]
    ):
        """
        Initialize DIAL client with OpenAI credentials and MCP tool mapping.
        
        Args:
            api_key: Azure OpenAI API key for authentication
            endpoint: Azure endpoint URL (e.g., https://ai-proxy.lab.epam.com)
            tools: List of tool definitions in OpenAI format ({"type": "function", "function": {...}})
            tool_name_client_map: Maps tool names to their MCP client instances for execution
        
        Side Effects:
            Creates AsyncAzureOpenAI instance with provided credentials
        """
        self.tools = tools
        self.tool_name_client_map = tool_name_client_map
        self.openai = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=""
        )

    def _collect_tool_calls(self, tool_deltas):
        """
        Aggregate tool call deltas from streaming chunks into complete tool calls.
        
        OpenAI streaming returns tool calls incrementally (function name, arguments in chunks).
        This method aggregates them by tool index into complete call objects ready for execution.
        
        **Streaming Pattern:**
        - Delta 1: {"index": 0, "id": "call_123", "function": {"name": "add_user"}}
        - Delta 2: {"index": 0, "function": {"arguments": "{\"name\": \""}}
        - Delta 3: {"index": 0, "function": {"arguments": "John\"}"}}
        Result: [{"id": "call_123", "function": {"name": "add_user", "arguments": "{...}"}, "type": "function"}]
        
        Args:
            tool_deltas: List of ToolCallDelta objects from streaming chunks (from openai.types.chat.completion_create_params)
        
        Returns:
            List of complete tool call dictionaries with id, function (name + arguments), and type
        """
        # Use defaultdict to auto-initialize tool entry on first reference by index
        tool_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        for delta in tool_deltas:
            idx = delta.index
            # Accumulate tool attributes from partial deltas
            if delta.id: tool_dict[idx]["id"] = delta.id
            if delta.function.name: tool_dict[idx]["function"]["name"] = delta.function.name
            # Arguments come in chunks; concatenate to build complete JSON
            if delta.function.arguments: tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type: tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _stream_response(self, messages: list[Message]) -> Message:
        """
        Stream OpenAI response and collect tool calls from streaming chunks.
        
        Makes streaming request to Azure OpenAI with current message history and tool definitions.
        Processes each chunk to accumulate text content and tool call deltas. Prints streamed tokens
        in real-time for user feedback.
        
        **Streaming Flow:**
        1. Create streaming completion request with gpt-4o model
        2. Iterate over response chunks
        3. Extract delta.content for text streaming (print live)
        4. Collect delta.tool_calls for later aggregation (may be empty)
        5. Return Message with accumulated content and aggregated tool_calls
        
        Args:
            messages: Conversation history (list of Message objects with role and content)
        
        Returns:
            Message object with role=Role.AI, content (text response), and tool_calls (if any)
        
        **Precondition:**
        - self.openai must be initialized (set in __init__)
        - messages must be valid Message objects with to_dict() method
        
        **Side Effects:**
        - Prints streaming tokens to stdout (prefixed with "🤖: ")
        - Network I/O to Azure OpenAI (streaming connection)
        """
        # Create streaming completion with tools enabled for function calling
        stream = await self.openai.chat.completions.create(
            **{
                "model": "gpt-4o",
                "messages": [msg.to_dict() for msg in messages],
                "tools": self.tools,
                "temperature": 0.0,  # Deterministic responses for consistent tool selection
                "stream": True
            }
        )

        content = ""
        tool_deltas = []

        print("🤖: ", end="", flush=True)

        # Process streaming chunks in real-time
        async for chunk in stream:
            delta = chunk.choices[0].delta

            # Stream text content to stdout immediately for user feedback
            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content

            # Collect tool call fragments for later aggregation
            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

        print()  # Newline after streaming output
        
        return Message(
            role=Role.AI,
            content=content,
            tool_calls=self._collect_tool_calls(tool_deltas) if tool_deltas else []
        )

    async def get_completion(self, messages: list[Message]) -> Message:
        """
        Main agent loop: stream AI response and execute tools recursively until done.
        
        **Agent Loop Logic:**
        1. Stream AI response (which may include tool calls)
        2. If AI generated tool calls:
           - Append AI message to history (required for tool result association)
           - Execute all tools via _call_tools() (which appends tool results to messages)
           - Recursively call get_completion() to continue agent loop with tool results
        3. If no tool calls: return AI message as final response
        
        This implements the standard agentic pattern where tool execution feeds results
        back into the next AI turn, allowing multi-step problem solving.
        
        Args:
            messages: Current conversation history (mutable list updated in place)
        
        Returns:
            Final AI message (with no tool calls) after all tool executions complete
        
        **Precondition:**
        - messages list must be mutable (will be modified with AI and tool messages)
        - Messages should contain proper role assignments (Role.SYSTEM, Role.USER, etc.)
        
        **Side Effects:**
        - Modifies messages list (appends AI response, tool results, and recursive responses)
        - Prints streaming output to stdout via _stream_response()
        - Network I/O to MCP servers and Azure OpenAI
        """
        ai_message: Message = await self._stream_response(messages)

        # Continue agent loop if tools were called, otherwise return final response
        if ai_message.tool_calls:
            messages.append(ai_message)  # Add AI message before tool results for context
            await self._call_tools(ai_message, messages)
            # Recursively feed tool results back to AI for continued reasoning
            return await self.get_completion(messages)

        return ai_message

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """
        Execute all tool calls from AI response using registered MCP clients.
        
        For each tool call in the AI message:
        1. Extract tool name and parse JSON arguments
        2. Look up corresponding MCP client from tool_name_client_map
        3. Execute tool via MCP client (async call to remote server)
        4. Append tool result to messages as Role.TOOL message (linked via tool_call_id)
        5. On error: catch exception and append error message with same tool_call_id
        
        Tool results are added to messages list in original order (preserves causality).
        Each tool result message includes the tool_call_id to associate it with the AI's
        original tool call request (required for proper message history reconstruction).
        
        Args:
            ai_message: AI response containing tool_calls list
            messages: Conversation history (modified in place, appends tool results)
        
        **Precondition:**
        - ai_message.tool_calls must be non-empty (caller checks this)
        - tool_name_client_map must contain entries for all tool names in tool_calls
        
        **Error Handling:**
        - Catches all exceptions (network, parsing, validation)
        - Wraps error messages in Role.TOOL messages (same as success case)
        - Continues executing remaining tools even if one fails
        - Prints error details to stdout for debugging
        
        **Side Effects:**
        - Network I/O to MCP servers (via client.call_tool())
        - Appends messages to messages list (modifies caller's data)
        - Prints tool calls and errors to stdout
        """
        for tool_call in ai_message.tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])

            try:
                # Look up MCP client for this specific tool
                client = self.tool_name_client_map.get(tool_name)
                if not client:
                    raise Exception(f"Unable to call {tool_name}. MCP client not found.")

                # Execute tool via MCP client and get result
                tool_result = await client.call_tool(tool_name, tool_args)

                # Add successful tool result to message history
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=str(tool_result),
                        tool_call_id=tool_call["id"],  # Links result to original call
                    )
                )
            except Exception as e:
                # Capture error message and include in message history
                error_msg = f"Error: {e}"
                print(f"Error: {error_msg}")
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=error_msg,
                        tool_call_id=tool_call["id"],  # Links error to original call
                    )
                )
