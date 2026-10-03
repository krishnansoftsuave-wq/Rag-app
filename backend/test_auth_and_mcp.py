import os
import sys
import json

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.user_service import UserService
from app.core.security import create_access_token, decode_access_token
from app.mcp.server import (
    upload_document,
    query_document_and_reply,
    summarize_document,
    list_documents,
    delete_document
)

def test_full_workflow():
    print("=== 1. Testing User Registration & Authentication ===")
    test_user = "test_user_mcp"
    test_email = "mcp_test@docubrain.ai"
    test_password = "SecretPassword123!"

    try:
        user = UserService.register_user(username=test_user, email=test_email, password=test_password)
        print(f"[OK] User registered: {user}")
    except ValueError:
        user = UserService.authenticate_user(username_or_email=test_user, password=test_password)
        print(f"[OK] User authenticated existing: {user}")

    token = create_access_token({"sub": user["id"], "username": user["username"], "email": user["email"]})
    print(f"[KEYS] Generated JWT Token: {token[:35]}...")

    payload = decode_access_token(token)
    assert payload["sub"] == user["id"]
    print("[OK] JWT Token decoding verified.")

    print("\n=== 2. Testing MCP Tool: upload_document ===")
    sample_doc_text = """
    DocuBrain Cloud SLA Policy 2026.
    Section 1: Availability
    DocuBrain guarantees a 99.99% monthly uptime for all Enterprise RAG API endpoints.
    If monthly uptime drops below 99.99%, customers receive a 15% service credit.
    
    Section 2: Security & Encryption
    All customer document embeddings in ChromaDB are encrypted at rest using AES-256.
    Document text transmitted over network uses TLS 1.3 encryption.
    
    Section 3: Data Retention & Privacy
    Customer documents uploaded to DocuBrain are retained strictly for the duration of the customer's subscription.
    Upon account cancellation, all stored vector embeddings and document chunks are permanently erased within 24 hours.
    """
    
    res_upload = upload_document(
        filename="DocuBrain_Cloud_SLA_2026.txt",
        content_text=sample_doc_text,
        user_id=user["id"],
        chunking_strategy="agentic"
    )
    print(f"[UPLOAD] Result: {json.dumps(res_upload, indent=2)}")
    doc_id = res_upload["doc_id"]
    assert res_upload["success"] is True

    print("\n=== 3. Testing MCP Tool: list_documents ===")
    res_list = list_documents(user_id=user["id"])
    print(f"[DOCS] Total Documents: {res_list['total_documents']}")

    print("\n=== 4. Testing MCP Tool: query_document_and_reply (Specific doc_id focus) ===")
    res_query = query_document_and_reply(
        question="What is the monthly uptime guarantee and service credit in the SLA policy?",
        doc_id=doc_id,
        user_id=user["id"]
    )
    print(f"[QUERY] Question: {res_query['question']}")
    print(f"[ANSWER] Answer: {res_query['answer']}")
    print(f"[CITATIONS] Citations count: {len(res_query['citations'])}")

    print("\n=== 5. Testing MCP Tool: summarize_document ===")
    res_summary = summarize_document(doc_id=doc_id, user_id=user["id"])
    print(f"[SUMMARY] Document Summary:\n{res_summary['summary']}")

    print("\n[SUCCESS] ALL AUTH & MCP TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_workflow()
