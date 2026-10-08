from fastapi import APIRouter
from app.schemas.mcp import ArtifactRequest
from app.services.artifacts import build_artifact

router = APIRouter()


@router.post("/artifacts")
async def generate_chat_artifact(req: ArtifactRequest):
    """Build a visual artifact for a chat answer via the first active MCP server exposing `generate_artifact`."""
    return await build_artifact(
        question=req.question,
        answer=req.answer or "",
        sources=req.sources or [],
        artifact_type=req.artifact_type or "auto"
    )
