from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
import os


from app.api.router import api_router
from app.api.v1.endpoints import oauth
from app.core.security import decode_access_token
from app.mcp.server.rag_server import mcp
from app.services.llm.client import LLMUnavailableError

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

# OAuth 2.1 discovery endpoints for MCP clients.
@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp:tools"],
    }

@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "resource": f"{base_url}/mcp/",
        "authorization_servers": [base_url],
        "scopes_supported": ["mcp:tools"],
    }

@app.get("/.well-known/mcp")
async def mcp_metadata(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "DocuBrain-RAG-MCP-Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "endpoint": f"{base_url}/mcp/",
        "authentication": {"type": "oauth2"}
    }

@app.get("/login")
async def login_redirect(request: Request):
    query_str = request.url.query
    target = "/api/v1/oauth/login_page"
    if query_str:
        target += f"?{query_str}"
    return RedirectResponse(url=target, status_code=302)


# Set the authenticated subject in request state after FastMCP validates a token.
class PureASGIAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

app.add_middleware(PureASGIAuthMiddleware)


# An LLM is required (no local fallback): surface quota/key/overload problems as a clear 503
@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# Mount aggregated API routes under /api
app.include_router(api_router, prefix="/api")
# OAuth clients, including Claude, expect the standard root endpoints. The API
# prefixed routes remain available for the application's own frontend.
app.include_router(oauth.router)

# Mount the standards-based Streamable HTTP transport at /mcp.
app.mount("/mcp", mcp_app)









