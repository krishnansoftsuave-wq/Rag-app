from fastapi import APIRouter
from app.api.v1.endpoints import health, documents, chat, evaluation, auth, mcp, oauth

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(auth.router, prefix="/v1/auth", tags=["User Authentication"])
api_router.include_router(oauth.router, prefix="/v1/oauth", tags=["OAuth 2.0 Auth Server"])
api_router.include_router(mcp.router, prefix="/v1/mcp", tags=["Model Context Protocol (MCP)"])
api_router.include_router(documents.router, tags=["Document Operations"])
api_router.include_router(chat.router, tags=["RAG Chat"])
api_router.include_router(evaluation.router, tags=["Agent Evaluation"])



