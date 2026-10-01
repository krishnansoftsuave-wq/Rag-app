# DocuBrain RAG Tools Documentation

This document describes the 3 single-responsibility tools created for the Adaptive RAG Agent in DocuBrain (Week 7 Module 4).

---

## Tool 1: `search_document`

### Purpose
Retrieves relevant document chunks matching an initial search query using **Hybrid Search** (SentenceTransformers dense vector embeddings + Rank-BM25 sparse keyword retrieval) combined with **Reciprocal Rank Fusion (RRF)**.

> **Single Responsibility**: Evidence retrieval only. Does NOT generate answers or evaluate evidence sufficiency.

### Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `document_id` | `Optional[str]` | No | `None` | Filter retrieval to a specific uploaded document ID. |
| `query` | `str` | Yes | - | Initial search query string. |
| `top_k` | `int` | No | `4` | Number of top RRF chunks to retrieve. |

### Example Input
```python
search_document(
    document_id="0878b231",
    query="What core technologies power DocuBrain's vector search?",
    top_k=4
)
```

### Example Output
```json
{
  "results": [
    {
      "chunk_index": 0,
      "filename": "RAG_Test_Knowledge_Base.pdf",
      "doc_id": "0878b231",
      "score": 1.0,
      "snippet": "DocuBrain uses ChromaDB with SentenceTransformers (all-MiniLM-L6-v2) for high performance vector indexing...",
      "full_content": "DocuBrain uses ChromaDB with SentenceTransformers (all-MiniLM-L6-v2) for high performance vector indexing..."
    }
  ],
  "result_count": 1,
  "top_score": 1.0,
  "query": "What core technologies power DocuBrain's vector search?"
}
```

---

## Tool 2: `refine_document_search`

### Purpose
Performs targeted follow-up evidence retrieval using a refined search formulation when prior evidence validation identifies specific missing information gaps.

> **Single Responsibility**: Targeted follow-up retrieval based on an identified information gap.

### Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `document_id` | `Optional[str]` | No | `None` | Filter retrieval to a specific uploaded document ID. |
| `query` | `str` | Yes | - | Targeted refined query string addressing missing evidence. |
| `top_k` | `int` | No | `4` | Number of top RRF chunks to retrieve. |

### Example Input
```python
refine_document_search(
    document_id="0878b231",
    query="DocuBrain vector search fallback mode behavior when offline",
    top_k=4
)
```

### Example Output
```json
{
  "results": [
    {
      "chunk_index": 2,
      "filename": "RAG_Test_Knowledge_Base.pdf",
      "doc_id": "0878b231",
      "score": 0.92,
      "snippet": "When no external API key is provided, DocuBrain uses a Smart Local RAG Synthesis fallback engine...",
      "full_content": "When no external API key is provided, DocuBrain uses a Smart Local RAG Synthesis fallback engine..."
    }
  ],
  "result_count": 1,
  "top_score": 0.92,
  "query": "DocuBrain vector search fallback mode behavior when offline",
  "refined_query": "DocuBrain vector search fallback mode behavior when offline"
}
```

---

## Tool 3: `validate_evidence`

### Purpose
Evaluates whether accumulated document context contains sufficient factual information to directly and completely answer the user's question.

> **Single Responsibility**: Evidence sufficiency assessment and missing information gap identification. Does NOT retrieve documents or generate final answers.

### Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `question` | `str` | Yes | - | The user's question. |
| `retrieved_context` | `str` | Yes | - | Combined text of all retrieved document chunks. |
| `api_key` | `Optional[str]` | No | `None` | Optional Gemini API key for evaluation. |

### Example Input
```python
validate_evidence(
    question="What happens if authentication fails during deployment?",
    retrieved_context="DocuBrain logs system metrics to logs/backend.log..."
)
```

### Example Output
```json
{
  "sufficient": false,
  "reason": "Retrieved context discusses logging but lacks specific error handling rules for deployment authentication failure.",
  "missing_information": [
    "deployment behavior after authentication failure"
  ],
  "input_tokens": 142,
  "output_tokens": 38
}
```
