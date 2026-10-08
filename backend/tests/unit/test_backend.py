import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # backend/

from app.services.ingestion.document_processor import process_document
from app.services import vector_store_service, hybrid_retriever_service, llm_service, late_chunker_service

def run_test():
    print("1. Testing document chunker & text processor...")
    sample_text = """
    Antigravity AI Overview.
    Antigravity AI is an advanced agentic coding framework built by Google DeepMind.
    It empowers developers to build complex fullstack applications, debug codebases,
    and automate engineering workflows seamlessly.
    
    Key Features of RAG Applications:
    RAG stands for Retrieval-Augmented Generation.
    It combines vector similarity search with generative language models.
    ChromaDB stores high dimensional vector embeddings for fast text lookup.
    """
    
    test_file = "test_doc.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(sample_text)

    chunks = process_document(test_file, "test_doc.txt", "doc123")
    print(f"   Created {len(chunks)} chunks.")
    
    print("2. Indexing chunks into ChromaDB...")
    embeddings = late_chunker_service.encode_chunks(
        full_text=chunks[0].get("full_text", sample_text),
        chunks=chunks,
        model=hybrid_retriever_service.embedding_model,
    )
    vector_store_service.add_chunks("doc123", "test_doc.txt", chunks, embeddings, len(sample_text), "2026-08-22 18:45:00")
    hybrid_retriever_service.build_bm25_index()
    print(f"   Collection count: {vector_store_service.collection.count()}")

    print("3. Querying RAG Engine...")
    sources = hybrid_retriever_service.retrieve_context(query="What is Antigravity AI?")
    print(f"   Retrieved {len(sources)} source citations.")
    for s in sources:
        clean_c = s.content[:80].encode('ascii', errors='ignore').decode('ascii')
        print(f"   - Match [{int(s.score*100)}%]: {clean_c}...")

    answer_res = llm_service.generate_answer(question="What is Antigravity AI?", sources=sources)
    print("\n4. Generated RAG Response:")
    print("----------------------------------------")
    clean_ans = answer_res.answer.encode('ascii', errors='ignore').decode('ascii')
    print(clean_ans)
    print("----------------------------------------")
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)
    vector_store_service.delete_document("doc123")
    hybrid_retriever_service.build_bm25_index()
    print("Backend test passed successfully!")

if __name__ == "__main__":
    run_test()
