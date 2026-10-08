import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    print("=== Testing FastMCP SSE Tool Discovery ===")
    async with sse_client('http://localhost:8000/mcp/sse') as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            print(f"[SUCCESS] Discovered {len(tools_resp.tools)} Tools:")
            for t in tools_resp.tools:
                print(f"  - {t.name}: {t.description[:60]}")

if __name__ == "__main__":
    asyncio.run(main())
