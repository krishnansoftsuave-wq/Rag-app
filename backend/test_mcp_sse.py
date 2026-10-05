import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_sse_test():
    url = "http://localhost:8000/mcp/sse"
    print(f"=== 1. Connecting to FastMCP Server via SSE transport at {url} ===")
    
    try:
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("[OK] Client Session initialized over SSE successfully!")

                print("\n=== 2. Listing Available FastMCP Tools over SSE ===")
                tools_response = await session.list_tools()
                print(f"[TOOLS] Discovered {len(tools_response.tools)} FastMCP Tools:")
                for tool in tools_response.tools:
                    print(f"  - {tool.name}: {tool.description[:70]}...")

                print("\n=== 3. Invoking 'list_documents' Tool over SSE ===")
                result = await session.call_tool("list_documents", {"user_id": "test_sse_user"})
                print(f"[RESULT] Tool output:\n{result.content[0].text}")

                print("\n=== 4. Invoking 'upload_document' Tool over SSE ===")
                upload_res = await session.call_tool(
                    "upload_document",
                    {
                        "filename": "SSE_Protocol_Spec.txt",
                        "content_text": "Server-Sent Events (SSE) allows streaming JSON-RPC messages from FastMCP backend to Claude Desktop.",
                        "user_id": "test_sse_user",
                        "chunking_strategy": "agentic"
                    }
                )
                print(f"[RESULT] Upload output:\n{upload_res.content[0].text}")

    except Exception as err:
        print(f"[NOTE] Server test requires backend server running on http://localhost:8000/mcp/sse: {err}")

if __name__ == "__main__":
    asyncio.run(run_sse_test())
