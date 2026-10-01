from typing import List
from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    upload_time: str
    file_size: int
    total_chunks: int
    chunking_strategy: str = "standard"


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentMetadata


class DocumentListResponse(BaseModel):
    documents: List[DocumentMetadata]
    total_documents: int
