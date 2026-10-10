"""
Index the Week 10 race corpus: the NovaCloud developer documentation (benchmarks/novacloud_docs.txt) under the
fixed doc id `w10_novacloud`.

novacloud_docs.txt is the documentation part of novacloud_rag_test_document.pdf. The PDF's last pages list the
evaluation questions with their expected answers; they are left out so retrieval cannot return the answer key.
Re-running replaces the previous copy.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import hybrid_retriever_service, vector_store_service
from app.services.ingestion.document_processor import process_document_with_text

DOC_ID = "w10_novacloud"
FILENAME = "novacloud_platform_docs.txt"
SOURCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novacloud_docs.txt")


def seed_docs() -> None:
    if vector_store_service.delete_document(DOC_ID):
        print(f"Removed the previous '{DOC_ID}' copy.")
    full_text, chunks = process_document_with_text(SOURCE_PATH, FILENAME, DOC_ID)
    embeddings = hybrid_retriever_service.embedding_model.encode(
        [c["content"] for c in chunks], show_progress_bar=False
    ).tolist()
    vector_store_service.add_chunks(
        doc_id=DOC_ID,
        filename=FILENAME,
        chunks=chunks,
        embeddings=embeddings,
        file_size=len(full_text),
        upload_time="2026-10-09 00:00:00",
        chunking_strategy="standard",
    )
    hybrid_retriever_service.build_bm25_index()
    print(f"Indexed '{DOC_ID}' ({FILENAME}): {len(chunks)} chunks.")


if __name__ == "__main__":
    seed_docs()
