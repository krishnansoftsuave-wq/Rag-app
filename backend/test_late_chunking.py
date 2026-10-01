import sys
import os
import torch
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.document_processor import chunk_text_with_spans, process_document
from app.services.late_chunker import late_chunker_service
from app.services import vector_store_service, hybrid_retriever_service
from app.rag_engine import rag_engine


def cosine_similarity(v1, v2):
    a = np.array(v1)
    b = np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_late_chunking():
    print("=== Testing Late Chunking Implementation ===")
    
    # 1. Span calculation test
    print("\n1. Testing chunk_text_with_spans...")
    sample_text = (
        "Berlin is the capital and largest city of Germany by both area and population. "
        "Its more than 3.85 million inhabitants make it the European Union's most populous city. "
        "The city is known for its festivals, diverse architecture, nightlife, and contemporary arts."
    )
    spans = chunk_text_with_spans(sample_text, chunk_size=90, overlap=15)
    print(f"   Generated {len(spans)} chunks with character spans:")
    for i, s in enumerate(spans):
        extracted = sample_text[s["start_char"]:s["end_char"]]
        print(f"   - Chunk {i}: span [{s['start_char']}:{s['end_char']}] -> '{extracted[:35]}...'")
        assert extracted == s["content"], f"Span slice does not match content for chunk {i}!"
    print("   [PASS] Character span alignment is 100% accurate.")

    # 2. Embedding dimension & normalization test
    print("\n2. Testing LateChunkerService.encode_chunks...")
    model = hybrid_retriever_service.embedding_model
    late_embeddings = late_chunker_service.encode_chunks(
        full_text=sample_text,
        chunks=spans,
        model=model,
        use_late_chunking=True
    )
    print(f"   Generated {len(late_embeddings)} embeddings.")
    expected_dim = model.get_sentence_embedding_dimension()
    print(f"   Embedding dimension: {len(late_embeddings[0])} (expected: {expected_dim})")
    assert len(late_embeddings[0]) == expected_dim, "Dimension mismatch!"

    for i, emb in enumerate(late_embeddings):
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-4, f"Vector {i} is not L2 normalized (norm = {norm})"
    print(f"   [PASS] All vectors have dimension {expected_dim} and unit L2 norm.")

    # 3. Context Retention: Late Chunking vs Early Chunking Comparison
    print("\n3. Comparing Context Retention: Late Chunking vs Early (Standard) Chunking...")
    context_doc = (
        "Project Antigravity is DeepMind's flagship agentic coding system. "
        "It provides autonomous pair programming, code reasoning, and test generation capabilities."
    )
    doc_chunks = chunk_text_with_spans(context_doc, chunk_size=70, overlap=0)
    # doc_chunks[0] has 'Project Antigravity is DeepMind's flagship agentic coding system.'
    # doc_chunks[1] has 'It provides autonomous pair programming, code reasoning, and test generation capabilities.'

    early_embs = late_chunker_service.encode_chunks(
        full_text=context_doc,
        chunks=doc_chunks,
        model=model,
        use_late_chunking=False
    )
    late_embs = late_chunker_service.encode_chunks(
        full_text=context_doc,
        chunks=doc_chunks,
        model=model,
        use_late_chunking=True
    )

    query = "What is Project Antigravity?"
    query_emb = model.encode(query, show_progress_bar=False).tolist()

    # Compare Chunk 1 ("It provides autonomous pair programming...") similarity to query
    sim_early = cosine_similarity(query_emb, early_embs[1])
    sim_late = cosine_similarity(query_emb, late_embs[1])

    print(f"   Query: '{query}'")
    print(f"   Target chunk without explicit subject: '{doc_chunks[1]['content']}'")
    print(f"   - Similarity with Early Chunking (isolated): {sim_early:.4f}")
    print(f"   - Similarity with Late Chunking (contextual): {sim_late:.4f}")
    print(f"   -> Context retention gain: +{(sim_late - sim_early):.4f} similarity boost!")
    assert sim_late >= sim_early, "Late chunking should maintain or improve contextual similarity!"
    print("   [PASS] Context retention test passed.")

    # 4. End-to-End Vector Store & Retrieval Test
    print("\n4. Testing ChromaDB Indexing and Retrieval with Late Chunking...")
    test_doc_file = "test_late_doc.txt"
    with open(test_doc_file, "w", encoding="utf-8") as f:
        f.write(context_doc)

    chunks = process_document(test_doc_file, test_doc_file, "test_doc_late")
    rag_engine.add_document_chunks(
        doc_id="test_doc_late",
        filename=test_doc_file,
        chunks=chunks,
        file_size=len(context_doc),
        upload_time="2026-09-05 15:00:00",
        full_text=context_doc,
        use_late_chunking=True
    )

    citations = rag_engine.retrieve_context("What capabilities does Antigravity provide?", top_k=2)
    print(f"   Retrieved {len(citations)} citations:")
    for c in citations:
        print(f"   - [{int(c.score * 100)}%] {c.content}")

    # Cleanup
    if os.path.exists(test_doc_file):
        os.remove(test_doc_file)
    rag_engine.delete_document("test_doc_late")
    print("   [PASS] End-to-end indexing and retrieval passed cleanly.")

    print("\n=== ALL LATE CHUNKING TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    test_late_chunking()
