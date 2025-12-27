import asyncio
import json
import os

from agent.clients.custom_mcp_client import CustomMCPClient
from agent.clients.mcp_client import MCPClient
from agent.clients.dial_client import DialClient
from agent.models.message import Message, Role


async def main():
    # Create empty list where we save tools from MCP Servers
    tools = []
    tool_name_client_map = {}
    
    # Create UMS MCPClient, url is http://localhost:8006/mcp
    ums_client = await MCPClient.create("http://localhost:8006/mcp")
    ums_tools = await ums_client.get_tools()
    tools.extend(ums_tools)
    
    # Collect tools and dict [tool name, mcp client]
    for tool in ums_tools:
        tool_name_client_map[tool["function"]["name"]] = ums_client
    
    # Create DialClient
    api_key = os.getenv("DIAL_API_KEY", "")
    dial_client = DialClient(
        api_key=api_key,
        endpoint="https://ai-proxy.lab.epam.com",
        tools=tools,
        tool_name_client_map=tool_name_client_map
    )
    
    # Create messages array with System message
    messages = [
        Message(
            role=Role.SYSTEM,
            content="You are a helpful assistant that can search and manage users. Use the available tools to help the user."
        )
    ]
    
    # Simple console chat loop
    while True:
        user_input = input("\nYou: ").strip()
        if not user_input or user_input.lower() in ["exit", "quit"]:
            break
        
        messages.append(Message(role=Role.USER, content=user_input))
        
        response = await dial_client.get_completion(messages)
        messages.append(response)
        
        print(f"\nAssistant: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())


# Check if Arkadiy Dobkin present as a user, if not then search info about him in the web and add him