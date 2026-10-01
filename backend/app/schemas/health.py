from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    vector_db_connected: bool
    total_documents: int
    total_chunks: int
