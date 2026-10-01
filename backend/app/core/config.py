import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Storage paths
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
CHROMADB_DIR = os.getenv("CHROMADB_DIR", str(BASE_DIR / "data" / "chromadb"))

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMADB_DIR, exist_ok=True)

# RAG & Embedding Settings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jinaai/jina-embeddings-v2-base-en")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "4"))

# Late Chunking Settings
USE_LATE_CHUNKING = os.getenv("USE_LATE_CHUNKING", "true").lower() in ("true", "1", "yes")
LATE_CHUNKING_MAX_TOKENS = int(os.getenv("LATE_CHUNKING_MAX_TOKENS", "8192"))
LATE_CHUNKING_STRIDE = int(os.getenv("LATE_CHUNKING_STRIDE", "1024"))

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
