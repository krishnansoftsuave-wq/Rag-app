import os
import json
from typing import List, Dict, Any, Optional
import chromadb

import re
from app.core.config import CHROMADB_DIR, EMBEDDING_MODEL_NAME
from app.core.logger import get_logger

logger = get_logger("vector_store")


def get_default_collection_name() -> str:
    safe_suffix = re.sub(r'[^a-zA-Z0-9_\-]', '_', EMBEDDING_MODEL_NAME).strip('_')
    return f"rag_{safe_suffix}"[:63]


class VectorStoreService:
    def __init__(self, collection_name: Optional[str] = None):
        if not collection_name or collection_name == "rag_documents":
            collection_name = get_default_collection_name()

        logger.info(f"Initializing Persistent ChromaDB Client at {CHROMADB_DIR} (collection: {collection_name})")
        self.chroma_client = chromadb.PersistentClient(path=CHROMADB_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.documents_metadata_file = os.path.join(CHROMADB_DIR, f"{collection_name}_meta.json")
        self.documents_store: Dict[str, Dict[str, Any]] = self._load_doc_metadata()

    def _load_doc_metadata(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.documents_metadata_file):
            try:
                with open(self.documents_metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load document metadata: {e}")
        return {}

    def _save_doc_metadata(self):
        try:
            with open(self.documents_metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.documents_store, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save document metadata: {e}")

    def add_chunks(
        self,
        doc_id: str,
        filename: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        file_size: int,
        upload_time: str,
        chunking_strategy: str = "standard"
    ):
        if not chunks:
            return

        texts = [chunk["content"] for chunk in chunks]
        ids = [chunk["id"] for chunk in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": chunk["chunk_index"],
                "chunking_strategy": chunking_strategy
            }
            for chunk in chunks
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        self.documents_store[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "file_type": os.path.splitext(filename)[1],
            "upload_time": upload_time,
            "file_size": file_size,
            "total_chunks": len(chunks),
            "chunking_strategy": chunking_strategy
        }
        self._save_doc_metadata()

    def set_document_status(self, doc_id: str, status: str) -> bool:
        """Mark a document "current" or "archived" (docs for an old version; see retrieval/version_policy.py)."""
        if doc_id not in self.documents_store:
            return False
        self.documents_store[doc_id]["status"] = status
        self._save_doc_metadata()
        return True

    def archived_doc_ids(self) -> set:
        return {d for d, meta in self.documents_store.items() if meta.get("status") == "archived"}

    def get_all_documents(self) -> List[Dict[str, Any]]:
        docs = []
        for doc in self.documents_store.values():
            doc_copy = dict(doc)
            if "chunking_strategy" not in doc_copy:
                doc_copy["chunking_strategy"] = "standard"
            docs.append(doc_copy)
        return docs


    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self.documents_store:
            return False

        try:
            self.collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            logger.error(f"Error deleting chunks from ChromaDB: {e}")

        del self.documents_store[doc_id]
        self._save_doc_metadata()
        return True

    def query_vectors(
        self,
        query_embedding: List[float],
        fetch_k: int,
        doc_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        where_filter = None
        if doc_ids and len(doc_ids) > 0:
            if len(doc_ids) == 1:
                where_filter = {"doc_id": doc_ids[0]}
            else:
                where_filter = {"$or": [{"doc_id": did} for did in doc_ids]}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(fetch_k, self.collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        candidates = []
        if results and results.get("documents") and len(results["documents"]) > 0:
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            ids = results["ids"][0]

            for cid, doc_text, meta, dist in zip(ids, documents, metadatas, distances):
                similarity_score = max(0.0, min(1.0, 1.0 - (dist / 2.0 if dist > 1.0 else dist)))
                candidates.append({
                    "id": cid,
                    "content": doc_text,
                    "metadata": meta,
                    "raw_score": similarity_score
                })

        return candidates

    def get_all_chunks() -> Dict[str, Any]:
        return self.collection.get(include=["documents", "metadatas"])
