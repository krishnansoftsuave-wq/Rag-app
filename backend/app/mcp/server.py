import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP

from app.services import (
    hybrid_retriever_service,
    vector_store_service,
    agentic_chunker_service,
    extract_text_from_file,
    llm_service
)
from app.services.user_service import UserService
from app.core.config import UPLOAD_DIR

# Initialize FastMCP Server for DocuBrain RAG & MCP Tools
mcp = FastMCP("DocuBrain-RAG-MCP-Server")


@mcp.tool()
def upload_document(
    filename: str,
    content_text: str,
    user_id: str = "default_user",
    chunking_strategy: str = "agentic"
) -> Dict[str, Any]:
    """
    MCP TOOL: upload_document
    Description: Upload and index a new text document into the RAG vector store for a user.
    Args:
        filename: Name of the document (e.g. 'report.txt' or 'manual.pdf')
        content_text: The full text content of the document
        user_id: ID of the owning user (defaults to 'default_user')
        chunking_strategy: Strategy to use ('agentic', 'semantic', 'standard')
    """
    if not content_text or not content_text.strip():
        return {"success": False, "error": "Document content text cannot be empty."}

    doc_id = str(uuid.uuid4())[:8]
    sanitized_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{sanitized_filename}")

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_text)

        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if chunking_strategy == "agentic":
            spans_data = agentic_chunker_service.chunk_text_agentically(
                full_text=content_text,
                embedding_model=hybrid_retriever_service.embedding_model
            )
            chunks = []
            for idx, item in enumerate(spans_data):
                chunks.append({
                    "id": f"{doc_id}_chunk_{idx}",
                    "doc_id": doc_id,
                    "filename": sanitized_filename,
                    "chunk_index": idx,
                    "content": item["content"],
                    "start_char": item["start_char"],
                    "end_char": item["end_char"],
                    "full_text": content_text
                })
        else:
            # Standard chunking fallback
            raw_lines = [l.strip() for l in content_text.split("\n") if l.strip()]
            chunks = []
            chunk_size = 500
            step = 400
            for idx in range(0, len(content_text), step):
                sub = content_text[idx:idx + chunk_size]
                if sub.strip():
                    chunks.append({
                        "id": f"{doc_id}_chunk_{len(chunks)}",
                        "doc_id": doc_id,
                        "filename": sanitized_filename,
                        "chunk_index": len(chunks),
                        "content": sub,
                        "start_char": idx,
                        "end_char": idx + len(sub),
                        "full_text": content_text
                    })

        embeddings = hybrid_retriever_service.embedding_model.encode(
            [c["content"] for c in chunks],
            show_progress_bar=False
        ).tolist()

        vector_store_service.add_chunks(
            doc_id=doc_id,
            filename=sanitized_filename,
            chunks=chunks,
            embeddings=embeddings,
            file_size=len(content_text.encode('utf-8')),
            upload_time=upload_time,
            chunking_strategy=chunking_strategy
        )

        # Associate document with user
        UserService.associate_document(doc_id=doc_id, user_id=user_id, filename=sanitized_filename)

        # Rebuild lexical BM25 index
        hybrid_retriever_service.build_bm25_index()

        return {
            "success": True,
            "doc_id": doc_id,
            "filename": sanitized_filename,
            "total_chunks": len(chunks),
            "upload_time": upload_time,
            "user_id": user_id,
            "message": f"Successfully uploaded and indexed '{sanitized_filename}' ({len(chunks)} chunks)."
        }
    except Exception as err:
        return {"success": False, "error": f"Failed to upload document: {str(err)}"}


@mcp.tool()
def query_document_and_reply(
    question: str,
    doc_id: Optional[str] = None,
    user_id: str = "default_user",
    top_k: int = 5
) -> Dict[str, Any]:
    """
    MCP TOOL: query_document_and_reply
    Description: Search user documents using hybrid retrieval and produce an answer with citations.
    Args:
        question: User query or question
        doc_id: Optional specific document ID to restrict search. If omitted, searches all user documents.
        user_id: ID of the user asking the question
        top_k: Number of relevant context chunks to retrieve
    """
    doc_ids = [doc_id] if doc_id else None

    # Retrieve matching context chunks
    citations = hybrid_retriever_service.retrieve_context(
        query=question,
        doc_ids=doc_ids,
        top_k=top_k,
        search_mode="hybrid"
    )

    if not citations:
        return {
            "question": question,
            "doc_id": doc_id,
            "answer": "No relevant document evidence was found to answer your question.",
            "citations": [],
            "found_matches": False
        }

    # Format retrieved passages for LLM answer generation
    context_str = "\n\n".join([
        f"--- Source [Chunk #{c.chunk_index} | File: {c.filename} | DocID: {c.doc_id}] ---\n{c.content}"
        for c in citations
    ])

    prompt = f"""You are DocuBrain RAG Assistant. Answer the user question accurately using ONLY the provided document context.
If the context doesn't contain enough information to answer, state clearly what is missing.
Provide line/chunk citations in your answer when referencing facts.

User Question: {question}

Retrieved Document Context:
{context_str}

Answer:"""

    try:
        raw_answer = llm_service.generate_answer(prompt=prompt)
    except Exception as err:
        raw_answer = f"Generated answer based on retrieved context:\n\n{context_str[:1000]}..."

    citation_records = [
        {
            "doc_id": c.doc_id,
            "filename": c.filename,
            "chunk_index": c.chunk_index,
            "relevance_score": c.score,
            "snippet": c.content[:200]
        }
        for c in citations
    ]

    return {
        "question": question,
        "doc_id": doc_id,
        "answer": raw_answer,
        "citations": citation_records,
        "found_matches": True
    }


@mcp.tool()
def summarize_document(
    doc_id: str,
    user_id: str = "default_user"
) -> Dict[str, Any]:
    """
    MCP TOOL: summarize_document
    Description: Retrieve a specific document by doc_id and generate a clear, structured executive summary.
    Args:
        doc_id: Specific document ID to summarize
        user_id: ID of the user requesting summary
    """
    try:
        # Retrieve all chunks belonging to doc_id
        all_records = vector_store_service.collection.get(
            where={"doc_id": doc_id},
            include=["documents", "metadatas"]
        )
        if not all_records or not all_records.get("documents"):
            return {
                "success": False,
                "error": f"Document with ID '{doc_id}' not found."
            }

        docs = all_records["documents"]
        metas = all_records["metadatas"]
        filename = metas[0].get("filename", "Unknown Document") if metas else "Unknown Document"
        full_text = "\n\n".join(docs[:15])  # Cap to first 15 chunks for summary prompt

        prompt = f"""You are an executive document summarizer.
Provide a clear, high-level summary of the following document '{filename}'.

Document Content:
{full_text}

Executive Summary:
- **Core Theme & Topic**:
- **Key Findings & Main Points**:
- **Conclusion / Takeaway**:"""

        try:
            summary = llm_service.generate_answer(prompt=prompt)
        except Exception:
            summary = f"Summary of {filename} ({len(docs)} chunks):\n" + "\n".join([f"- {d[:150]}..." for d in docs[:5]])

        return {
            "success": True,
            "doc_id": doc_id,
            "filename": filename,
            "total_chunks": len(docs),
            "summary": summary
        }
    except Exception as err:
        return {"success": False, "error": f"Failed to summarize document: {str(err)}"}


@mcp.tool()
def list_documents(user_id: str = "default_user") -> Dict[str, Any]:
    """
    MCP TOOL: list_documents
    Description: List all documents uploaded and available in the RAG knowledge base.
    """
    docs_data = vector_store_service.get_all_documents()
    return {
        "user_id": user_id,
        "total_documents": len(docs_data),
        "documents": docs_data
    }


@mcp.tool()
def delete_document(doc_id: str, user_id: str = "default_user") -> Dict[str, Any]:
    """
    MCP TOOL: delete_document
    Description: Delete a document and its vector embeddings from the store.
    """
    success = vector_store_service.delete_document(doc_id)
    if success:
        hybrid_retriever_service.build_bm25_index()
        return {"success": True, "message": f"Document '{doc_id}' deleted successfully."}
    return {"success": False, "error": f"Document '{doc_id}' not found."}


# Exposed resource for direct document reading
@mcp.resource("resource://documents/{doc_id}")
def get_document_resource(doc_id: str) -> str:
    """Read full text content of a specific document via MCP resource URI."""
    all_records = vector_store_service.collection.get(
        where={"doc_id": doc_id},
        include=["documents"]
    )
    if all_records and all_records.get("documents"):
        return "\n\n".join(all_records["documents"])
    return f"Document '{doc_id}' not found."
