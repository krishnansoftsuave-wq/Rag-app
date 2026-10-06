from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
import os


from app.api.router import api_router
from app.core.security import decode_access_token
from app.mcp.server import mcp

# FastMCP owns background task groups for Streamable HTTP. Its lifespan must be
# passed to FastAPI, otherwise MCP requests fail after the app has started.
mcp_app = mcp.http_app(path="/", transport="streamable-http")

app = FastAPI(
    title="Enterprise RAG Application API",
    description="Enterprise Fullstack RAG Backend powering document upload, text indexing, hybrid vector/BM25 retrieval & question answering",
    version="2.0.0",
    lifespan=mcp_app.lifespan,
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth 2.0 & MCP Discovery Metadata Endpoints
@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    return JSONResponse(status_code=404, content={"detail": "OAuth authentication disabled"})

@app.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request):
    return JSONResponse(status_code=404, content={"detail": "OAuth authentication disabled"})

@app.get("/.well-known/mcp")
async def mcp_metadata(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "DocuBrain-RAG-MCP-Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "endpoint": f"{base_url}/mcp/",
        "authentication": {"type": "none"}
    }

@app.get("/login")
async def login_redirect(request: Request):
    query_str = request.url.query
    target = "/api/v1/oauth/login_page"
    if query_str:
        target += f"?{query_str}"
    return RedirectResponse(url=target, status_code=302)


# Pure ASGI Middleware setting default guest user context for open MCP access
class PureASGIAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            scope.setdefault("state", {})
            scope["state"]["user_id"] = "default_user"
            scope["state"]["username"] = "guest"
        await self.app(scope, receive, send)

app.add_middleware(PureASGIAuthMiddleware)

# Mount aggregated API routes under /api
app.include_router(api_router, prefix="/api")

# Mount the standards-based Streamable HTTP transport at /mcp.
app.mount("/mcp", mcp_app)









