import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ingestion.document_processor import process_document_with_text
from app.services import vector_store_service, hybrid_retriever_service

SAMPLE_KB_TEXT = """
DocuBrain Knowledge Base & System Specification

1. Core Architecture & Technologies:
DocuBrain is an enterprise Retrieval-Augmented Generation (RAG) platform.
It uses ChromaDB with SentenceTransformers (jinaai/jina-embeddings-v2-base-en or all-MiniLM-L6-v2) for high-performance dense vector search.
For sparse lexical retrieval, DocuBrain uses Rank-BM25 (BM25Okapi).
LLM question answering is powered by Google Gemini API (gemini-2.5-flash) with inline citations.

2. Document Upload & Chunking Configurations:
DocuBrain supports 4 document chunking strategies: Standard, Semantic, Agentic, and Late Chunking.
The default chunk size is 600 characters with an overlap of 80 characters.
When uploading via /api/upload, text is extracted from PDF, DOCX, TXT, or MD files, chunked, embedded, and indexed into ChromaDB while rebuilding the BM25 index.

3. Chunking Strategy Comparison:
Standard Chunking uses recursive character splitting which can fragment context at chunk boundaries.
Late Chunking passes the full text through transformer embedding layers first before pool-averaging chunk spans, preserving global document context across chunk boundaries.

4. Hybrid Search & Reciprocal Rank Fusion (RRF):
DocuBrain combines dense vector search and BM25 sparse keyword retrieval using Reciprocal Rank Fusion (RRF).
RRF calculates a fused rank score for each chunk by summing inverse rank positions: score = 0.5 / (60 + rank).
The top fused results are passed as context to the LLM.

5. Gemini LLM & Local Fallback Mode:
When no Gemini API key is provided or network is offline, DocuBrain operates in Smart Local Fallback Mode.
Local Fallback Mode extracts structured text snippets and relevance scores directly from top chunks into a summary without calling external LLM APIs.

6. Deployment & System Credentials Failure Handling:
If system credentials or authentication fail during deployment, DocuBrain logs warning events to logs/backend.log, falls back to local context synthesis mode without crashing, and reports health status on /api/health.

7. Evidence Validation & Query Refinement Workflow:
In the adaptive RAG agent loop, validate_evidence evaluates context sufficiency.
If evidence is insufficient, it identifies missing information topics, triggers refine_document_search with a targeted refined query, accumulates new evidence, and re-validates context before generating the final answer.

8. End-to-End Multi-Hop Retrieval:
For multi-hop queries, initial search retrieves primary context, evidence validation identifies gaps, refined search fetches secondary details across sections, and the unified context is passed to the LLM for citation-backed synthesis.
"""


def seed_docs():
    print("Seeding DocuBrain benchmark document into ChromaDB & BM25...")
    file_path = os.path.join(os.path.dirname(__file__), "docubrain_kb.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_KB_TEXT)

    doc_id = "test_kb"
    full_text, chunks = process_document_with_text(file_path, "docubrain_kb.txt", doc_id)

    embeddings = hybrid_retriever_service.embedding_model.encode(
        [c["content"] for c in chunks],
        show_progress_bar=False
    ).tolist()

    vector_store_service.add_chunks(
        doc_id=doc_id,
        filename="docubrain_kb.txt",
        chunks=chunks,
        embeddings=embeddings,
        file_size=len(SAMPLE_KB_TEXT),
        upload_time="2026-09-15 01:00:00",
        chunking_strategy="standard"
    )

    hybrid_retriever_service.build_bm25_index()
    print(f"Successfully seeded 'test_kb' with {len(chunks)} chunks into ChromaDB & BM25 index!")


if __name__ == "__main__":
    seed_docs()
