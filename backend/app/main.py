from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router

app = FastAPI(
    title="Enterprise RAG Application API",
    description="Enterprise Fullstack RAG Backend powering document upload, text indexing, hybrid vector/BM25 retrieval & question answering",
    version="2.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount aggregated API routes under /api
app.include_router(api_router, prefix="/api")
