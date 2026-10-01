from fastapi import APIRouter
from app.schemas.health import HealthResponse
from app.services import vector_store_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    docs = vector_store_service.get_all_documents()
    total_chunks = vector_store_service.collection.count()
    return HealthResponse(
        status="healthy",
        vector_db_connected=True,
        total_documents=len(docs),
        total_chunks=total_chunks
    )
