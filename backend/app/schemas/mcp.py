from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AddServerRequest(BaseModel):
    name: str
    url: str
    transport: Optional[str] = "sse"
    auth_type: Optional[str] = "none"
    auth_token: Optional[str] = ""


class TestConnectionRequest(BaseModel):
    url: str
    transport: Optional[str] = "sse"
    auth_type: Optional[str] = "none"
    auth_token: Optional[str] = ""


class CallToolRequest(BaseModel):
    server_id: str
    tool_name: str
    arguments: Optional[Dict[str, Any]] = {}


class ArtifactRequest(BaseModel):
    question: str
    answer: Optional[str] = ""
    sources: Optional[List[Dict[str, Any]]] = []
    artifact_type: Optional[str] = "auto"
