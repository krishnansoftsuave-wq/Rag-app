from fastapi import APIRouter
from app.api.v1.endpoints import health, documents, chat, evaluation

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health Check"])
api_router.include_router(documents.router, tags=["Document Operations"])
api_router.include_router(chat.router, tags=["RAG Chat"])
api_router.include_router(evaluation.router, tags=["Agent Evaluation"])

