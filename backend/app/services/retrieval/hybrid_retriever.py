import re
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from app.core.config import EMBEDDING_MODEL_NAME, DEFAULT_TOP_K
from app.core.logger import get_logger
from app.schemas.chat import SourceCitation
from app.services.retrieval.vector_store import VectorStoreService
from app.services.llm.client import complete
from app.core.tracing import record_contexts, span
from app.services.retrieval import version_policy

logger = get_logger("hybrid_retriever")


def tokenize(text: str) -> List[str]:
    """Extract lowercase words/tokens for BM25 keyword matching."""
    return re.findall(r'\w+', text.lower())


def expand_query(query: str) -> str:
    """Enriches queries dynamically using the LLM by generating domain-specific synonyms and concepts."""
    prompt = f"""You are an expert search query expander for domain-agnostic document retrieval.
Given the user query, generate 3 to 5 domain-specific search synonyms, related technical concepts, or keyword expansions that might appear in relevant target documents.
Output ONLY the expanded search keywords separated by spaces. Do not include markdown formatting, numbers, quotes, or conversational prefix.

User Query: {query}
Expanded Terms:"""
    # An LLM is required: raises LLMUnavailableError when no model can answer
    text, model_name = complete(prompt)
    expanded_terms = re.sub(r'[\*\`\#\"]', '', text.strip().replace("\n", " ")).strip()
    if not expanded_terms:
        return query
    logger.info(f"Dynamic query expansion via LLM ({model_name}): '{query}' -> '{query} {expanded_terms}'")
    return f"{query} {expanded_terms}"


class HybridRetrieverService:
    def __init__(self, vector_store: VectorStoreService):
        self.vector_store = vector_store
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)

        self.bm25: Optional[BM25Okapi] = None
        self.bm25_chunks: List[Dict[str, Any]] = []
        self.build_bm25_index()

    def build_bm25_index(self):
        """Rebuilds the BM25 lexical index over all document chunks in vector store."""
        try:
            if self.vector_store.collection.count() == 0:
                self.bm25 = None
                self.bm25_chunks = []
                return

            all_records = self.vector_store.collection.get(include=["documents", "metadatas"])
            if not all_records or not all_records.get("documents"):
                self.bm25 = None
                self.bm25_chunks = []
                return

            documents = all_records["documents"]
            metadatas = all_records["metadatas"]
            ids = all_records["ids"]

            tokenized_corpus = []
            chunks_info = []

            for cid, doc_text, meta in zip(ids, documents, metadatas):
                tokens = tokenize(doc_text)
                tokenized_corpus.append(tokens)
                chunks_info.append({
                    "id": cid,
                    "content": doc_text,
                    "metadata": meta
                })

            if tokenized_corpus:
                self.bm25 = BM25Okapi(tokenized_corpus)
                self.bm25_chunks = chunks_info
                logger.info(f"Successfully built BM25 index with {len(chunks_info)} chunks.")
            else:
                self.bm25 = None
                self.bm25_chunks = []
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            self.bm25 = None
            self.bm25_chunks = []

    def _bm25_search(self, query: str, doc_ids: Optional[List[str]], fetch_k: int) -> List[Dict[str, Any]]:
        """Sparse lexical keyword retrieval via BM25."""
        if not self.bm25 or not self.bm25_chunks:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        target_doc_ids = set(doc_ids) if doc_ids else None
        candidates = []

        for idx, score in indexed_scores:
            if score <= 0:
                continue
            chunk = self.bm25_chunks[idx]
            chunk_doc_id = chunk["metadata"].get("doc_id", "")
            if target_doc_ids and chunk_doc_id not in target_doc_ids:
                continue

            candidates.append({
                "id": chunk["id"],
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "raw_score": float(score)
            })
            if len(candidates) >= fetch_k:
                break

        return candidates

    def _rrf_rerank(
        self,
        vector_candidates: List[Dict[str, Any]],
        bm25_candidates: List[Dict[str, Any]],
        top_k: int,
        k_constant: int = 60
    ) -> List[SourceCitation]:
        """Reciprocal Rank Fusion (RRF) algorithm to fuse vector & BM25 rankings."""
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        # Accumulate RRF score for Vector Search results
        for rank, item in enumerate(vector_candidates, start=1):
            cid = item["id"]
            doc_map[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (0.5 / (k_constant + rank))

        # Accumulate RRF score for BM25 Search results
        for rank, item in enumerate(bm25_candidates, start=1):
            cid = item["id"]
            doc_map[cid] = item
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (0.5 / (k_constant + rank))

        if not rrf_scores:
            return []

        sorted_cids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
        max_score = max(rrf_scores.values()) if rrf_scores else 1.0

        citations = []
        for cid in sorted_cids:
            item = doc_map[cid]
            meta = item["metadata"]
            norm_score = round(rrf_scores[cid] / max_score, 4) if max_score > 0 else 0.0
            citations.append(
                SourceCitation(
                    content=item["content"],
                    doc_id=meta.get("doc_id", ""),
                    filename=meta.get("filename", "Unknown"),
                    chunk_index=meta.get("chunk_index", 0),
                    score=norm_score
                )
            )

        return citations

    def retrieve_context(
        self,
        query: str,
        doc_ids: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        search_mode: str = "hybrid"
    ) -> List[SourceCitation]:
        # One span per retrieval (its query expansion LLM call included); the chunks it returns are logged by id
        with span("retrieval", stage="retrieval", search_mode=search_mode, top_k=top_k, query=query, doc_ids=doc_ids,
                  version_policy=version_policy.POLICY) as s:
            # Archived docs (old versions) are searched only when the user asks about an older version
            excluded = set() if version_policy.wants_archived(query) else self.vector_store.archived_doc_ids()
            citations = self._retrieve(query, doc_ids, top_k, search_mode, excluded)
            if s is not None:
                s.attrs["archived_excluded"] = sorted(excluded)
            record_contexts(citations)
        return citations

    def _retrieve(
        self,
        query: str,
        doc_ids: Optional[List[str]],
        top_k: int,
        search_mode: str,
        excluded_doc_ids: Optional[set] = None
    ) -> List[SourceCitation]:
        if self.vector_store.collection.count() == 0:
            return []

        expanded_q = expand_query(query)
        fetch_k = max(top_k * 3, 10)

        # 1. Vector Search
        vector_candidates = []
        if search_mode in ["hybrid", "vector"]:
            query_embedding = self.embedding_model.encode([expanded_q]).tolist()[0]
            vector_candidates = self.vector_store.query_vectors(
                query_embedding=query_embedding,
                fetch_k=fetch_k,
                doc_ids=doc_ids
            )

        # 2. BM25 Search
        bm25_candidates = []
        if search_mode in ["hybrid", "bm25"]:
            bm25_candidates = self._bm25_search(query=expanded_q, doc_ids=doc_ids, fetch_k=fetch_k)

        if excluded_doc_ids:
            vector_candidates = [c for c in vector_candidates if c["metadata"].get("doc_id") not in excluded_doc_ids]
            bm25_candidates = [c for c in bm25_candidates if c["metadata"].get("doc_id") not in excluded_doc_ids]

        # 3. Output mode formatting
        if search_mode == "vector":
            citations = []
            for item in vector_candidates[:top_k]:
                meta = item["metadata"]
                citations.append(
                    SourceCitation(
                        content=item["content"],
                        doc_id=meta.get("doc_id", ""),
                        filename=meta.get("filename", "Unknown"),
                        chunk_index=meta.get("chunk_index", 0),
                        score=round(float(item["raw_score"]), 4)
                    )
                )
            return citations
        elif search_mode == "bm25":
            citations = []
            max_s = max([c["raw_score"] for c in bm25_candidates]) if bm25_candidates else 1.0
            for item in bm25_candidates[:top_k]:
                meta = item["metadata"]
                norm_score = round(item["raw_score"] / max_s, 4) if max_s > 0 else 0.0
                citations.append(
                    SourceCitation(
                        content=item["content"],
                        doc_id=meta.get("doc_id", ""),
                        filename=meta.get("filename", "Unknown"),
                        chunk_index=meta.get("chunk_index", 0),
                        score=norm_score
                    )
                )
            return citations
        else:
            # Hybrid Search with RRF Reranking
            return self._rrf_rerank(vector_candidates=vector_candidates, bm25_candidates=bm25_candidates, top_k=top_k)
