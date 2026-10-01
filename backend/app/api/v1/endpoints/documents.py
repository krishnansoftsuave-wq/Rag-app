import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, Query, status

from app.core.config import UPLOAD_DIR, USE_LATE_CHUNKING
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentMetadata,
)
from app.services import (
    process_document,
    process_document_with_text,
    extract_text_from_file,
    vector_store_service,
    hybrid_retriever_service,
    late_chunker_service,
    semantic_chunker_service,
    agentic_chunker_service,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunking_strategy: Optional[str] = Query(
        "agentic",
        description="Chunking strategy: 'agentic', 'semantic', 'standard', or 'late'"
    ),
    use_late_chunking: Optional[bool] = Query(
        None,
        description="Legacy override for Late Chunking"
    )
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a name")

    # Determine strategy
    if use_late_chunking is True:
        strategy = "late"
    elif chunking_strategy in ["standard", "semantic", "agentic", "late"]:
        strategy = chunking_strategy
    else:
        strategy = "agentic"

    doc_id = str(uuid.uuid4())[:8]
    sanitized_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{sanitized_filename}")

    try:
        contents = await file.read()
        file_size = len(contents)

        with open(file_path, "wb") as f:
            f.write(contents)

        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if strategy == "agentic":
            full_text = extract_text_from_file(file_path, sanitized_filename)
            spans_data = agentic_chunker_service.chunk_text_agentically(
                full_text=full_text,
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
                    "full_text": full_text
                })
            embeddings = hybrid_retriever_service.embedding_model.encode(
                [c["content"] for c in chunks],
                show_progress_bar=False
            ).tolist()
        elif strategy == "semantic":
            full_text = extract_text_from_file(file_path, sanitized_filename)
            spans_data = semantic_chunker_service.chunk_text_semantically(
                full_text=full_text,
                model=hybrid_retriever_service.embedding_model
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
                    "full_text": full_text
                })
            embeddings = hybrid_retriever_service.embedding_model.encode(
                [c["content"] for c in chunks],
                show_progress_bar=False
            ).tolist()
        elif strategy == "late":
            full_text, chunks = process_document_with_text(file_path, sanitized_filename, doc_id)
            embeddings = late_chunker_service.encode_chunks(
                full_text=full_text,
                chunks=chunks,
                model=hybrid_retriever_service.embedding_model,
                use_late_chunking=True,
            )
        else: # "standard"
            full_text, chunks = process_document_with_text(file_path, sanitized_filename, doc_id)
            embeddings = late_chunker_service.encode_chunks(
                full_text=full_text,
                chunks=chunks,
                model=hybrid_retriever_service.embedding_model,
                use_late_chunking=False,
            )


        # Add to vector store with strategy metadata
        vector_store_service.add_chunks(
            doc_id=doc_id,
            filename=sanitized_filename,
            chunks=chunks,
            embeddings=embeddings,
            file_size=file_size,
            upload_time=upload_time,
            chunking_strategy=strategy
        )

        # Rebuild BM25 index
        hybrid_retriever_service.build_bm25_index()

        doc_meta = DocumentMetadata(
            doc_id=doc_id,
            filename=sanitized_filename,
            file_type=os.path.splitext(sanitized_filename)[1],
            upload_time=upload_time,
            file_size=file_size,
            total_chunks=len(chunks),
            chunking_strategy=strategy
        )

        return DocumentUploadResponse(
            message=f"Successfully processed '{sanitized_filename}' into {len(chunks)} chunks using strategy '{strategy}'.",
            document=doc_meta
        )


    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents():
    docs_data = vector_store_service.get_all_documents()
    documents = [DocumentMetadata(**d) for d in docs_data]
    return DocumentListResponse(
        documents=documents,
        total_documents=len(documents)
    )


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    success = vector_store_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    hybrid_retriever_service.build_bm25_index()
    return {"message": f"Document {doc_id} successfully deleted"}
