import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.document_processor import process_document
from app.rag_engine import rag_engine
from app.models import ChatRequest

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
    rag_engine.add_document_chunks("doc123", "test_doc.txt", chunks, len(sample_text), "2026-08-22 18:45:00")
    print(f"   Collection count: {rag_engine.collection.count()}")

    print("3. Querying RAG Engine...")
    sources = rag_engine.retrieve_context("What is Antigravity AI?")
    print(f"   Retrieved {len(sources)} source citations.")
    for s in sources:
        clean_c = s.content[:80].encode('ascii', errors='ignore').decode('ascii')
        print(f"   - Match [{int(s.score*100)}%]: {clean_c}...")

    answer_res = rag_engine.generate_answer("What is Antigravity AI?", sources)
    print("\n4. Generated RAG Response:")
    print("----------------------------------------")
    clean_ans = answer_res.answer.encode('ascii', errors='ignore').decode('ascii')
    print(clean_ans)
    print("----------------------------------------")
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)
    rag_engine.delete_document("doc123")
    print("Backend test passed successfully!")

if __name__ == "__main__":
    run_test()
