# Re-export engine services for backward compatibility
from typing import List, Dict, Any, Optional
from app.schemas.chat import SourceCitation, ChatResponse
from app.services import (
    vector_store_service,
    hybrid_retriever_service,
    llm_service,
    late_chunker_service,
)


class LegacyRAGEngineBridge:
    """Backward compatibility bridge mapping legacy RAGEngine calls to decoupled services."""
    @property
    def collection(self):
        return vector_store_service.collection

    @property
    def embedding_model(self):
        return hybrid_retriever_service.embedding_model

    def add_document_chunks(
        self,
        doc_id: str,
        filename: str,
        chunks: List[Dict[str, Any]],
        file_size: int,
        upload_time: str,
        full_text: Optional[str] = None,
        use_late_chunking: Optional[bool] = None,
    ):
        doc_text = full_text or (chunks[0].get("full_text") if chunks else "")
        embeddings = late_chunker_service.encode_chunks(
            full_text=doc_text,
            chunks=chunks,
            model=self.embedding_model,
            use_late_chunking=use_late_chunking,
        )
        vector_store_service.add_chunks(doc_id, filename, chunks, embeddings, file_size, upload_time)
        hybrid_retriever_service.build_bm25_index()

    def get_all_documents(self) -> List[Dict[str, Any]]:
        return vector_store_service.get_all_documents()

    def delete_document(self, doc_id: str) -> bool:
        res = vector_store_service.delete_document(doc_id)
        hybrid_retriever_service.build_bm25_index()
        return res

    def retrieve_context(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        top_k: int = 4,
        search_mode: str = "hybrid",
        api_key: Optional[str] = None
    ) -> List[SourceCitation]:
        return hybrid_retriever_service.retrieve_context(
            query=query,
            doc_ids=doc_ids,
            top_k=top_k,
            search_mode=search_mode,
            api_key=api_key
        )

    def generate_answer(
        self,
        question: str,
        sources: List[SourceCitation],
        api_key: Optional[str] = None,
        provider: str = "gemini"
    ) -> ChatResponse:
        return llm_service.generate_answer(
            question=question,
            sources=sources,
            api_key=api_key,
            provider=provider
        )


rag_engine = LegacyRAGEngineBridge()
