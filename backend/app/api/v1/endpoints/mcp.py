from fastapi import APIRouter, Depends, Request, HTTPException, Body
from typing import Dict, Any, Optional
from app.mcp.server import (
    upload_document,
    query_document_and_reply,
    summarize_document,
    list_documents,
    delete_document,
    get_document_resource
)
from app.core.security import get_current_user_from_token

router = APIRouter()


@router.get("/tools")
async def get_mcp_tools(current_user: Dict[str, Any] = Depends(get_current_user_from_token)):
    """Return JSON-RPC / OpenAPI schema of all available MCP tools."""
    return {
        "mcp_version": "1.0",
        "server_name": "DocuBrain-RAG-MCP-Server",
        "authenticated_user": current_user,
        "tools": [
            {
                "name": "upload_document",
                "description": "Upload and index a text document into RAG vector store.",
                "parameters": {
                    "filename": "string",
                    "content_text": "string",
                    "chunking_strategy": "string (default: 'agentic')"
                }
            },
            {
                "name": "query_document_and_reply",
                "description": "Ask a question across all documents or a specific document ID.",
                "parameters": {
                    "question": "string",
                    "doc_id": "string (optional)",
                    "top_k": "integer (default: 5)"
                }
            },
            {
                "name": "summarize_document",
                "description": "Generate an executive summary of a specific document by doc_id.",
                "parameters": {
                    "doc_id": "string"
                }
            },
            {
                "name": "list_documents",
                "description": "List all uploaded documents in the knowledge base."
            },
            {
                "name": "delete_document",
                "description": "Delete a document by doc_id.",
                "parameters": {
                    "doc_id": "string"
                }
            }
        ]
    }


@router.post("/tools/call")
async def call_mcp_tool(
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Execute an MCP tool request for the authenticated user."""
    tool_name = payload.get("name")
    args = payload.get("arguments", {})
    user_id = current_user.get("user_id", "default_user")

    if tool_name == "upload_document":
        return upload_document(
            filename=args.get("filename", "document.txt"),
            content_text=args.get("content_text", ""),
            user_id=user_id,
            chunking_strategy=args.get("chunking_strategy", "agentic")
        )
    elif tool_name == "query_document_and_reply":
        return query_document_and_reply(
            question=args.get("question", ""),
            doc_id=args.get("doc_id"),
            user_id=user_id,
            top_k=args.get("top_k", 5)
        )
    elif tool_name == "summarize_document":
        return summarize_document(
            doc_id=args.get("doc_id", ""),
            user_id=user_id
        )
    elif tool_name == "list_documents":
        return list_documents(user_id=user_id)
    elif tool_name == "delete_document":
        return delete_document(
            doc_id=args.get("doc_id", ""),
            user_id=user_id
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown MCP tool '{tool_name}'")


@router.get("/resources/{doc_id}")
async def read_mcp_resource(
    doc_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
):
    """Read a document content resource."""
    content = get_document_resource(doc_id=doc_id)
    return {
        "uri": f"resource://documents/{doc_id}",
        "mime_type": "text/plain",
        "user_id": current_user.get("user_id"),
        "content": content
    }
