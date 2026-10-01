# Re-export core config for backward compatibility
from app.core.config import (
    BASE_DIR,
    UPLOAD_DIR,
    CHROMADB_DIR,
    EMBEDDING_MODEL_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    DEFAULT_TOP_K,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
)

__all__ = [
    "BASE_DIR",
    "UPLOAD_DIR",
    "CHROMADB_DIR",
    "EMBEDDING_MODEL_NAME",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "DEFAULT_TOP_K",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
]
