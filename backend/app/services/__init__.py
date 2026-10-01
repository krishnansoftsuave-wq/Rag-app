from app.services.document_processor import (
    process_document,
    process_document_with_text,
    extract_text_from_file,
    chunk_text,
    chunk_text_with_spans,
)
from app.services.vector_store import VectorStoreService
from app.services.hybrid_retriever import HybridRetrieverService
from app.services.llm_service import LLMService
from app.services.late_chunker import LateChunkerService, late_chunker_service
from app.services.semantic_chunker import SemanticChunkerService, semantic_chunker_service
from app.services.agentic_chunker import AgenticChunkerService, agentic_chunker_service

# Global service singletons
vector_store_service = VectorStoreService()
hybrid_retriever_service = HybridRetrieverService(vector_store=vector_store_service)
llm_service = LLMService()

__all__ = [
    "process_document",
    "process_document_with_text",
    "extract_text_from_file",
    "chunk_text",
    "chunk_text_with_spans",
    "VectorStoreService",
    "HybridRetrieverService",
    "LLMService",
    "LateChunkerService",
    "SemanticChunkerService",
    "AgenticChunkerService",
    "vector_store_service",
    "hybrid_retriever_service",
    "llm_service",
    "late_chunker_service",
    "semantic_chunker_service",
    "agentic_chunker_service",
]


