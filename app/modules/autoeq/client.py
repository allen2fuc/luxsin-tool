

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    from app.core.anthropic import anthropic_client
    from app.core.config import settings

    server_params = StdioServerParameters(
        command="autoeq-mcp",
        args=[],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 2. 拉取 MCP 工具列表，转成 Anthropic 格式
            mcp_tools = await session.list_tools()

            anthropic_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema,
                }
                for t in mcp_tools.tools
            ]

            # 3. 调用 Claude，把工具列表传进去
            messages = [{"role": "user", "content": "HD650 的 PEQ"}]
            
            while True:
                resp = await anthropic_client.messages.create(
                    model=settings.AI_MODEL,
                    max_tokens=4096,
                    tools=anthropic_tools,
                    messages=messages,
                )

                print("resp", resp)
                
                if resp.stop_reason != "tool_use":
                    break
                
                # 4. 执行 tool_use 块，调用 MCP server
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        result = await session.call_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [
                                {"type": "text", "text": c.text}
                                for c in result.content
                            ],
                        })
                
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
